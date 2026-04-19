from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from .constants import (
    ACWR_DANGER_THRESHOLD,
    ANOMALY_THRESHOLDS,
    DECORRELATION_BASELINE_MIN,
    DECORRELATION_CURRENT_MAX,
    ELEVATED_DAY_THRESHOLD,
    HIGH_STRAIN_Z_THRESHOLD,
    HRV_DROP_THRESHOLD,
    HRV_LOW_SIGMA,
    ILLNESS_RISK_THRESHOLDS,
    MIN_STD_THRESHOLD,
    OVERREACHING_THRESHOLDS,
    RECOVERED_Z_THRESHOLD,
    RECOVERY_LOOKBACK_DAYS,
    TACHYCARDIA_MIN_DAYS,
    TACHYCARDIA_SIGMA,
    WEIGHT_LOSS_THRESHOLD,
)
from .date_utils import filter_by_window, local_today, to_day_date, to_day_key
from .metrics import calculate_activity_metrics, calculate_baseline_metrics
from .series import to_daily_series, to_daily_series_for_metric
from .stats import mean_or_none
from .types import (
    AnomalyMetrics,
    AnomalyResult,
    ClinicalAlerts,
    DataPoint,
    DecorrelationAlert,
    IllnessRiskSignal,
    OverreachingMetrics,
    RecoveryCapacityMetrics,
)


def _count_tachycardia_days(
    rhr_data: list[DataPoint], baseline_window: int, ref_date: date | None
) -> tuple[int, bool]:
    rhr_bl = calculate_baseline_metrics(
        rhr_data, baseline_window, 7, "rhr", ref_date=ref_date
    )
    daily_rhr = to_daily_series(rhr_data, "mean")
    recent_rhr = sorted(
        [
            d
            for d in filter_by_window(daily_rhr, 7, ref_date=ref_date)
            if d.value is not None
        ],
        key=lambda d: d.date,
    )
    tachycardia_days = 0
    rhr_threshold = rhr_bl.mean + TACHYCARDIA_SIGMA * rhr_bl.std
    if rhr_bl.std > MIN_STD_THRESHOLD and recent_rhr:
        for d in reversed(recent_rhr):
            if d.value is not None and d.value > rhr_threshold:
                tachycardia_days += 1
            else:
                break
    return tachycardia_days, tachycardia_days >= TACHYCARDIA_MIN_DAYS


def _detect_acute_hrv_drop(
    hrv_data: list[DataPoint], ref_date: date | None
) -> tuple[float | None, bool]:
    daily_hrv = to_daily_series(hrv_data, "mean")
    recent_hrv_window = sorted(
        [
            d
            for d in filter_by_window(daily_hrv, 7, ref_date=ref_date)
            if d.value is not None
        ],
        key=lambda d: d.date,
    )
    if len(recent_hrv_window) < 3:
        return None, False
    latest_avg = mean_or_none(
        [d.value for d in recent_hrv_window[-2:] if d.value is not None]
    )
    prior_avg = mean_or_none(
        [d.value for d in recent_hrv_window[:-2] if d.value is not None]
    )
    if latest_avg is None or prior_avg is None or prior_avg <= 0:
        return None, False
    hrv_drop_percent = (prior_avg - latest_avg) / prior_avg
    return hrv_drop_percent, hrv_drop_percent > HRV_DROP_THRESHOLD


def _detect_progressive_weight_loss(
    weight_data: list[DataPoint], ref_date: date | None
) -> tuple[float | None, bool]:
    daily_weight = to_daily_series(weight_data, "last")
    last30_weight = sorted(
        [
            d
            for d in filter_by_window(daily_weight, 30, ref_date=ref_date)
            if d.value is not None
        ],
        key=lambda d: d.date,
    )
    if len(last30_weight) < 6:
        return None, False
    earliest_avg = mean_or_none(
        [d.value for d in last30_weight[:3] if d.value is not None]
    )
    latest_avg = mean_or_none(
        [d.value for d in last30_weight[-3:] if d.value is not None]
    )
    if earliest_avg is None or latest_avg is None or earliest_avg <= 0:
        return None, False
    weight_loss_percent = (earliest_avg - latest_avg) / earliest_avg
    return weight_loss_percent, weight_loss_percent > WEIGHT_LOSS_THRESHOLD


