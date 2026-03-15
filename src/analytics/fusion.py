from __future__ import annotations

from datetime import date

from .constants import (
    MIN_OVERLAP_FOR_BLENDING,
    MIN_OVERLAP_FOR_NORMALIZATION,
    MIN_STD_THRESHOLD,
    SOURCE_STATS_WINDOW,
)
from .date_utils import filter_by_window, to_day_key
from .metric_series import FusedHealthData, FusedMetric, MetricSeries
from .stats import calculate_std, mean_or_none
from .types import (
    DataPoint,
    DataProvider,
    DataSourceSummary,
    FusedZScoreInput,
    UnifiedMetricPoint,
)


def _is_physiologically_valid(value: float, metric_type: str) -> bool:
    from .constants import PHYSIOLOGICAL_LIMITS

    limits = PHYSIOLOGICAL_LIMITS.get(metric_type)
    if not limits:
        return True
    return limits["min"] <= value <= limits["max"]


def _calculate_source_stats(
    values: list[DataPoint],
    window_days: int = SOURCE_STATS_WINDOW,
    ref_date: date | None = None,
) -> dict:
    window_data = filter_by_window(values, window_days, ref_date=ref_date)
    nums = [v.value for v in window_data if v.value is not None]
    if not nums:
        return {"mean": 0.0, "std": 1.0, "count": 0, "coverage": 0.0}
    mean = sum(nums) / len(nums)
    raw_std = calculate_std(nums)
    std = raw_std if raw_std > MIN_STD_THRESHOLD else 1.0
    coverage = min(1.0, len(nums) / window_days)
    return {"mean": mean, "std": std, "count": len(nums), "coverage": coverage}


def _calculate_source_weight(
    stats: dict[str, float], value: float | None, metric_type: str
) -> float:
    if stats["count"] == 0 or value is None:
        return 0.0
    weight = 1.0
    if stats["count"] < 7:
        weight *= 0.5
    elif stats["count"] < 14:
        weight *= 0.75
    elif stats["count"] < 21:
        weight *= 0.9
    weight *= 0.3 + 0.7 * stats["coverage"]
    if not _is_physiologically_valid(value, metric_type):
        weight *= 0.1
    return max(0.0, min(1.0, weight))


def _get_percentile(value: float, sorted_values: list[float]) -> float:
    if not sorted_values:
        return 0.5
    count = 0.0
    for v in sorted_values:
        if v < value:
            count += 1
        elif v == value:
            count += 0.5
    return count / len(sorted_values)


def _get_value_at_percentile(percentile: float, sorted_values: list[float]) -> float:
    if not sorted_values:
        return 0.0
    import math

    clamped_p = max(0.0, min(1.0, percentile))
    index = clamped_p * (len(sorted_values) - 1)
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return sorted_values[lower]
    fraction = index - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def normalize_garmin_strain_to_whoop_scale(
    garmin_values: list[DataPoint],
    whoop_values: list[DataPoint],
) -> tuple[list[DataPoint], bool]:
    garmin_by_day = {
        to_day_key(v.date): v.value for v in garmin_values if v.value is not None
    }
    whoop_by_day = {
        to_day_key(v.date): v.value for v in whoop_values if v.value is not None
    }

    overlap_garmin: list[float] = []
    overlap_whoop: list[float] = []
    for dk, g_val in garmin_by_day.items():
        w_val = whoop_by_day.get(dk)
        if w_val is not None and g_val is not None:
            overlap_garmin.append(g_val)
            overlap_whoop.append(w_val)

    if len(overlap_garmin) < MIN_OVERLAP_FOR_NORMALIZATION:
        return garmin_values, False

    sorted_overlap_garmin = sorted(overlap_garmin)
    sorted_overlap_whoop = sorted(overlap_whoop)

    result: list[DataPoint] = []
    for gv in garmin_values:
        if gv.value is None:
            result.append(gv)
            continue
        pct = _get_percentile(gv.value, sorted_overlap_garmin)
        normalized = _get_value_at_percentile(pct, sorted_overlap_whoop)
        result.append(DataPoint(date=gv.date, value=normalized))
    return result, True


def _compute_source_z(value: float | None, stats: dict) -> float | None:
    if value is not None and stats["std"] > 0:
        return float((value - stats["mean"]) / stats["std"])
    return None


def _concordance_factor(g_z: float | None, w_z: float | None) -> float:
    if g_z is None or w_z is None:
        return 1.0
    z_diff = abs(g_z - w_z)
    if z_diff > 2.0:
        return 0.5
    if z_diff > 1.0:
        return 0.75
    return 1.0


