from __future__ import annotations

import math
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date

from .constants import (
    MAD_SCALE_FACTOR,
    MAX_SLEEP_TARGET_WINDOW,
    MAX_STEPS_FLOOR_WINDOW,
    METRIC_COMPLETENESS_THRESHOLDS,
    MIN_SAMPLE_SIZE,
    MIN_STD_THRESHOLD,
    MIN_STEPS_FLOOR_DATA,
    STEP_FLOOR_FALLBACK,
    STEPS_FLOOR_PERCENTILE,
)
from .date_utils import (
    dates_in_window,
    day_number,
    filter_by_window,
    filter_by_window_range,
    local_today,
    to_day_date,
    to_day_key,
)
from .series import (
    get_window_range_values,
    get_window_values,
    to_daily_series,
    to_daily_series_for_metric,
)
from .stats import (
    calculate_ema_value,
    calculate_mad,
    calculate_median,
    calculate_percentile,
    calculate_robust_stats,
    calculate_std,
    mean_or_none,
    sum_or_none,
    winsorize,
)
from .types import (
    ActivityMetrics,
    BaselineMetrics,
    BaselineOptions,
    CaloriesMetrics,
    DataPoint,
    DataQuality,
    DayMetrics,
    DayOverDayDelta,
    DayOverDayMetrics,
    EnergyBalanceMetrics,
    FusedZScoreInput,
    HealthScore,
    HealthScoreContributor,
    RecoveryMetrics,
    SleepMetrics,
    WeightMetrics,
)

# ============================================
# DATA QUALITY
# ============================================


def _calculate_freshness_score(latency_days: int | None, tau: float = 5.0) -> float:
    if latency_days is None:
        return 0.0
    return math.exp(-latency_days / tau)


def _calculate_outlier_rate(values: list[float]) -> float:
    if len(values) < 4:
        return 0.0
    median = calculate_median(values)
    mad = calculate_mad(values)
    scaled_mad = MAD_SCALE_FACTOR * mad
    if scaled_mad < MIN_STD_THRESHOLD:
        sorted_vals = sorted(values)
        q1 = calculate_percentile(sorted_vals, 25)
        q3 = calculate_percentile(sorted_vals, 75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        outliers = [v for v in values if v < lower_bound or v > upper_bound]
        return len(outliers) / len(values) if values else 0.0
    outliers = [v for v in values if abs((v - median) / scaled_mad) > 3]
    return len(outliers) / len(values)


def _calculate_missing_streak(dates_in_win: set[str], dates_with_data: set[str]) -> int:
    sorted_dates = sorted(dates_in_win)
    max_streak = 0
    current_streak = 0
    for d in sorted_dates:
        if d not in dates_with_data:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0
    return max_streak


def calculate_data_quality(
    data: list[DataPoint],
    window_days: int,
    metric_name: str = "hrv",
    ref_date: date | None = None,
) -> DataQuality:
    today = ref_date or local_today()
    dates_in_win = dates_in_window(window_days, ref_date=today)
    daily = to_daily_series_for_metric(data, metric_name)
    data_in_window = filter_by_window(daily, window_days, ref_date=today)
    valid_data = [d for d in data_in_window if d.value is not None]
    dates_with_data = {to_day_key(d.date) for d in valid_data}

    days_with_data = sum(1 for d in dates_in_win if d in dates_with_data)
    actual_window_size = len(dates_in_win)
    coverage = days_with_data / actual_window_size if actual_window_size > 0 else 0.0

    latency_days: int | None = None
    if valid_data:
        from .date_utils import to_day_date

        sorted_dates = sorted(valid_data, key=lambda d: d.date, reverse=True)
        last_date = to_day_date(to_day_key(sorted_dates[0].date))
        latency_days = (today - last_date).days

    values = [d.value for d in valid_data if d.value is not None]
    outlier_rate = _calculate_outlier_rate(values)
    missing_streak = _calculate_missing_streak(dates_in_win, dates_with_data)
    freshness_score = _calculate_freshness_score(latency_days)
    outlier_penalty = 1 - outlier_rate

    min_points_for_stats = 14
    data_sufficiency = min(1.0, days_with_data / min_points_for_stats)
    effective_coverage = 0.7 * coverage + 0.3 * data_sufficiency
    raw_confidence = effective_coverage * outlier_penalty * freshness_score
    confidence = min(1.0, raw_confidence)

    return DataQuality(
        coverage=coverage,
        latency_days=latency_days,
        outlier_rate=outlier_rate,
        missing_streak=missing_streak,
        total_points=actual_window_size,
        valid_points=days_with_data,
        confidence=confidence,
        freshness_score=freshness_score,
    )


# ============================================
# DAY COMPLETENESS
# ============================================


def calculate_day_completeness(
    ref_date: date | None = None, sleep_target_minutes: float | None = None
) -> float:
    import os
    from datetime import datetime, timedelta, timezone

    offset_hours = int(os.getenv("BOT_TIMEZONE_OFFSET_HOURS", "0"))
    tz = timezone(timedelta(hours=offset_hours))
    now = datetime.now(tz)
    local_today_date = now.date()
    effective_date = ref_date or local_today_date
    if effective_date < local_today_date:
        return 1.0
    hours_elapsed = now.hour + now.minute / 60
    sleep_hours = (sleep_target_minutes or 480) / 60
    waking_hours = max(12, min(18, 24 - sleep_hours))
    complete_cutoff = min(22, 6 + waking_hours)
    if hours_elapsed >= complete_cutoff:
        return 1.0
    return min(1.0, hours_elapsed / waking_hours)


def should_use_today_metric(
    data: list[DataPoint],
    metric_type: str,
    ref_date: date | None = None,
) -> tuple[bool, list[DataPoint], str]:
    effective_date = ref_date or local_today()
    today_str = effective_date.isoformat()
    completeness = calculate_day_completeness(ref_date)
    threshold = METRIC_COMPLETENESS_THRESHOLDS.get(metric_type, 0.8)

    today_entry = next((d for d in data if to_day_key(d.date) == today_str), None)
    has_today = today_entry is not None and today_entry.value is not None

    if not has_today:
        return False, data, f"No {metric_type} data for {today_str}"

    if completeness >= threshold:
        return True, data, f"Day {round(completeness * 100)}% complete"

    filtered = [d for d in data if to_day_key(d.date) != today_str]
    return (
        False,
        filtered,
        f"Day {round(completeness * 100)}% complete - using previous for {metric_type}",
    )


# ============================================
# BASELINE METRICS
# ============================================

_baseline_cache: ContextVar[dict | None] = ContextVar("_baseline_cache", default=None)


@contextmanager
def baseline_cache_scope():
    _token = _baseline_cache.set({})
    try:
        yield
    finally:
        _baseline_cache.set(None)


def _linear_slope_per_day(
    points: list[DataPoint], winsorize_pct: tuple[float, float] | None = None
) -> float | None:
    pts = [(day_number(p.date), p.value) for p in points if p.value is not None]
    if len(pts) < 7:
        return None
    xs = [p[0] for p in pts]
    ys_raw = [p[1] for p in pts]
    ys = (
        winsorize(ys_raw, winsorize_pct[0], winsorize_pct[1])
        if winsorize_pct
        else ys_raw
    )
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=False))
    den = sum((x - x_mean) ** 2 for x in xs)
    return num / den if den != 0 else None