def _detect_severe_overtraining(
    strain_data: list[DataPoint],
    steps_data: list[DataPoint],
    hrv_z: float | None,
    ref_date: date | None,
) -> tuple[bool, float | None]:
    activity = calculate_activity_metrics(
        strain_data, steps_data, 7, 28, 7, ref_date=ref_date
    )
    if activity.acwr is None or hrv_z is None:
        return False, None
    acwr_excess = max(0, activity.acwr - 1.0)
    hrv_deficit = max(0, -hrv_z)
    overtraining_score = acwr_excess * hrv_deficit
    severe = activity.acwr > ACWR_DANGER_THRESHOLD and hrv_z < HRV_LOW_SIGMA
    return severe, overtraining_score


def calculate_clinical_alerts(
    rhr_data: list[DataPoint],
    hrv_data: list[DataPoint],
    weight_data: list[DataPoint],
    strain_data: list[DataPoint],
    steps_data: list[DataPoint] | None = None,
    baseline_window: int = 30,
    ref_date: date | None = None,
) -> ClinicalAlerts:
    hrv_bl = calculate_baseline_metrics(
        hrv_data, baseline_window, 7, "hrv", ref_date=ref_date
    )

    tachycardia_days, persistent_tachycardia = _count_tachycardia_days(
        rhr_data, baseline_window, ref_date
    )
    hrv_drop_percent, acute_hrv_drop = _detect_acute_hrv_drop(hrv_data, ref_date)
    weight_loss_percent, progressive_weight_loss = _detect_progressive_weight_loss(
        weight_data, ref_date
    )
    severe_overtraining, overtraining_score = _detect_severe_overtraining(
        strain_data, steps_data or [], hrv_bl.z_score, ref_date
    )

    any_alert = (
        persistent_tachycardia
        or acute_hrv_drop
        or progressive_weight_loss
        or severe_overtraining
    )

    return ClinicalAlerts(
        persistent_tachycardia=persistent_tachycardia,
        tachycardia_days=tachycardia_days,
        acute_hrv_drop=acute_hrv_drop,
        hrv_drop_percent=hrv_drop_percent,
        progressive_weight_loss=progressive_weight_loss,
        weight_loss_percent=weight_loss_percent,
        severe_overtraining=severe_overtraining,
        overtraining_score=overtraining_score,
        any_alert=any_alert,
    )


def _count_consecutive_low_hrv_days(
    hrv_data: list[DataPoint],
    hrv_bl_mean: float,
    hrv_bl_std: float,
    ref_date: date | None,
) -> int:
    daily_hrv = to_daily_series(hrv_data, "mean")
    recent_hrv = sorted(
        [
            d
            for d in filter_by_window(daily_hrv, 14, ref_date=ref_date)
            if d.value is not None
        ],
        key=lambda d: d.date,
        reverse=True,
    )
    consecutive_low = 0
    if hrv_bl_std > MIN_STD_THRESHOLD:
        for d in recent_hrv:
            if d.value is not None:
                z = (d.value - hrv_bl_mean) / hrv_bl_std
                if z < -1:
                    consecutive_low += 1
                else:
                    break
    return consecutive_low


def _compute_overreaching_score(
    strain_comp: float | None,
    hrv_comp: float | None,
    sleep_comp: float | None,
    rhr_comp: float | None,
) -> float | None:
    weights = {"strain": 0.3, "hrv": 0.3, "sleep": 0.25, "rhr": 0.15}
    total_weight = sum(weights.values())
    weighted_sum = 0.0
    available = 0
    for comp, w_key in [
        (strain_comp, "strain"),
        (hrv_comp, "hrv"),
        (sleep_comp, "sleep"),
        (rhr_comp, "rhr"),
    ]:
        if comp is not None:
            weighted_sum += comp * weights[w_key]
            available += 1
    if available < 2:
        return None
    return min(1.0, (weighted_sum / total_weight) / 3.0)