def _fuse_both_sources(
    g_val: float,
    w_val: float,
    g_weight: float,
    w_weight: float,
    g_z: float | None,
    w_z: float | None,
    has_enough_overlap: bool,
) -> tuple[float | None, float | None, float, DataProvider]:
    total_weight = g_weight + w_weight
    if total_weight <= 0:
        return None, None, 0.0, "garmin"
    if has_enough_overlap:
        fused_value = (g_val * g_weight + w_val * w_weight) / total_weight
        fused_z = (
            ((g_z or 0) * g_weight + (w_z or 0) * w_weight) / total_weight
            if g_z is not None and w_z is not None
            else (g_z or w_z)
        )
        concordance = _concordance_factor(g_z, w_z)
        confidence = min(1.0, (total_weight / 2) * concordance)
        return fused_value, fused_z, confidence, "blended"
    prefer_whoop = w_weight >= g_weight
    return (
        w_val if prefer_whoop else g_val,
        w_z if prefer_whoop else g_z,
        min(1.0, max(g_weight, w_weight) * 0.6),
        "whoop" if prefer_whoop else "garmin",
    )


def _fuse_single_source(
    val: float,
    z: float | None,
    weight: float,
    provider: DataProvider,
) -> tuple[float | None, float | None, float, DataProvider]:
    return val, z, min(1.0, weight * 0.8), provider


def _fuse_point(
    g_val: float | None,
    w_val: float | None,
    g_weight: float,
    w_weight: float,
    g_z: float | None,
    w_z: float | None,
    has_enough_overlap: bool,
) -> tuple[float | None, float | None, float, DataProvider]:
    if g_val is not None and w_val is not None:
        return _fuse_both_sources(
            g_val, w_val, g_weight, w_weight, g_z, w_z, has_enough_overlap
        )
    if g_val is not None:
        return _fuse_single_source(g_val, g_z, g_weight, "garmin")
    if w_val is not None:
        return _fuse_single_source(w_val, w_z, w_weight, "whoop")
    return None, None, 0.0, "garmin"


def blended_merge(
    garmin_data: list[DataPoint],
    whoop_data: list[DataPoint],
    metric_type: str,
    normalized_garmin_data: list[DataPoint] | None = None,
    ref_date: date | None = None,
) -> list[UnifiedMetricPoint]:
    effective_garmin = normalized_garmin_data or garmin_data
    garmin_stats = _calculate_source_stats(effective_garmin, ref_date=ref_date)
    whoop_stats = _calculate_source_stats(whoop_data, ref_date=ref_date)

    garmin_map = {
        to_day_key(v.date): v.value for v in effective_garmin if v.value is not None
    }
    whoop_map = {to_day_key(v.date): v.value for v in whoop_data if v.value is not None}

    overlap_days = sum(1 for dk in garmin_map if dk in whoop_map)
    has_enough_overlap = overlap_days >= MIN_OVERLAP_FOR_BLENDING

    all_dates = set(garmin_map.keys()) | set(whoop_map.keys())
    result: list[UnifiedMetricPoint] = []

    for date_key in all_dates:
        g_val = garmin_map.get(date_key)
        w_val = whoop_map.get(date_key)
        g_weight = _calculate_source_weight(garmin_stats, g_val, metric_type)
        w_weight = _calculate_source_weight(whoop_stats, w_val, metric_type)
        g_z = _compute_source_z(g_val, garmin_stats)
        w_z = _compute_source_z(w_val, whoop_stats)

        fused_value, fused_z, confidence, provider = _fuse_point(
            g_val, w_val, g_weight, w_weight, g_z, w_z, has_enough_overlap
        )

        result.append(
            UnifiedMetricPoint(
                date=date_key,
                value=fused_value,
                z_score=fused_z,
                garmin_value=g_val,
                whoop_value=w_val,
                garmin_z_score=g_z,
                whoop_z_score=w_z,
                provider=provider,
                confidence=confidence,
            )
        )

    return sorted(result, key=lambda p: p.date)


def fuse_hrv(
    garmin_hrv: list[DataPoint],
    whoop_hrv: list[DataPoint],
    ref_date: date | None = None,
) -> list[UnifiedMetricPoint]:
    return blended_merge(garmin_hrv, whoop_hrv, "hrv", ref_date=ref_date)


def fuse_sleep(
    garmin_sleep: list[DataPoint],
    whoop_sleep: list[DataPoint],
    ref_date: date | None = None,
) -> list[UnifiedMetricPoint]:
    return blended_merge(garmin_sleep, whoop_sleep, "sleep", ref_date=ref_date)


def fuse_resting_hr(
    garmin_rhr: list[DataPoint],
    whoop_rhr: list[DataPoint],
    ref_date: date | None = None,
) -> list[UnifiedMetricPoint]:
    return blended_merge(garmin_rhr, whoop_rhr, "resting_hr", ref_date=ref_date)


def fuse_strain(
    whoop_strain: list[DataPoint],
    garmin_atl: list[DataPoint],
    ref_date: date | None = None,
) -> list[UnifiedMetricPoint]:
    normalized_garmin, normalization_succeeded = normalize_garmin_strain_to_whoop_scale(
        garmin_atl, whoop_strain
    )
    if normalization_succeeded:
        return blended_merge(
            garmin_atl, whoop_strain, "strain", normalized_garmin, ref_date=ref_date
        )
    return blended_merge(garmin_atl, whoop_strain, "strain", ref_date=ref_date)