def _build_cache_key(
    data: list[DataPoint],
    baseline_window: int,
    short_term_window: int,
    metric_name: str,
    trend_window: int,
    options: BaselineOptions | None,
    ref_date: date | None,
) -> tuple:
    data_fingerprint = (
        len(data),
        data[0].date if data else None,
        data[-1].date if data else None,
    )
    opts_key = (
        (
            options.exclude_recent_days_from_baseline,
            options.regression_uses_real_days,
            options.winsorize_trend,
        )
        if options
        else None
    )
    return (
        data_fingerprint,
        baseline_window,
        short_term_window,
        metric_name,
        trend_window,
        opts_key,
        ref_date,
    )


def calculate_baseline_metrics(
    data: list[DataPoint],
    baseline_window: int = 30,
    short_term_window: int = 7,
    metric_name: str = "hrv",
    trend_window: int = 7,
    options: BaselineOptions | None = None,
    ref_date: date | None = None,
) -> BaselineMetrics:
    cache = _baseline_cache.get()
    if cache is not None:
        cache_key = _build_cache_key(
            data,
            baseline_window,
            short_term_window,
            metric_name,
            trend_window,
            options,
            ref_date,
        )
        cached: BaselineMetrics | None = cache.get(cache_key)
        if cached is not None:
            return cached

    result = _calculate_baseline_metrics_impl(
        data,
        baseline_window,
        short_term_window,
        metric_name,
        trend_window,
        options,
        ref_date,
    )

    cache = _baseline_cache.get()
    if cache is not None:
        cache_key = _build_cache_key(
            data,
            baseline_window,
            short_term_window,
            metric_name,
            trend_window,
            options,
            ref_date,
        )
        cache[cache_key] = result
    return result