def _classify_overreaching_risk(
    score: float | None,
) -> Literal["low", "moderate", "high", "critical"] | None:
    if score is None:
        return None
    if score < OVERREACHING_THRESHOLDS["low"]:
        return "low"
    if score < OVERREACHING_THRESHOLDS["moderate"]:
        return "moderate"
    if score < OVERREACHING_THRESHOLDS["high"]:
        return "high"
    return "critical"


def calculate_overreaching_metrics(
    hrv_data: list[DataPoint],
    rhr_data: list[DataPoint],
    sleep_data: list[DataPoint],
    strain_data: list[DataPoint],
    baseline_window: int = 30,
    short_term_window: int = 7,
    ref_date: date | None = None,
) -> OverreachingMetrics:
    hrv_bl = calculate_baseline_metrics(
        hrv_data, baseline_window, short_term_window, "hrv", ref_date=ref_date
    )
    rhr_bl = calculate_baseline_metrics(
        rhr_data, baseline_window, short_term_window, "rhr", ref_date=ref_date
    )
    sleep_bl = calculate_baseline_metrics(
        sleep_data, baseline_window, short_term_window, "sleep", ref_date=ref_date
    )
    strain_bl = calculate_baseline_metrics(
        strain_data, baseline_window, short_term_window, "strain", ref_date=ref_date
    )

    strain_comp = max(0, strain_bl.z_score) if strain_bl.z_score is not None else None
    hrv_comp = max(0, -hrv_bl.z_score) if hrv_bl.z_score is not None else None
    sleep_comp = max(0, -sleep_bl.z_score) if sleep_bl.z_score is not None else None
    rhr_comp = max(0, rhr_bl.z_score) if rhr_bl.z_score is not None else None

    consecutive_low = _count_consecutive_low_hrv_days(
        hrv_data, hrv_bl.mean, hrv_bl.std, ref_date
    )
    score = _compute_overreaching_score(strain_comp, hrv_comp, sleep_comp, rhr_comp)
    risk_level = _classify_overreaching_risk(score)

    return OverreachingMetrics(
        score=score,
        risk_level=risk_level,
        components={
            "strain": strain_comp,
            "hrv": hrv_comp,
            "sleep": sleep_comp,
            "rhr": rhr_comp,
        },
        consecutive_low_recovery_days=consecutive_low,
    )


def _classify_anomaly_severity(abs_z: float) -> Literal["warning", "alert", "critical"]:
    if abs_z >= ANOMALY_THRESHOLDS["critical"]:
        return "critical"
    if abs_z >= ANOMALY_THRESHOLDS["alert"]:
        return "alert"
    return "warning"


def _collect_metric_anomalies(
    data: list[DataPoint],
    metric_name: str,
    display_name: str,
    baseline_window: int,
    lookback_days: int,
    ref_date: date | None,
    invert: bool = False,
    both_directions: bool = True,
) -> list[AnomalyResult]:
    daily = to_daily_series_for_metric(data, metric_name)
    bl = calculate_baseline_metrics(
        daily, baseline_window, 7, metric_name, ref_date=ref_date
    )
    recent = [
        d
        for d in filter_by_window(daily, lookback_days, ref_date=ref_date)
        if d.value is not None
    ]
    if bl.std < MIN_STD_THRESHOLD:
        return []
    results = []
    for d in recent:
        if d.value is None:
            continue
        raw_z = (d.value - bl.mean) / bl.std
        directional_z = -raw_z if invert else raw_z
        if not both_directions and directional_z < 0:
            continue
        abs_z = abs(raw_z)
        if abs_z >= ANOMALY_THRESHOLDS["warning"]:
            results.append(
                AnomalyResult(
                    date=d.date,
                    metric=display_name,
                    value=d.value,
                    z_score=raw_z,
                    severity=_classify_anomaly_severity(abs_z),
                )
            )
    return results


