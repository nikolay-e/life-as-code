from __future__ import annotations

from datetime import date, timedelta

from scipy import stats as scipy_stats

from .constants import VELOCITY_SIGNIFICANCE
from .date_utils import filter_by_window, to_day_date, to_day_key
from .series import to_daily_series
from .stats import pearson_correlation_with_pvalue
from .types import (
    CorrelationMetrics,
    DataPoint,
    VelocityMetrics,
)


def calculate_correlation_metrics(
    hrv_data: list[DataPoint],
    rhr_data: list[DataPoint],
    sleep_data: list[DataPoint],
    strain_data: list[DataPoint],
    window_days: int = 30,
    ref_date: date | None = None,
) -> CorrelationMetrics:
    daily_hrv = to_daily_series(hrv_data, "mean")
    daily_rhr = to_daily_series(rhr_data, "mean")
    daily_sleep = to_daily_series(sleep_data, "last")
    daily_strain = to_daily_series(strain_data, "max")

    hrv_map = {
        to_day_key(d.date): d.value
        for d in filter_by_window(daily_hrv, window_days + 1, ref_date=ref_date)
        if d.value is not None
    }
    rhr_map = {
        to_day_key(d.date): d.value
        for d in filter_by_window(daily_rhr, window_days, ref_date=ref_date)
        if d.value is not None
    }
    sleep_map = {
        to_day_key(d.date): d.value
        for d in filter_by_window(daily_sleep, window_days, ref_date=ref_date)
        if d.value is not None
    }
    strain_map = {
        to_day_key(d.date): d.value
        for d in filter_by_window(daily_strain, window_days, ref_date=ref_date)
        if d.value is not None
    }

    hrv_rhr_x, hrv_rhr_y = [], []
    for dk, hrv_v in hrv_map.items():
        rhr_v = rhr_map.get(dk)
        if rhr_v is not None:
            hrv_rhr_x.append(hrv_v)
            hrv_rhr_y.append(rhr_v)
    hrv_rhr_corr, hrv_rhr_p = pearson_correlation_with_pvalue(hrv_rhr_x, hrv_rhr_y)

    sleep_hrv_x, sleep_hrv_y = [], []
    for dk in sorted(sleep_map.keys()):
        sleep_v = sleep_map[dk]
        next_day = to_day_date(dk) + timedelta(days=1)
        next_key = next_day.isoformat()
        next_hrv = hrv_map.get(next_key)
        if next_hrv is not None:
            sleep_hrv_x.append(sleep_v)
            sleep_hrv_y.append(next_hrv)
    sleep_hrv_corr, sleep_hrv_p = pearson_correlation_with_pvalue(
        sleep_hrv_x, sleep_hrv_y
    )

    strain_hrv_x, strain_hrv_y = [], []
    for dk in sorted(strain_map.keys()):
        strain_v = strain_map[dk]
        next_day = to_day_date(dk) + timedelta(days=1)
        next_key = next_day.isoformat()
        next_hrv = hrv_map.get(next_key)
        if next_hrv is not None:
            strain_hrv_x.append(strain_v)
            strain_hrv_y.append(next_hrv)
    strain_recovery_corr, strain_recovery_p = pearson_correlation_with_pvalue(
        strain_hrv_x, strain_hrv_y
    )

    p_values = [p for p in (hrv_rhr_p, sleep_hrv_p, strain_recovery_p) if p is not None]
    is_sig = any(p < 0.05 for p in p_values) if p_values else False

    return CorrelationMetrics(
        hrv_rhr_correlation=hrv_rhr_corr,
        hrv_rhr_p_value=hrv_rhr_p,
        sleep_hrv_lag_correlation=sleep_hrv_corr,
        sleep_hrv_p_value=sleep_hrv_p,
        strain_recovery_correlation=strain_recovery_corr,
        strain_recovery_p_value=strain_recovery_p,
        sample_size=min(len(hrv_rhr_x), len(sleep_hrv_x)),
        is_significant=is_sig,
    )


def _calc_metric_slope(
    data: list[DataPoint],
    metric: str,
    window_days: int,
    ref_date: date | None,
) -> float | None:
    from .date_utils import day_number
    from .series import to_daily_series_for_metric

    daily = to_daily_series_for_metric(data, metric)
    recent = [
        d
        for d in filter_by_window(daily, window_days, ref_date=ref_date)
        if d.value is not None
    ]
    if len(recent) < 7:
        return None
    xs = [day_number(d.date) for d in recent]
    ys: list[float] = [d.value for d in recent if d.value is not None]
    return float(scipy_stats.linregress(xs, ys).slope)


def _interpret_velocity(
    velocity: float | None, threshold: float, invert_good: bool = False
) -> str | None:
    if velocity is None:
        return None
    if abs(velocity) < threshold:
        return "stable"
    is_positive = velocity > 0
    is_good = not is_positive if invert_good else is_positive
    return "improving" if is_good else "declining"


def _interpret_weight_velocity(weight_v: float | None) -> str | None:
    if weight_v is None:
        return None
    if abs(weight_v) < VELOCITY_SIGNIFICANCE["weight"]:
        return "stable"
    return "gaining" if weight_v > 0 else "losing"


def calculate_velocity_metrics(
    hrv_data: list[DataPoint],
    rhr_data: list[DataPoint],
    weight_data: list[DataPoint],
    sleep_data: list[DataPoint],
    window_days: int = 14,
    ref_date: date | None = None,
) -> VelocityMetrics:
    hrv_v = _calc_metric_slope(hrv_data, "hrv", window_days, ref_date)
    rhr_v = _calc_metric_slope(rhr_data, "rhr", window_days, ref_date)
    weight_v = _calc_metric_slope(weight_data, "weight", window_days, ref_date)
    sleep_v = _calc_metric_slope(sleep_data, "sleep", window_days, ref_date)

    return VelocityMetrics(
        hrv_velocity=hrv_v,
        rhr_velocity=rhr_v,
        weight_velocity=weight_v,
        sleep_velocity=sleep_v,
        interpretation={
            "hrv": _interpret_velocity(hrv_v, VELOCITY_SIGNIFICANCE["hrv"]),
            "rhr": _interpret_velocity(
                rhr_v, VELOCITY_SIGNIFICANCE["rhr"], invert_good=True
            ),
            "weight": _interpret_weight_velocity(weight_v),
            "sleep": _interpret_velocity(sleep_v, VELOCITY_SIGNIFICANCE["sleep"]),
        },
    )