def _calculate_baseline_metrics_impl(
    data: list[DataPoint],
    baseline_window: int = 30,
    short_term_window: int = 7,
    metric_name: str = "hrv",
    trend_window: int = 7,
    options: BaselineOptions | None = None,
    ref_date: date | None = None,
) -> BaselineMetrics:
    opts = options or BaselineOptions()
    daily = to_daily_series_for_metric(data, metric_name)
    exclude_days = max(0, opts.exclude_recent_days_from_baseline)

    if exclude_days > 0:
        baseline_slice = filter_by_window_range(
            daily,
            baseline_window + exclude_days,
            exclude_days - 1,
            ref_date=ref_date,
        )
    else:
        baseline_slice = filter_by_window(daily, baseline_window, ref_date=ref_date)

    baseline_data = [d for d in baseline_slice if d.value is not None]
    short_term_data = [
        d
        for d in filter_by_window(daily, short_term_window, ref_date=ref_date)
        if d.value is not None
    ]

    if ref_date is not None:
        ref_str = ref_date.isoformat()
        sorted_daily = sorted(
            [d for d in daily if d.value is not None and d.date <= ref_str],
            key=lambda d: d.date,
        )
    else:
        sorted_daily = sorted(
            [d for d in daily if d.value is not None], key=lambda d: d.date
        )
    current_value = sorted_daily[-1].value if sorted_daily else None

    if not baseline_data:
        return BaselineMetrics(
            mean=0,
            std=0,
            median=0,
            cv=0,
            current_value=current_value,
            z_score=None,
            shifted_z_score=None,
            percent_change=None,
            trend_slope=None,
            short_term_mean=None,
            long_term_mean=None,
        )

    raw_values = [d.value for d in baseline_data if d.value is not None]
    baseline_values = winsorize(raw_values, 5, 95)
    stats = calculate_robust_stats(baseline_values)
    mean = stats["mean"]
    std = stats["std"]
    median = stats["median"]
    cv = std / abs(mean) if mean != 0 else 0

    adaptive_min_samples = min(MIN_SAMPLE_SIZE, max(3, baseline_window // 2))
    has_sufficient_data = len(baseline_values) >= adaptive_min_samples
    has_valid_std = std >= MIN_STD_THRESHOLD

    z_score: float | None = None
    if current_value is not None and has_sufficient_data and has_valid_std:
        z_score = (current_value - mean) / std

    percent_change = (
        ((current_value - mean) / abs(mean)) * 100
        if current_value is not None and mean != 0
        else None
    )

    short_term_values = [d.value for d in short_term_data if d.value is not None]
    short_term_mean = mean_or_none(short_term_values)

    shifted_z_score: float | None = None
    if short_term_mean is not None and has_sufficient_data and has_valid_std:
        shifted_z_score = (short_term_mean - mean) / std

    trend_data = [
        d
        for d in filter_by_window(daily, trend_window, ref_date=ref_date)
        if d.value is not None
    ]
    prev_trend_data = [
        d
        for d in filter_by_window_range(
            daily, trend_window * 2, trend_window, ref_date=ref_date
        )
        if d.value is not None
    ]
    raw_trend_values = [d.value for d in trend_data if d.value is not None]
    raw_prev_trend_values = [d.value for d in prev_trend_data if d.value is not None]
    trend_values = (
        winsorize(raw_trend_values, 5, 95) if opts.winsorize_trend else raw_trend_values
    )
    prev_trend_values = (
        winsorize(raw_prev_trend_values, 5, 95)
        if opts.winsorize_trend
        else raw_prev_trend_values
    )

    min_data_for_trend = max(3, int(trend_window * 0.7))
    has_valid_trend = (
        len(trend_values) >= min_data_for_trend
        and len(prev_trend_values) >= min_data_for_trend
    )

    trend_slope: float | None = None
    if has_valid_trend:
        if trend_window > 14 and len(trend_values) >= 7:
            if opts.regression_uses_real_days:
                trend_slope = _linear_slope_per_day(
                    trend_data,
                    (5, 95) if opts.winsorize_trend else None,
                )
            else:
                n = len(trend_values)
                x_mean = (n - 1) / 2
                y_mean = sum(trend_values) / n
                num = sum((i - x_mean) * (trend_values[i] - y_mean) for i in range(n))
                den = sum((i - x_mean) ** 2 for i in range(n))
                trend_slope = num / den if den != 0 else None
        else:
            current_median = calculate_median(trend_values)
            prev_median = calculate_median(prev_trend_values)
            trend_slope = (current_median - prev_median) / trend_window

    return BaselineMetrics(
        mean=mean,
        std=std,
        median=median,
        cv=cv,
        current_value=current_value,
        z_score=z_score,
        shifted_z_score=shifted_z_score,
        percent_change=percent_change,
        trend_slope=trend_slope,
        short_term_mean=short_term_mean,
        long_term_mean=mean,
    )


# ============================================
# RECOVERY METRICS
# ============================================


def calculate_recovery_metrics(
    hrv_data: list[DataPoint],
    rhr_data: list[DataPoint],
    stress_data: list[DataPoint],
    recovery_data: list[DataPoint],
    short_term_window: int = 7,
    long_term_window: int = 30,
    trend_window: int = 7,
    ref_date: date | None = None,
) -> RecoveryMetrics:
    hrv_bl = calculate_baseline_metrics(
        hrv_data,
        long_term_window,
        short_term_window,
        "hrv",
        trend_window,
        ref_date=ref_date,
    )
    rhr_bl = calculate_baseline_metrics(
        rhr_data,
        long_term_window,
        short_term_window,
        "rhr",
        trend_window,
        ref_date=ref_date,
    )

    hrv_rhr_imbalance: float | None = None
    if hrv_bl.z_score is not None and rhr_bl.z_score is not None:
        hrv_rhr_imbalance = -hrv_bl.z_score + rhr_bl.z_score

    recovery_bl = calculate_baseline_metrics(
        recovery_data,
        long_term_window,
        short_term_window,
        "recovery",
        trend_window,
        ref_date=ref_date,
    )

    daily_stress = to_daily_series(stress_data, "mean")
    stress_short = get_window_values(daily_stress, short_term_window, ref_date=ref_date)
    stress_long = get_window_values(daily_stress, long_term_window, ref_date=ref_date)
    stress_trend_vals = get_window_values(daily_stress, trend_window, ref_date=ref_date)
    stress_prev_vals = get_window_range_values(
        daily_stress, trend_window * 2, trend_window, ref_date=ref_date
    )

    stress_load_short = sum_or_none(stress_short)
    stress_load_long = sum_or_none(stress_long)
    stress_trend_mean = mean_or_none(stress_trend_vals)
    stress_prev_mean = mean_or_none(stress_prev_vals)

    min_data = min(14, max(3, int(trend_window * 0.7)))
    has_valid = (
        stress_trend_mean is not None
        and stress_prev_mean is not None
        and len(stress_trend_vals) >= min_data
        and len(stress_prev_vals) >= min_data
    )
    stress_trend = (
        (stress_trend_mean - stress_prev_mean)
        if has_valid and stress_trend_mean is not None and stress_prev_mean is not None
        else None
    )

    has_recovery = bool(recovery_data)
    return RecoveryMetrics(
        hrv_rhr_imbalance=hrv_rhr_imbalance,
        recovery_cv=recovery_bl.cv if has_recovery else None,
        has_recovery_data=has_recovery,
        stress_load_short=stress_load_short,
        stress_load_long=stress_load_long,
        stress_trend=stress_trend,
        short_term_window=short_term_window,
        long_term_window=long_term_window,
    )


# ============================================
# SLEEP METRICS
# ============================================


def calculate_sleep_metrics(
    sleep_data: list[DataPoint],
    short_term_window: int = 7,
    long_term_window: int = 30,
    target_minutes: float | None = None,
    ref_date: date | None = None,
) -> SleepMetrics:
    daily_sleep = to_daily_series(sleep_data, "last")
    target_baseline_values = get_window_values(
        daily_sleep, MAX_SLEEP_TARGET_WINDOW, ref_date=ref_date
    )
    personal_target = target_minutes or (
        calculate_median(target_baseline_values) if target_baseline_values else 480
    )

    short_vals = get_window_values(daily_sleep, short_term_window, ref_date=ref_date)
    long_vals = get_window_values(daily_sleep, long_term_window, ref_date=ref_date)

    sleep_debt = sum(max(0, personal_target - s) for s in short_vals)
    sleep_surplus = sum(max(0, s - personal_target) for s in short_vals)

    avg_short = mean_or_none(short_vals)
    avg_long = mean_or_none(long_vals)
    mean_long = avg_long or 0
    std_long = calculate_std(long_vals)
    sleep_cv = std_long / abs(mean_long) if mean_long != 0 else 0

    return SleepMetrics(
        sleep_debt_short=sleep_debt,
        sleep_surplus_short=sleep_surplus,
        sleep_cv=sleep_cv,
        target_sleep=personal_target,
        avg_sleep_short=avg_short,
        avg_sleep_long=avg_long,
        short_term_window=short_term_window,
        long_term_window=long_term_window,
    )


# ============================================
# STEPS METRICS
# ============================================


def calculate_dynamic_steps_floor(
    steps_data: list[DataPoint], window_days: int = 90, ref_date: date | None = None
) -> float:
    daily_steps = to_daily_series(steps_data, "last")
    floor_window = min(window_days, MAX_STEPS_FLOOR_WINDOW)
    floor_values = get_window_values(daily_steps, floor_window, ref_date=ref_date)
    if len(floor_values) < MIN_STEPS_FLOOR_DATA:
        return STEP_FLOOR_FALLBACK
    sorted_vals = sorted(floor_values)
    return round(calculate_percentile(sorted_vals, STEPS_FLOOR_PERCENTILE))


# ============================================
# ACTIVITY METRICS
# ============================================


def calculate_activity_metrics(
    strain_data: list[DataPoint],
    steps_data: list[DataPoint],
    short_term_window: int = 7,
    long_term_window: int = 30,
    trend_window: int = 7,
    ref_date: date | None = None,
) -> ActivityMetrics:
    daily_strain = to_daily_series(strain_data, "max")
    strain_short = get_window_values(daily_strain, short_term_window, ref_date=ref_date)
    strain_long = get_window_values(daily_strain, long_term_window, ref_date=ref_date)
    acute_load = mean_or_none(strain_short)
    chronic_load = mean_or_none(strain_long)
    acwr = (
        acute_load / chronic_load
        if acute_load is not None and chronic_load is not None and chronic_load > 0
        else None
    )

    daily_steps = to_daily_series(steps_data, "last")
    steps_short = get_window_values(daily_steps, short_term_window, ref_date=ref_date)
    steps_long = get_window_values(daily_steps, long_term_window, ref_date=ref_date)
    steps_trend_vals = get_window_values(daily_steps, trend_window, ref_date=ref_date)
    steps_prev_vals = get_window_range_values(
        daily_steps, trend_window * 2, trend_window, ref_date=ref_date
    )

    steps_avg_short = mean_or_none(steps_short)
    steps_avg_long = mean_or_none(steps_long)
    steps_trend_mean = mean_or_none(steps_trend_vals)
    steps_prev_mean = mean_or_none(steps_prev_vals)

    min_data = min(14, max(3, int(trend_window * 0.7)))
    has_valid = (
        steps_trend_mean is not None
        and steps_prev_mean is not None
        and len(steps_trend_vals) >= min_data
        and len(steps_prev_vals) >= min_data
    )
    steps_change = (
        (steps_trend_mean - steps_prev_mean)
        if has_valid and steps_trend_mean is not None and steps_prev_mean is not None
        else None
    )
    steps_mean = steps_avg_long or 0
    steps_std = calculate_std(steps_long)
    steps_cv = steps_std / abs(steps_mean) if steps_mean != 0 else 0

    return ActivityMetrics(
        acute_load=acute_load,
        chronic_load=chronic_load,
        acwr=acwr,
        steps_avg_short=steps_avg_short,
        steps_avg_long=steps_avg_long,
        steps_change=steps_change,
        steps_cv=steps_cv,
        short_term_window=short_term_window,
        long_term_window=long_term_window,
    )


# ============================================
# WEIGHT METRICS
# ============================================


def calculate_weight_metrics(
    weight_data: list[DataPoint],
    short_term_window: int = 7,
    long_term_window: int = 30,
    trend_window: int = 7,
    ref_date: date | None = None,
) -> WeightMetrics:
    daily_weight = to_daily_series(weight_data, "last")
    if not daily_weight:
        return WeightMetrics(
            ema_short=None,
            ema_long=None,
            period_change=None,
            volatility_short=0,
            volatility_long=0,
        )

    all_values = [d.value for d in daily_weight if d.value is not None]
    ema_short = calculate_ema_value(all_values, short_term_window)
    ema_long = calculate_ema_value(all_values, long_term_window)

    short_values = get_window_values(daily_weight, short_term_window, ref_date=ref_date)
    trend_values = get_window_values(daily_weight, trend_window, ref_date=ref_date)
    prev_trend_values = get_window_range_values(
        daily_weight, trend_window * 2, trend_window, ref_date=ref_date
    )
    long_values = get_window_values(daily_weight, long_term_window, ref_date=ref_date)

    mean_trend = mean_or_none(trend_values)
    mean_prev = mean_or_none(prev_trend_values)
    period_change = (
        (mean_trend - mean_prev)
        if mean_trend is not None and mean_prev is not None
        else None
    )

    return WeightMetrics(
        ema_short=ema_short,
        ema_long=ema_long,
        period_change=period_change,
        volatility_short=calculate_std(short_values),
        volatility_long=calculate_std(long_values),
    )


# ============================================
# CALORIES METRICS
# ============================================


def calculate_calories_metrics(
    calories_data: list[DataPoint], ref_date: date | None = None
) -> CaloriesMetrics:
    daily = to_daily_series(calories_data, "last")
    if not daily:
        return CaloriesMetrics(
            avg_7=None, avg_30=None, delta=None, cv_30=0, z_score=None, trend=None
        )

    last7 = get_window_values(daily, 7, ref_date=ref_date)
    last30 = get_window_values(daily, 30, ref_date=ref_date)
    avg7 = mean_or_none(last7)
    avg30 = mean_or_none(last30)
    delta = (avg7 - avg30) if avg7 is not None and avg30 is not None else None
    mean30 = avg30 or 0
    std30 = calculate_std(last30)
    cv30 = std30 / abs(mean30) if mean30 != 0 else 0

    if ref_date is not None:
        ref_str = ref_date.isoformat()
        filtered_daily = [d for d in daily if d.date <= ref_str]
    else:
        filtered_daily = daily
    sorted_daily = sorted(filtered_daily, key=lambda d: d.date)
    current_value = sorted_daily[-1].value if sorted_daily else None
    z_score = (
        (current_value - mean30) / std30
        if current_value is not None and std30 > 0
        else None
    )

    trend = None
    if delta is not None:
        if delta > mean30 * 0.05:
            trend = "increasing"
        elif delta < -mean30 * 0.05:
            trend = "decreasing"
        else:
            trend = "stable"

    return CaloriesMetrics(
        avg_7=avg7, avg_30=avg30, delta=delta, cv_30=cv30, z_score=z_score, trend=trend
    )


# ============================================
# ENERGY BALANCE
# ============================================


def calculate_energy_balance(
    cal: CaloriesMetrics, wt: WeightMetrics
) -> EnergyBalanceMetrics:
    cal_delta = cal.delta
    weight_delta = wt.period_change

    calories_trend = None
    if cal_delta is not None:
        if cal_delta > 100:
            calories_trend = "surplus"
        elif cal_delta < -100:
            calories_trend = "deficit"
        else:
            calories_trend = "maintenance"

    weight_trend = None
    if weight_delta is not None:
        if weight_delta > 0.2:
            weight_trend = "gaining"
        elif weight_delta < -0.2:
            weight_trend = "losing"
        else:
            weight_trend = "stable"

    balance_signal = None
    if calories_trend is not None and weight_trend is not None:
        if (calories_trend == "surplus" and weight_trend == "gaining") or (
            calories_trend == "maintenance" and weight_trend == "gaining"
        ):
            balance_signal = "surplus_confirmed"
        elif (calories_trend == "deficit" and weight_trend == "losing") or (
            calories_trend == "maintenance" and weight_trend == "losing"
        ):
            balance_signal = "deficit_confirmed"
        else:
            balance_signal = "mixed"

    return EnergyBalanceMetrics(
        calories_trend=calories_trend,
        weight_trend=weight_trend,
        balance_signal=balance_signal,
        cal_delta=cal_delta,
        weight_delta=weight_delta,
    )


# ============================================
# HEALTH SCORE
# ============================================

Z_SCORE_CLAMP = 3.0
STRAIN_OPTIMAL_Z = 0.3


def _clamp_z(z: float | None, limit: float = Z_SCORE_CLAMP) -> float | None:
    if z is None:
        return None
    return max(-limit, min(limit, z))


def _strain_goodness(z: float) -> float:
    deviation = abs(z - STRAIN_OPTIMAL_Z)
    if deviation <= 0.5:
        return 0.3 * (1.0 - deviation / 0.5)
    return -(deviation - 0.5)


def _calories_goodness(raw_z: float) -> float:
    if raw_z >= 0:
        return -0.3 * max(0.0, raw_z - 0.5)
    return 0.4 * raw_z


def _weight_goodness(raw_z: float) -> float:
    if raw_z > 0:
        return -0.6 * raw_z
    return -0.3 * raw_z


def _confidence_gate(conf: float, threshold: float = 0.6, width: float = 0.15) -> float:
    x = (conf - threshold) / width
    return 1.0 / (1.0 + math.exp(-5 * x))


def _cap_confidence(conf: float) -> float:
    return max(0.0, min(1.0, conf))


def calculate_health_score(
    hrv_data: list[DataPoint],
    rhr_data: list[DataPoint],
    sleep_data: list[DataPoint],
    stress_data: list[DataPoint],
    steps_data: list[DataPoint],
    strain_data: list[DataPoint],
    hrv_quality: DataQuality | None = None,
    rhr_quality: DataQuality | None = None,
    sleep_quality: DataQuality | None = None,
    stress_quality: DataQuality | None = None,
    steps_quality: DataQuality | None = None,
    strain_quality: DataQuality | None = None,
    fused_inputs: dict[str, FusedZScoreInput] | None = None,
    calories_data: list[DataPoint] | None = None,
    weight_data: list[DataPoint] | None = None,
    baseline_window: int = 30,
    short_term_window: int = 7,
    trend_window: int = 7,
    options: BaselineOptions | None = None,
    use_shifted_z_score: bool = False,
    ref_date: date | None = None,
) -> HealthScore:
    steps_ok, adjusted_steps, steps_reason = should_use_today_metric(
        steps_data, "steps", ref_date=ref_date
    )
    _, adjusted_strain, _ = should_use_today_metric(
        strain_data, "strain", ref_date=ref_date
    )
    _, adjusted_stress, _ = should_use_today_metric(
        stress_data, "stress", ref_date=ref_date
    )
    if calories_data:
        _, adjusted_calories, _ = should_use_today_metric(
            calories_data, "calories", ref_date=ref_date
        )
    else:
        adjusted_calories = []

    bl_hrv = calculate_baseline_metrics(
        hrv_data,
        baseline_window,
        short_term_window,
        "hrv",
        trend_window,
        options,
        ref_date=ref_date,
    )
    bl_rhr = calculate_baseline_metrics(
        rhr_data,
        baseline_window,
        short_term_window,
        "rhr",
        trend_window,
        options,
        ref_date=ref_date,
    )
    bl_sleep = calculate_baseline_metrics(
        sleep_data,
        baseline_window,
        short_term_window,
        "sleep",
        trend_window,
        options,
        ref_date=ref_date,
    )
    bl_stress = calculate_baseline_metrics(
        adjusted_stress,
        baseline_window,
        short_term_window,
        "stress",
        trend_window,
        options,
        ref_date=ref_date,
    )
    bl_steps = calculate_baseline_metrics(
        adjusted_steps,
        baseline_window,
        short_term_window,
        "steps",
        trend_window,
        options,
        ref_date=ref_date,
    )
    bl_strain = calculate_baseline_metrics(
        adjusted_strain,
        baseline_window,
        short_term_window,
        "strain",
        trend_window,
        options,
        ref_date=ref_date,
    )
    bl_calories = (
        calculate_baseline_metrics(
            adjusted_calories,
            baseline_window,
            short_term_window,
            "calories",
            trend_window,
            options,
            ref_date=ref_date,
        )
        if adjusted_calories
        else None
    )
    bl_weight = (
        calculate_baseline_metrics(
            weight_data,
            baseline_window,
            short_term_window,
            "weight",
            trend_window,
            options,
            ref_date=ref_date,
        )
        if weight_data
        else None
    )

    fi = fused_inputs or {}
    hrv_conf = _cap_confidence(
        fi.get(
            "hrv",
            FusedZScoreInput(
                confidence=hrv_quality.confidence if hrv_quality else 1, source="garmin"
            ),
        ).confidence
    )
    rhr_conf = _cap_confidence(
        fi.get(
            "rhr",
            FusedZScoreInput(
                confidence=rhr_quality.confidence if rhr_quality else 1, source="garmin"
            ),
        ).confidence
    )
    sleep_conf = _cap_confidence(
        fi.get(
            "sleep",
            FusedZScoreInput(
                confidence=sleep_quality.confidence if sleep_quality else 1,
                source="garmin",
            ),
        ).confidence
    )
    stress_conf = _cap_confidence(stress_quality.confidence if stress_quality else 1)
    steps_conf = _cap_confidence(steps_quality.confidence if steps_quality else 1)
    strain_conf = _cap_confidence(strain_quality.confidence if strain_quality else 1)
    cal_fi = fi.get("calories")
    calories_conf = _cap_confidence(
        cal_fi.confidence
        if cal_fi
        else (0.7 if bl_calories and bl_calories.z_score is not None else 0)
    )
    weight_conf = _cap_confidence(
        0.8 if bl_weight and bl_weight.z_score is not None else 0
    )

    def select_z(bl: BaselineMetrics) -> float | None:
        return bl.shifted_z_score if use_shifted_z_score else bl.z_score

    raw_z_hrv = _clamp_z(select_z(bl_hrv))
    raw_z_rhr = _clamp_z(select_z(bl_rhr))
    raw_z_sleep = _clamp_z(select_z(bl_sleep))
    raw_z_stress = _clamp_z(select_z(bl_stress))
    raw_z_steps = _clamp_z(select_z(bl_steps))
    raw_z_load = _clamp_z(select_z(bl_strain))
    raw_z_cal = _clamp_z(select_z(bl_calories) if bl_calories else None)
    raw_z_weight = _clamp_z(select_z(bl_weight) if bl_weight else None)

    z_hrv = raw_z_hrv
    z_rhr = -raw_z_rhr if raw_z_rhr is not None else None
    z_sleep = raw_z_sleep
    z_stress = -raw_z_stress if raw_z_stress is not None else None
    z_steps = raw_z_steps
    z_load = _strain_goodness(raw_z_load) if raw_z_load is not None else None
    z_cal = _calories_goodness(raw_z_cal) if raw_z_cal is not None else None
    z_weight = _weight_goodness(raw_z_weight) if raw_z_weight is not None else None

    core_weights = {"hrv": 0.35, "rhr": 0.25, "sleep": 0.25, "stress": 0.15}
    support_weights = {"steps": 0.35, "calories": 0.35, "weight": 0.30}
    total_core_weight = sum(core_weights.values())
    total_support_weight = sum(support_weights.values())
    min_core_metrics = 2

    hrv_gate = _confidence_gate(hrv_conf)
    rhr_gate = _confidence_gate(rhr_conf)
    sleep_gate = _confidence_gate(sleep_conf)
    stress_gate = _confidence_gate(stress_conf)
    steps_gate = _confidence_gate(steps_conf)
    strain_gate = _confidence_gate(strain_conf)
    cal_gate = _confidence_gate(calories_conf)
    weight_gate = _confidence_gate(weight_conf)

    recovery_core: float | None = None
    core_sum = 0.0
    core_weight_sum = 0.0
    core_available = 0
    for z, gate, w_key in [
        (z_hrv, hrv_gate, "hrv"),
        (z_rhr, rhr_gate, "rhr"),
        (z_sleep, sleep_gate, "sleep"),
        (z_stress, stress_gate, "stress"),
    ]:
        if z is not None:
            core_available += 1
            ew = core_weights[w_key] * gate
            core_sum += z * ew
            core_weight_sum += ew
    if core_available >= min_core_metrics and core_weight_sum > 0:
        recovery_core = core_sum / core_weight_sum

    behavior_support: float | None = None
    support_sum = 0.0
    support_weight_sum = 0.0
    for z, gate, w_key in [
        (z_steps, steps_gate, "steps"),
        (z_cal, cal_gate, "calories"),
        (z_weight, weight_gate, "weight"),
    ]:
        if z is not None:
            ew = support_weights[w_key] * gate
            support_sum += z * ew
            support_weight_sum += ew
    if support_weight_sum > 0:
        behavior_support = support_sum / support_weight_sum

    training_load: float | None = None
    if z_load is not None and strain_gate > 0.1:
        training_load = z_load

    overall: float | None = None
    recovery_weight = 0.6
    training_weight = 0.2
    support_weight = 0.2
    if training_load is None:
        recovery_weight = 0.75
        support_weight = 0.25

    scored_parts: list[tuple[float, float]] = []
    if recovery_core is not None:
        scored_parts.append((recovery_core, recovery_weight))
    if training_load is not None:
        scored_parts.append((training_load, training_weight))
    if behavior_support is not None:
        scored_parts.append((behavior_support, support_weight))
    if scored_parts:
        total_w = sum(w for _, w in scored_parts)
        overall = sum(s * w for s, w in scored_parts) / total_w

    total_possible_weight = total_core_weight + total_support_weight
    data_confidence = (
        (core_weight_sum + support_weight_sum) / total_possible_weight
        if total_possible_weight > 0
        else None
    )

    def _gate_reason(conf: float, gate: float) -> str:
        if gate >= 0.5:
            return ""
        return f"Conf {conf * 100:.0f}%, gate {gate:.2f}"

    contributors = [
        HealthScoreContributor(
            name="HRV",
            raw_z_score=raw_z_hrv,
            goodness_z_score=z_hrv,
            weight=core_weights["hrv"],
            contribution=(
                z_hrv * core_weights["hrv"] * hrv_gate if z_hrv is not None else None
            ),
            confidence=hrv_conf,
            gate_factor=hrv_gate,
            gate_reason=_gate_reason(hrv_conf, hrv_gate),
            source=fi["hrv"].source if "hrv" in fi else None,
        ),
        HealthScoreContributor(
            name="Resting HR",
            raw_z_score=raw_z_rhr,
            goodness_z_score=z_rhr,
            weight=core_weights["rhr"],
            contribution=(
                z_rhr * core_weights["rhr"] * rhr_gate if z_rhr is not None else None
            ),
            confidence=rhr_conf,
            gate_factor=rhr_gate,
            gate_reason=_gate_reason(rhr_conf, rhr_gate),
            source=fi["rhr"].source if "rhr" in fi else None,
        ),
        HealthScoreContributor(
            name="Sleep",
            raw_z_score=raw_z_sleep,
            goodness_z_score=z_sleep,
            weight=core_weights["sleep"],
            contribution=(
                z_sleep * core_weights["sleep"] * sleep_gate
                if z_sleep is not None
                else None
            ),
            confidence=sleep_conf,
            gate_factor=sleep_gate,
            gate_reason=_gate_reason(sleep_conf, sleep_gate),
            source=fi["sleep"].source if "sleep" in fi else None,
        ),
        HealthScoreContributor(
            name="Stress",
            raw_z_score=raw_z_stress,
            goodness_z_score=z_stress,
            weight=core_weights["stress"],
            contribution=(
                z_stress * core_weights["stress"] * stress_gate
                if z_stress is not None
                else None
            ),
            confidence=stress_conf,
            gate_factor=stress_gate,
            gate_reason=_gate_reason(stress_conf, stress_gate),
            source="garmin",
        ),
        HealthScoreContributor(
            name="Steps",
            raw_z_score=raw_z_steps,
            goodness_z_score=z_steps,
            weight=support_weights["steps"],
            contribution=(
                z_steps * support_weights["steps"] * steps_gate
                if z_steps is not None
                else None
            ),
            confidence=steps_conf,
            gate_factor=steps_gate,
            gate_reason=(
                _gate_reason(steps_conf, steps_gate)
                if steps_gate < 0.5
                else steps_reason
            ),
            source="garmin",
        ),
        HealthScoreContributor(
            name="Calories",
            raw_z_score=raw_z_cal,
            goodness_z_score=z_cal,
            weight=support_weights["calories"],
            contribution=(
                z_cal * support_weights["calories"] * cal_gate
                if z_cal is not None
                else None
            ),
            confidence=calories_conf,
            gate_factor=cal_gate,
            gate_reason=_gate_reason(calories_conf, cal_gate),
            source=fi["calories"].source if "calories" in fi else None,
        ),
        HealthScoreContributor(
            name="Weight",
            raw_z_score=raw_z_weight,
            goodness_z_score=z_weight,
            weight=support_weights["weight"],
            contribution=(
                z_weight * support_weights["weight"] * weight_gate
                if z_weight is not None
                else None
            ),
            confidence=weight_conf,
            gate_factor=weight_gate,
            gate_reason=_gate_reason(weight_conf, weight_gate),
            source="garmin",
        ),
    ]

    return HealthScore(
        overall=overall,
        recovery_core=recovery_core,
        training_load=training_load,
        behavior_support=behavior_support,
        contributors=contributors,
        steps_status={"use_today": steps_ok, "reason": steps_reason},
        data_confidence=data_confidence,
    )


# ============================================
# DAY-OVER-DAY
# ============================================


def _get_day_over_day_delta(
    data: list[DataPoint], metric_name: str, ref_date: date | None = None
) -> DayOverDayDelta:
    daily = to_daily_series_for_metric(data, metric_name)
    ref_str = (ref_date or local_today()).isoformat()
    sorted_data = sorted(
        [d for d in daily if d.value is not None and d.date <= ref_str],
        key=lambda d: d.date,
        reverse=True,
    )

    if not sorted_data:
        return DayOverDayDelta(
            latest=None,
            previous=None,
            delta=None,
            delta_percent=None,
            latest_date=None,
            previous_date=None,
        )
    if len(sorted_data) == 1:
        return DayOverDayDelta(
            latest=sorted_data[0].value,
            previous=None,
            delta=None,
            delta_percent=None,
            latest_date=sorted_data[0].date,
            previous_date=None,
        )

    t = sorted_data[0].value
    y = sorted_data[1].value
    if t is not None and y is not None:
        delta = t - y
        delta_pct = (delta / y) * 100 if y != 0 else None
    else:
        delta = None
        delta_pct = None

    gap = (to_day_date(sorted_data[0].date) - to_day_date(sorted_data[1].date)).days

    return DayOverDayDelta(
        latest=t,
        previous=y,
        delta=delta,
        delta_percent=delta_pct,
        latest_date=sorted_data[0].date,
        previous_date=sorted_data[1].date,
        gap_days=gap,
    )


def calculate_day_over_day_metrics(
    hrv: list[DataPoint],
    rhr: list[DataPoint],
    sleep: list[DataPoint],
    recovery: list[DataPoint],
    steps: list[DataPoint],
    weight: list[DataPoint],
    strain: list[DataPoint],
    ref_date: date | None = None,
) -> DayOverDayMetrics:
    return DayOverDayMetrics(
        hrv=_get_day_over_day_delta(hrv, "hrv", ref_date),
        rhr=_get_day_over_day_delta(rhr, "rhr", ref_date),
        sleep=_get_day_over_day_delta(sleep, "sleep", ref_date),
        recovery=_get_day_over_day_delta(recovery, "recovery", ref_date),
        steps=_get_day_over_day_delta(steps, "steps", ref_date),
        weight=_get_day_over_day_delta(weight, "weight", ref_date),
        strain=_get_day_over_day_delta(strain, "strain", ref_date),
    )


# ============================================
# LAST N DAYS
# ============================================


def calculate_last_n_days_metrics(
    hrv: list[DataPoint],
    rhr: list[DataPoint],
    sleep: list[DataPoint],
    recovery: list[DataPoint],
    steps: list[DataPoint],
    weight: list[DataPoint],
    strain: list[DataPoint],
    stress: list[DataPoint],
    calories: list[DataPoint],
    days: int = 3,
    ref_date: date | None = None,
) -> list[DayMetrics]:
    ref_str = (ref_date or local_today()).isoformat()
    all_dates: set[str] = set()
    for dataset in [hrv, rhr, sleep, recovery, steps, weight, strain, stress, calories]:
        for d in dataset:
            if d.value is not None and to_day_key(d.date) <= ref_str:
                all_dates.add(to_day_key(d.date))

    sorted_dates = sorted(all_dates, reverse=True)[:days]

    def get_val(data: list[DataPoint], metric: str, target: str) -> float | None:
        daily = to_daily_series_for_metric(data, metric)
        entry = next((d for d in daily if to_day_key(d.date) == target), None)
        return entry.value if entry else None

    return [
        DayMetrics(
            date=d,
            hrv=get_val(hrv, "hrv", d),
            rhr=get_val(rhr, "rhr", d),
            sleep=get_val(sleep, "sleep", d),
            recovery=get_val(recovery, "recovery", d),
            steps=get_val(steps, "steps", d),
            weight=get_val(weight, "weight", d),
            strain=get_val(strain, "strain", d),
            stress=get_val(stress, "stress", d),
            calories=get_val(calories, "calories", d),
        )
        for d in sorted_dates
    ]