def detect_anomalies(
    hrv_data: list[DataPoint],
    rhr_data: list[DataPoint],
    sleep_data: list[DataPoint],
    stress_data: list[DataPoint],
    baseline_window: int = 30,
    lookback_days: int = 7,
    ref_date: date | None = None,
) -> AnomalyMetrics:
    today = ref_date or local_today()

    anomalies: list[AnomalyResult] = []
    anomalies += _collect_metric_anomalies(
        hrv_data,
        "hrv",
        "HRV",
        baseline_window,
        lookback_days,
        ref_date,
        invert=True,
        both_directions=False,
    )
    anomalies += _collect_metric_anomalies(
        rhr_data,
        "rhr",
        "Resting HR",
        baseline_window,
        lookback_days,
        ref_date,
        both_directions=False,
    )
    anomalies += _collect_metric_anomalies(
        sleep_data,
        "sleep",
        "Sleep",
        baseline_window,
        lookback_days,
        ref_date,
        invert=True,
        both_directions=False,
    )
    anomalies += _collect_metric_anomalies(
        stress_data,
        "stress",
        "Stress",
        baseline_window,
        lookback_days,
        ref_date,
        both_directions=False,
    )

    severity_order = {"critical": 0, "alert": 1, "warning": 2}
    anomalies.sort(
        key=lambda a: (a.date, severity_order.get(a.severity, 3)), reverse=True
    )

    has_recent = any(
        (today - to_day_date(to_day_key(a.date))).days <= 2 for a in anomalies
    )
    most_severe = next(
        (a for a in anomalies if a.severity == "critical"),
        anomalies[0] if anomalies else None,
    )

    return AnomalyMetrics(
        anomalies=anomalies,
        anomaly_count=len(anomalies),
        has_recent_anomaly=has_recent,
        most_severe=most_severe,
    )


def _compute_illness_components(
    hrv_vals: list[float],
    rhr_vals: list[float],
    sleep_vals: list[float],
    hrv_bl_mean: float,
    hrv_bl_std: float,
    rhr_bl_mean: float,
    rhr_bl_std: float,
    sleep_bl_mean: float,
    sleep_bl_std: float,
) -> tuple[float | None, float | None, float | None]:
    hrv_drop: float | None = None
    rhr_rise: float | None = None
    sleep_drop: float | None = None
    if hrv_vals and hrv_bl_std > MIN_STD_THRESHOLD:
        avg_hrv = sum(hrv_vals) / len(hrv_vals)
        hrv_drop = max(0, -(avg_hrv - hrv_bl_mean) / hrv_bl_std)
    if rhr_vals and rhr_bl_std > MIN_STD_THRESHOLD:
        avg_rhr = sum(rhr_vals) / len(rhr_vals)
        rhr_rise = max(0, (avg_rhr - rhr_bl_mean) / rhr_bl_std)
    if sleep_vals and sleep_bl_std > MIN_STD_THRESHOLD:
        avg_sleep = sum(sleep_vals) / len(sleep_vals)
        sleep_drop = max(0, -(avg_sleep - sleep_bl_mean) / sleep_bl_std)
    return hrv_drop, rhr_rise, sleep_drop


def _count_consecutive_elevated_days(
    hrv_map: dict,
    rhr_map: dict,
    hrv_bl_mean: float,
    hrv_bl_std: float,
    rhr_bl_mean: float,
    rhr_bl_std: float,
) -> int:
    all_dates = sorted(set(hrv_map.keys()) | set(rhr_map.keys()), reverse=True)
    consecutive = 0
    for dk in all_dates:
        day_dev = 0.0
        hrv_v = hrv_map.get(dk)
        rhr_v = rhr_map.get(dk)
        if hrv_v is not None and hrv_bl_std > MIN_STD_THRESHOLD:
            day_dev += max(0, -(hrv_v - hrv_bl_mean) / hrv_bl_std)
        if rhr_v is not None and rhr_bl_std > MIN_STD_THRESHOLD:
            day_dev += max(0, (rhr_v - rhr_bl_mean) / rhr_bl_std)
        if day_dev >= ELEVATED_DAY_THRESHOLD:
            consecutive += 1
        else:
            break
    return consecutive