def fuse_calories(
    garmin_calories: list[DataPoint],
    whoop_calories: list[DataPoint],
    ref_date: date | None = None,
) -> list[UnifiedMetricPoint]:
    return blended_merge(garmin_calories, whoop_calories, "calories", ref_date=ref_date)


def unified_to_data_points(data: list[UnifiedMetricPoint]) -> list[DataPoint]:
    return [DataPoint(date=d.date, value=d.value) for d in data]


def get_latest_fused_input(data: list[UnifiedMetricPoint]) -> FusedZScoreInput | None:
    if not data:
        return None
    sorted_data = sorted(data, key=lambda d: d.date, reverse=True)
    latest = next((d for d in sorted_data if d.value is not None), None)
    if latest is None:
        return None
    return FusedZScoreInput(confidence=latest.confidence, source=latest.provider)


def get_fusion_stats(data: list[UnifiedMetricPoint]) -> dict:
    garmin_only = sum(
        1 for d in data if d.garmin_value is not None and d.whoop_value is None
    )
    whoop_only = sum(
        1 for d in data if d.whoop_value is not None and d.garmin_value is None
    )
    blended = sum(
        1 for d in data if d.garmin_value is not None and d.whoop_value is not None
    )
    garmin_days = sum(1 for d in data if d.garmin_value is not None)
    whoop_days = sum(1 for d in data if d.whoop_value is not None)
    avg_confidence = mean_or_none([d.confidence for d in data]) or 0.0
    total = len(data)
    return {
        "total": total,
        "garmin_only": garmin_only,
        "whoop_only": whoop_only,
        "blended": blended,
        "avg_confidence": avg_confidence,
        "garmin_coverage": garmin_days / total if total > 0 else 0,
        "whoop_coverage": whoop_days / total if total > 0 else 0,
    }


def get_data_source_summary(fused: FusedHealthData) -> list[DataSourceSummary]:
    metrics = [
        ("HRV", fused.hrv.unified),
        ("Sleep", fused.sleep.unified),
        ("Resting HR", fused.resting_hr.unified),
        ("Strain", fused.strain.unified),
        ("Calories", fused.calories.unified),
    ]
    result: list[DataSourceSummary] = []
    for name, data in metrics:
        stats = get_fusion_stats(data)
        result.append(
            DataSourceSummary(
                metric=name,
                total=stats["total"],
                garmin_only=stats["garmin_only"],
                whoop_only=stats["whoop_only"],
                blended=stats["blended"],
                avg_confidence=stats["avg_confidence"],
            )
        )
    return result


def _build_fused_metric(
    unified: list[UnifiedMetricPoint],
    metric: str,
    garmin_raw: list[DataPoint],
    whoop_raw: list[DataPoint],
) -> FusedMetric:
    blended_points = unified_to_data_points(unified)
    blended = MetricSeries(metric=metric, source="blended", points=blended_points)
    garmin = (
        MetricSeries(metric=metric, source="garmin", points=garmin_raw)
        if garmin_raw
        else None
    )
    whoop = (
        MetricSeries(metric=metric, source="whoop", points=whoop_raw)
        if whoop_raw
        else None
    )
    return FusedMetric(unified=unified, blended=blended, garmin=garmin, whoop=whoop)


def create_fused_health_data(raw, ref_date: date | None = None) -> FusedHealthData:
    from .data_loader import RawHealthData

    r: RawHealthData = raw

    hrv_unified = fuse_hrv(r.hrv_garmin, r.hrv_whoop, ref_date=ref_date)
    sleep_unified = fuse_sleep(r.sleep_garmin, r.sleep_whoop, ref_date=ref_date)
    rhr_unified = fuse_resting_hr(r.rhr_garmin, r.rhr_whoop, ref_date=ref_date)
    strain_unified = fuse_strain(r.strain_whoop, r.strain_garmin, ref_date=ref_date)
    calories_unified = fuse_calories(
        r.calories_garmin, r.calories_whoop, ref_date=ref_date
    )

    return FusedHealthData(
        hrv=_build_fused_metric(hrv_unified, "hrv", r.hrv_garmin, r.hrv_whoop),
        sleep=_build_fused_metric(
            sleep_unified, "sleep", r.sleep_garmin, r.sleep_whoop
        ),
        resting_hr=_build_fused_metric(rhr_unified, "rhr", r.rhr_garmin, r.rhr_whoop),
        strain=_build_fused_metric(
            strain_unified, "strain", r.strain_garmin, r.strain_whoop
        ),
        calories=_build_fused_metric(
            calories_unified, "calories", r.calories_garmin, r.calories_whoop
        ),
    )