def _classify_illness_risk(
    combined_deviation: float | None,
) -> Literal["low", "moderate", "high"] | None:
    if combined_deviation is None:
        return None
    if combined_deviation >= ILLNESS_RISK_THRESHOLDS["high"]:
        return "high"
    if combined_deviation >= ILLNESS_RISK_THRESHOLDS["moderate"]:
        return "moderate"
    return "low"


def calculate_illness_risk_signal(
    hrv_data: list[DataPoint],
    rhr_data: list[DataPoint],
    sleep_data: list[DataPoint],
    baseline_window: int = 30,
    lookback_days: int = 3,
    ref_date: date | None = None,
) -> IllnessRiskSignal:
    hrv_bl = calculate_baseline_metrics(
        hrv_data, baseline_window, 7, "hrv", ref_date=ref_date
    )
    rhr_bl = calculate_baseline_metrics(
        rhr_data, baseline_window, 7, "rhr", ref_date=ref_date
    )
    sleep_bl = calculate_baseline_metrics(
        sleep_data, baseline_window, 7, "sleep", ref_date=ref_date
    )

    recent_hrv = filter_by_window(
        to_daily_series(hrv_data, "mean"), lookback_days, ref_date=ref_date
    )
    recent_rhr = filter_by_window(
        to_daily_series(rhr_data, "mean"), lookback_days, ref_date=ref_date
    )
    recent_sleep = filter_by_window(
        to_daily_series(sleep_data, "last"), lookback_days, ref_date=ref_date
    )

    hrv_vals = [d.value for d in recent_hrv if d.value is not None]
    rhr_vals = [d.value for d in recent_rhr if d.value is not None]
    sleep_vals = [d.value for d in recent_sleep if d.value is not None]

    hrv_drop, rhr_rise, sleep_drop = _compute_illness_components(
        hrv_vals,
        rhr_vals,
        sleep_vals,
        hrv_bl.mean,
        hrv_bl.std,
        rhr_bl.mean,
        rhr_bl.std,
        sleep_bl.mean,
        sleep_bl.std,
    )

    present = [v for v in [hrv_drop, rhr_rise, sleep_drop] if v is not None]
    combined_deviation = sum(present) if present else None

    hrv_map = {to_day_key(d.date): d.value for d in recent_hrv if d.value is not None}
    rhr_map = {to_day_key(d.date): d.value for d in recent_rhr if d.value is not None}
    consecutive = _count_consecutive_elevated_days(
        hrv_map, rhr_map, hrv_bl.mean, hrv_bl.std, rhr_bl.mean, rhr_bl.std
    )

    return IllnessRiskSignal(
        combined_deviation=combined_deviation,
        consecutive_days_elevated=consecutive,
        risk_level=_classify_illness_risk(combined_deviation),
        components={
            "hrv_drop": hrv_drop,
            "rhr_rise": rhr_rise,
            "sleep_drop": sleep_drop,
        },
    )


def calculate_decorrelation_alert(
    hrv_data: list[DataPoint],
    rhr_data: list[DataPoint],
    recent_window: int = 14,
    baseline_window: int = 60,
    ref_date: date | None = None,
) -> DecorrelationAlert:
    from .correlations import calculate_correlation_metrics

    recent_corr = calculate_correlation_metrics(
        hrv_data, rhr_data, [], [], recent_window, ref_date=ref_date
    )
    baseline_corr = calculate_correlation_metrics(
        hrv_data, rhr_data, [], [], baseline_window, ref_date=ref_date
    )

    current = recent_corr.hrv_rhr_correlation
    baseline = baseline_corr.hrv_rhr_correlation

    correlation_delta: float | None = None
    is_decorrelated = False
    if current is not None and baseline is not None:
        correlation_delta = current - baseline
        is_decorrelated = (
            baseline < DECORRELATION_BASELINE_MIN
            and current > DECORRELATION_CURRENT_MAX
        )

    return DecorrelationAlert(
        is_decorrelated=is_decorrelated,
        current_correlation=current,
        baseline_correlation=baseline,
        correlation_delta=correlation_delta,
    )


def _track_recovery_after_high_strain(
    dk: str,
    strain_z: float,
    hrv_map: dict,
    hrv_bl_mean: float,
    hrv_bl_std: float,
    start_hrv_z: float | None,
) -> tuple[float | None, float | None]:
    start_date = to_day_date(dk)
    data_days_seen = 0
    for offset in range(1, RECOVERY_LOOKBACK_DAYS + 1):
        check_key = (start_date + timedelta(days=offset)).isoformat()
        check_hrv = hrv_map.get(check_key)
        if check_hrv is None:
            continue
        data_days_seen += 1
        hrv_z = (check_hrv - hrv_bl_mean) / hrv_bl_std
        if hrv_z >= RECOVERED_Z_THRESHOLD:
            efficiency = (
                (hrv_z - start_hrv_z) / strain_z
                if start_hrv_z is not None and strain_z != 0
                else None
            )
            return float(data_days_seen), efficiency
    return None, None


def _compute_recovery_events(
    strain_map: dict,
    hrv_map: dict,
    strain_bl_mean: float,
    strain_bl_std: float,
    hrv_bl_mean: float,
    hrv_bl_std: float,
) -> tuple[list[float], list[float], int]:
    recovery_times: list[float] = []
    efficiencies: list[float] = []
    high_strain_events = 0

    for dk in sorted(strain_map.keys()):
        strain_z = (strain_map[dk] - strain_bl_mean) / strain_bl_std
        if strain_z <= HIGH_STRAIN_Z_THRESHOLD:
            continue
        high_strain_events += 1
        start_hrv = hrv_map.get(dk)
        start_hrv_z = (
            (start_hrv - hrv_bl_mean) / hrv_bl_std if start_hrv is not None else None
        )
        recovery_days, efficiency = _track_recovery_after_high_strain(
            dk, strain_z, hrv_map, hrv_bl_mean, hrv_bl_std, start_hrv_z
        )
        if recovery_days is not None:
            recovery_times.append(recovery_days)
            if efficiency is not None:
                efficiencies.append(efficiency)

    return recovery_times, efficiencies, high_strain_events


def calculate_recovery_capacity(
    hrv_data: list[DataPoint],
    strain_data: list[DataPoint],
    baseline_window: int = 30,
    ref_date: date | None = None,
) -> RecoveryCapacityMetrics:
    hrv_bl = calculate_baseline_metrics(
        hrv_data, baseline_window, 7, "hrv", ref_date=ref_date
    )
    strain_bl = calculate_baseline_metrics(
        strain_data, baseline_window, 7, "strain", ref_date=ref_date
    )

    if hrv_bl.std < MIN_STD_THRESHOLD or strain_bl.std < MIN_STD_THRESHOLD:
        return RecoveryCapacityMetrics(
            avg_recovery_days=None,
            recovery_efficiency=None,
            high_strain_events=0,
            recovered_events=0,
        )

    hrv_map = {
        to_day_key(d.date): d.value
        for d in to_daily_series(hrv_data, "mean")
        if d.value is not None
    }
    strain_map = {
        to_day_key(d.date): d.value
        for d in to_daily_series(strain_data, "max")
        if d.value is not None
    }

    recovery_times, efficiencies, high_strain_events = _compute_recovery_events(
        strain_map, hrv_map, strain_bl.mean, strain_bl.std, hrv_bl.mean, hrv_bl.std
    )

    return RecoveryCapacityMetrics(
        avg_recovery_days=mean_or_none(recovery_times),
        recovery_efficiency=mean_or_none(efficiencies),
        high_strain_events=high_strain_events,
        recovered_events=len(recovery_times),
    )
