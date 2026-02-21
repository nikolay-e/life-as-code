from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta

from .date_utils import filter_by_window, local_today, to_day_date, to_day_key
from .series import get_window_values, to_daily_series
from .stats import (
    calculate_ema_value,
    calculate_std,
    mean_or_none,
    pearson_correlation_with_pvalue,
)
from .types import (
    AdvancedInsights,
    AllostaticLoadMetrics,
    CrossDomainMetrics,
    DataPoint,
    DayOfWeekProfile,
    FitnessMetrics,
    HRVAdvancedMetrics,
    HRVResidualMetrics,
    LagCorrelationMetrics,
    LagCorrelationPair,
    RecoveryEnhancedMetrics,
    SleepQualityMetrics,
    WeekdayWeekendSplit,
)

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _build_day_map(
    data: list[DataPoint],
    window_days: int,
    method: str = "mean",
    ref_date: date | None = None,
) -> dict[str, float]:
    daily = to_daily_series(data, method)
    filtered = filter_by_window(daily, window_days, ref_date=ref_date)
    return {to_day_key(d.date): d.value for d in filtered if d.value is not None}


def _aligned_pairs(
    map_a: dict[str, float],
    map_b: dict[str, float],
    lag: int = 0,
) -> tuple[list[float], list[float]]:
    xs, ys = [], []
    for dk, va in sorted(map_a.items()):
        target = (to_day_date(dk) + timedelta(days=lag)).isoformat()
        vb = map_b.get(target)
        if vb is not None:
            xs.append(va)
            ys.append(vb)
    return xs, ys


# ============================================
# GROUP 1: HRV ADVANCED
# ============================================


def calculate_hrv_advanced(
    hrv_data: list[DataPoint],
    rhr_data: list[DataPoint],
    short_window: int = 7,
    baseline_window: int = 90,
    ref_date: date | None = None,
) -> HRVAdvancedMetrics:
    hrv_map = _build_day_map(hrv_data, baseline_window, "mean", ref_date)

    ln_values_all = {dk: math.log(v) for dk, v in hrv_map.items() if v > 0}

    today = ref_date or local_today()
    short_start = today - timedelta(days=short_window - 1)
    ln_short = [
        v for dk, v in sorted(ln_values_all.items()) if to_day_date(dk) >= short_start
    ]

    ln_current = ln_short[-1] if ln_short else None
    ln_mean_7d = mean_or_none(ln_short)
    ln_sd_7d = calculate_std(ln_short) if len(ln_short) >= 3 else None

    rhr_map = _build_day_map(rhr_data, baseline_window, "mean", ref_date)

    def _rolling_corr(window: int) -> float | None:
        start = today - timedelta(days=window - 1)
        h_vals, r_vals = [], []
        for dk in sorted(hrv_map.keys()):
            if to_day_date(dk) >= start and dk in rhr_map:
                h_vals.append(hrv_map[dk])
                r_vals.append(rhr_map[dk])
        corr, _ = pearson_correlation_with_pvalue(h_vals, r_vals)
        return corr

    r_14d = _rolling_corr(14)
    r_60d = _rolling_corr(60)

    divergence_rate: float | None = None
    if r_14d is not None and r_60d is not None:
        divergence_rate = r_14d - r_60d

    return HRVAdvancedMetrics(
        ln_rmssd_current=ln_current,
        ln_rmssd_mean_7d=ln_mean_7d,
        ln_rmssd_sd_7d=ln_sd_7d,
        hrv_rhr_rolling_r_14d=r_14d,
        hrv_rhr_rolling_r_60d=r_60d,
        divergence_rate=divergence_rate,
    )


# ============================================
# GROUP 2: SLEEP QUALITY
# ============================================


def calculate_sleep_quality(
    sleep_data: list[DataPoint],
    sleep_deep: list[DataPoint],
    sleep_rem: list[DataPoint],
    sleep_awake_count: list[DataPoint],
    sleep_efficiency: list[DataPoint],
    hrv_data: list[DataPoint],
    baseline_window: int = 90,
    short_window: int = 7,
    ref_date: date | None = None,
) -> SleepQualityMetrics:
    sleep_map = _build_day_map(sleep_data, baseline_window, "last", ref_date)
    deep_map = _build_day_map(sleep_deep, baseline_window, "last", ref_date)
    rem_map = _build_day_map(sleep_rem, baseline_window, "last", ref_date)
    awake_map = _build_day_map(sleep_awake_count, baseline_window, "last", ref_date)
    eff_map = _build_day_map(sleep_efficiency, baseline_window, "last", ref_date)

    today = ref_date or local_today()
    short_start = today - timedelta(days=short_window - 1)

    short_sleep_vals = [
        v for dk, v in sorted(sleep_map.items()) if to_day_date(dk) >= short_start
    ]

    deep_pcts, rem_pcts = [], []
    for dk, total in sorted(sleep_map.items()):
        if total and total > 0 and to_day_date(dk) >= short_start:
            deep_v = deep_map.get(dk)
            rem_v = rem_map.get(dk)
            if deep_v is not None:
                deep_pcts.append(deep_v / total * 100)
            if rem_v is not None:
                rem_pcts.append(rem_v / total * 100)

    deep_pct = mean_or_none(deep_pcts) if deep_pcts else None
    rem_pct = mean_or_none(rem_pcts) if rem_pcts else None

    eff_vals = [
        v for dk, v in sorted(eff_map.items()) if to_day_date(dk) >= short_start
    ]
    efficiency = mean_or_none(eff_vals)

    awake_vals = []
    for dk, total in sorted(sleep_map.items()):
        if to_day_date(dk) >= short_start and total and total > 0:
            ac = awake_map.get(dk)
            if ac is not None:
                hours = total / 60
                awake_vals.append(ac / hours if hours > 0 else 0)
    fragmentation = mean_or_none(awake_vals)

    consistency: float | None = None
    if len(short_sleep_vals) >= 3:
        std_sleep = calculate_std(short_sleep_vals)
        mean_sleep = mean_or_none(short_sleep_vals)
        if mean_sleep and mean_sleep > 0:
            consistency = max(0, min(100, 100 * (1 - std_sleep / mean_sleep)))

    hrv_map_full = _build_day_map(hrv_data, baseline_window + 1, "mean", ref_date)
    sleep_x, hrv_y = [], []
    for dk in sorted(sleep_map.keys()):
        sleep_v = sleep_map[dk]
        next_day = (to_day_date(dk) + timedelta(days=1)).isoformat()
        next_hrv = hrv_map_full.get(next_day)
        if next_hrv is not None:
            sleep_x.append(sleep_v)
            hrv_y.append(next_hrv)
    responsiveness, resp_p = pearson_correlation_with_pvalue(sleep_x, hrv_y)

    return SleepQualityMetrics(
        deep_sleep_pct=deep_pct,
        rem_sleep_pct=rem_pct,
        efficiency=efficiency,
        fragmentation_index=fragmentation,
        sleep_hrv_responsiveness=responsiveness,
        sleep_hrv_p_value=resp_p,
        consistency_score=consistency,
    )


# ============================================
# GROUP 3+4: FITNESS & TRAINING LOAD
# ============================================


def calculate_fitness_metrics(
    workout_dates: list[DataPoint],
    strain_data: list[DataPoint],
    vo2_max_data: list[DataPoint],
    ref_date: date | None = None,
) -> FitnessMetrics:
    today = ref_date or local_today()

    workout_date_set = {
        to_day_key(d.date) for d in workout_dates if d.value is not None
    }

    days_since: int | None = None
    if workout_date_set:
        sorted_dates = sorted(workout_date_set, reverse=True)
        last_workout = to_day_date(sorted_dates[0])
        days_since = (today - last_workout).days

    freq_7d = sum(1 for d in workout_date_set if (today - to_day_date(d)).days < 7)
    freq_30d = sum(1 for d in workout_date_set if (today - to_day_date(d)).days < 30)

    daily_strain = to_daily_series(strain_data, "max")
    strain_by_date: dict[str, float] = {}
    for d in daily_strain:
        if d.value is not None:
            strain_by_date[to_day_key(d.date)] = d.value

    ctl: float | None = None
    atl: float | None = None
    tsb: float | None = None
    monotony: float | None = None

    if strain_by_date:
        sorted_strain_dates = sorted(strain_by_date.keys())
        start_date = to_day_date(sorted_strain_dates[0])
        end_date = today
        daily_loads: list[float] = []
        current = start_date
        while current <= end_date:
            dk = current.isoformat()
            daily_loads.append(strain_by_date.get(dk, 0.0))
            current += timedelta(days=1)

        if len(daily_loads) >= 7:
            atl = calculate_ema_value(daily_loads, 7)
        if len(daily_loads) >= 42:
            ctl = calculate_ema_value(daily_loads, 42)
        if ctl is not None and atl is not None:
            tsb = ctl - atl

        last_7 = daily_loads[-7:] if len(daily_loads) >= 7 else daily_loads
        if last_7:
            load_mean = sum(last_7) / len(last_7)
            load_std = calculate_std(last_7)
            monotony = load_mean / load_std if load_std > 0 else None

    strain_index: float | None = None
    if monotony is not None and atl is not None:
        strain_index = atl * monotony

    detraining_score: float | None = None
    if days_since is not None and days_since > 7:
        decay_factor = 1 - math.exp(-days_since / 21)
        detraining_score = min(1.0, decay_factor)

    vo2_daily = to_daily_series(vo2_max_data, "last")
    vo2_vals = get_window_values(vo2_daily, 30, ref_date=ref_date)
    vo2_current = vo2_vals[-1] if vo2_vals else None

    vo2_trend: float | None = None
    if len(vo2_vals) >= 7:
        n = len(vo2_vals)
        x_mean = (n - 1) / 2
        y_mean = sum(vo2_vals) / n
        num = sum((i - x_mean) * (vo2_vals[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        vo2_trend = num / den * 7 if den > 0 else None

    return FitnessMetrics(
        days_since_last_workout=days_since,
        training_frequency_7d=freq_7d,
        training_frequency_30d=freq_30d,
        ctl=ctl,
        atl=atl,
        tsb=tsb,
        monotony=monotony,
        strain_index=strain_index,
        detraining_score=detraining_score,
        vo2_max_current=vo2_current,
        vo2_max_trend=vo2_trend,
    )


# ============================================
# GROUP 5: CROSS-DOMAIN ANALYTICS
# ============================================


def calculate_lag_correlations(
    metric_maps: dict[str, dict[str, float]],
    max_lag: int = 3,
) -> LagCorrelationMetrics:
    target_pairs = [
        ("sleep", "hrv", "Sleep → HRV"),
        ("strain", "hrv", "Strain → HRV"),
        ("stress", "hrv", "Stress → HRV"),
        ("strain", "recovery", "Strain → Recovery"),
        ("sleep", "rhr", "Sleep → RHR"),
        ("steps", "hrv", "Steps → HRV"),
        ("weight", "hrv", "Weight → HRV"),
    ]

    results: list[LagCorrelationPair] = []
    for metric_a, metric_b, _ in target_pairs:
        map_a = metric_maps.get(metric_a)
        map_b = metric_maps.get(metric_b)
        if not map_a or not map_b:
            continue
        for lag in range(1, max_lag + 1):
            xs, ys = _aligned_pairs(map_a, map_b, lag)
            corr, p_val = pearson_correlation_with_pvalue(xs, ys)
            results.append(
                LagCorrelationPair(
                    metric_a=metric_a,
                    metric_b=metric_b,
                    lag_days=lag,
                    correlation=corr,
                    p_value=p_val,
                    sample_size=len(xs),
                )
            )

    valid = [
        r
        for r in results
        if r.correlation is not None and r.p_value is not None and r.p_value < 0.05
    ]
    strongest_pos = (
        max(valid, key=lambda r: r.correlation or 0.0, default=None) if valid else None
    )
    strongest_neg = (
        min(valid, key=lambda r: r.correlation or 0.0, default=None) if valid else None
    )

    return LagCorrelationMetrics(
        pairs=results,
        strongest_positive=strongest_pos,
        strongest_negative=strongest_neg,
    )


def calculate_hrv_residual(
    metric_maps: dict[str, dict[str, float]],
    ref_date: date | None = None,
) -> HRVResidualMetrics:
    hrv_map = metric_maps.get("hrv", {})
    if len(hrv_map) < 14:
        return HRVResidualMetrics(
            predicted=None,
            actual=None,
            residual=None,
            residual_z=None,
            r_squared=None,
            model_features=[],
        )

    feature_names = ["rhr", "sleep", "strain", "stress", "weight"]
    available_features = [
        f for f in feature_names if f in metric_maps and metric_maps[f]
    ]

    if not available_features:
        return HRVResidualMetrics(
            predicted=None,
            actual=None,
            residual=None,
            residual_z=None,
            r_squared=None,
            model_features=[],
        )

    rows: list[tuple[float, list[float]]] = []
    today = ref_date or local_today()
    today_str = today.isoformat()
    latest_hrv: float | None = None
    latest_features: list[float] | None = None

    for dk in sorted(hrv_map.keys()):
        hrv_v = hrv_map[dk]
        feature_vals = []
        complete = True
        for f in available_features:
            fv = metric_maps[f].get(dk)
            if fv is None:
                complete = False
                break
            feature_vals.append(fv)
        if not complete:
            continue
        rows.append((hrv_v, feature_vals))
        if dk <= today_str:
            latest_hrv = hrv_v
            latest_features = feature_vals

    if len(rows) < 14 or latest_features is None or latest_hrv is None:
        return HRVResidualMetrics(
            predicted=None,
            actual=None,
            residual=None,
            residual_z=None,
            r_squared=None,
            model_features=available_features,
        )

    n = len(rows)
    k = len(available_features)
    y_vals = [r[0] for r in rows]
    y_mean = sum(y_vals) / n

    x_matrix = [[1.0] + r[1] for r in rows]
    kk = k + 1

    xtx = [[0.0] * kk for _ in range(kk)]
    xty = [0.0] * kk
    for i in range(n):
        for j in range(kk):
            xty[j] += x_matrix[i][j] * y_vals[i]
            for m in range(j, kk):
                xtx[j][m] += x_matrix[i][j] * x_matrix[i][m]
    for j in range(kk):
        for m in range(j):
            xtx[j][m] = xtx[m][j]

    aug = [xtx[j][:] + [xty[j]] for j in range(kk)]
    for col in range(kk):
        max_row = max(range(col, kk), key=lambda r: abs(aug[r][col]))
        aug[col], aug[max_row] = aug[max_row], aug[col]
        pivot = aug[col][col]
        if abs(pivot) < 1e-12:
            return HRVResidualMetrics(
                predicted=None,
                actual=None,
                residual=None,
                residual_z=None,
                r_squared=None,
                model_features=available_features,
            )
        for j in range(col, kk + 1):
            aug[col][j] /= pivot
        for row in range(kk):
            if row != col:
                factor = aug[row][col]
                for j in range(col, kk + 1):
                    aug[row][j] -= factor * aug[col][j]
    coeffs = [aug[j][kk] for j in range(kk)]
    intercept = coeffs[0]
    betas = coeffs[1:]

    predictions = [
        intercept + sum(betas[j] * rows[i][1][j] for j in range(k)) for i in range(n)
    ]
    residuals = [y_vals[i] - predictions[i] for i in range(n)]

    ss_res = sum(r**2 for r in residuals)
    ss_tot = sum((y - y_mean) ** 2 for y in y_vals)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else None

    predicted_latest = intercept + sum(betas[j] * latest_features[j] for j in range(k))
    residual = latest_hrv - predicted_latest

    residual_std = calculate_std(residuals) if len(residuals) >= 3 else None
    residual_z = residual / residual_std if residual_std and residual_std > 0 else None

    return HRVResidualMetrics(
        predicted=predicted_latest,
        actual=latest_hrv,
        residual=residual,
        residual_z=residual_z,
        r_squared=r_squared,
        model_features=available_features,
    )


def calculate_weekday_weekend_splits(
    metric_maps: dict[str, dict[str, float]],
) -> dict[str, WeekdayWeekendSplit]:
    result: dict[str, WeekdayWeekendSplit] = {}
    for metric, day_map in metric_maps.items():
        weekday_vals, weekend_vals = [], []
        for dk, val in day_map.items():
            d = to_day_date(dk)
            if d.weekday() < 5:
                weekday_vals.append(val)
            else:
                weekend_vals.append(val)
        wd_mean = mean_or_none(weekday_vals)
        we_mean = mean_or_none(weekend_vals)
        delta = (
            (we_mean - wd_mean) if wd_mean is not None and we_mean is not None else None
        )
        result[metric] = WeekdayWeekendSplit(
            weekday_mean=wd_mean,
            weekend_mean=we_mean,
            delta=delta,
        )
    return result


def calculate_day_of_week_profiles(
    metric_maps: dict[str, dict[str, float]],
) -> dict[str, list[DayOfWeekProfile]]:
    result: dict[str, list[DayOfWeekProfile]] = {}
    for metric, day_map in metric_maps.items():
        by_dow: dict[int, list[float]] = defaultdict(list)
        for dk, val in day_map.items():
            dow = to_day_date(dk).weekday()
            by_dow[dow].append(val)
        profiles = []
        for dow in range(7):
            vals = by_dow.get(dow, [])
            profiles.append(
                DayOfWeekProfile(
                    day=dow,
                    day_name=DAY_NAMES[dow],
                    mean=mean_or_none(vals),
                    count=len(vals),
                )
            )
        result[metric] = profiles
    return result


def calculate_cross_domain(
    metric_maps: dict[str, dict[str, float]],
    ref_date: date | None = None,
) -> CrossDomainMetrics:
    weight_map = metric_maps.get("weight", {})
    hrv_map = metric_maps.get("hrv", {})
    w_vals, h_vals = _aligned_pairs(weight_map, hrv_map)
    coupling, coupling_p = pearson_correlation_with_pvalue(w_vals, h_vals)

    splits = calculate_weekday_weekend_splits(metric_maps)
    profiles = calculate_day_of_week_profiles(metric_maps)
    residual = calculate_hrv_residual(metric_maps, ref_date)

    return CrossDomainMetrics(
        weight_hrv_coupling=coupling,
        weight_hrv_p_value=coupling_p,
        weekday_weekend=splits,
        day_of_week_profiles=profiles,
        hrv_residual=residual,
    )


# ============================================
# GROUP 6: ALLOSTATIC LOAD
# ============================================


def calculate_allostatic_load(
    metric_maps: dict[str, dict[str, float]],
    ref_date: date | None = None,
) -> AllostaticLoadMetrics:
    today = ref_date or local_today()
    target_metrics = ["hrv", "rhr", "sleep", "stress", "weight"]
    available = {
        m: metric_maps[m] for m in target_metrics if m in metric_maps and metric_maps[m]
    }

    if not available:
        return AllostaticLoadMetrics(composite_score=None, breach_rates={}, trend=None)

    metric_stats: dict[str, tuple[float, float]] = {}
    for metric, day_map in available.items():
        sorted_vals = [v for _, v in sorted(day_map.items())]
        if len(sorted_vals) < 14:
            continue
        baseline_end = len(sorted_vals) // 2
        baseline_vals = sorted_vals[:baseline_end]
        metric_stats[metric] = (
            sum(baseline_vals) / len(baseline_vals),
            calculate_std(baseline_vals),
        )

    if not metric_stats:
        return AllostaticLoadMetrics(composite_score=None, breach_rates={}, trend=None)

    breach_rates: dict[str, float] = {}
    daily_breach_counts: dict[str, int] = defaultdict(int)
    daily_metric_counts: dict[str, int] = defaultdict(int)

    for metric, day_map in available.items():
        if metric not in metric_stats:
            continue
        mean_val, std_val = metric_stats[metric]
        if std_val < 1e-6:
            continue
        total = 0
        breaches = 0
        for dk, val in day_map.items():
            total += 1
            z = abs((val - mean_val) / std_val)
            if z > 1.0:
                breaches += 1
                daily_breach_counts[dk] += 1
            daily_metric_counts[dk] += 1
        breach_rates[metric] = breaches / total if total > 0 else 0.0

    all_dates: set[str] = set()
    for day_map in available.values():
        all_dates.update(day_map.keys())

    if not all_dates:
        return AllostaticLoadMetrics(
            composite_score=None, breach_rates=breach_rates, trend=None
        )

    daily_scores: list[tuple[str, float]] = []
    for dk in sorted(all_dates):
        n_measured = daily_metric_counts.get(dk, 0)
        if n_measured > 0:
            score = daily_breach_counts.get(dk, 0) / n_measured * 100
            daily_scores.append((dk, score))

    recent_scores = [s for dk, s in daily_scores if (today - to_day_date(dk)).days < 30]
    composite = mean_or_none(recent_scores)

    trend: float | None = None
    if len(daily_scores) >= 14:
        recent_14 = [s for _, s in daily_scores[-14:]]
        prev_14 = (
            [s for _, s in daily_scores[-28:-14]] if len(daily_scores) >= 28 else []
        )
        recent_mean = mean_or_none(recent_14)
        prev_mean = mean_or_none(prev_14)
        if recent_mean is not None and prev_mean is not None:
            trend = recent_mean - prev_mean

    return AllostaticLoadMetrics(
        composite_score=composite,
        breach_rates=breach_rates,
        trend=trend,
    )


# ============================================
# GROUP 8: RECOVERY ENHANCED
# ============================================


def calculate_recovery_enhanced(
    recovery_data: list[DataPoint],
    strain_data: list[DataPoint],
    short_window: int = 7,
    baseline_window: int = 90,
    ref_date: date | None = None,
) -> RecoveryEnhancedMetrics:
    recovery_daily = to_daily_series(recovery_data, "last")
    rec_vals = get_window_values(recovery_daily, 30, ref_date=ref_date)
    target_recovery = 70.0
    recovery_debt: float | None = None
    if rec_vals:
        recovery_debt = sum(max(0, target_recovery - r) for r in rec_vals)

    strain_map = _build_day_map(strain_data, short_window, "max", ref_date)
    rec_map = _build_day_map(recovery_data, short_window, "last", ref_date)
    mismatch_vals = []
    for dk in sorted(strain_map.keys()):
        next_day = (to_day_date(dk) + timedelta(days=1)).isoformat()
        rec_v = rec_map.get(next_day)
        if rec_v is not None and rec_v > 0:
            mismatch_vals.append(strain_map[dk] / rec_v * 100)
    mismatch = mean_or_none(mismatch_vals)

    half_life: float | None = None
    strain_map_long = _build_day_map(strain_data, baseline_window, "max", ref_date)
    rec_map_long = _build_day_map(recovery_data, baseline_window, "last", ref_date)
    strain_vals_sorted = sorted(strain_map_long.items())
    strain_mean = mean_or_none(list(strain_map_long.values()))
    if strain_mean and strain_mean > 0:
        strain_threshold = strain_mean + calculate_std(list(strain_map_long.values()))
        recovery_times = []
        for dk, sv in strain_vals_sorted:
            if sv >= strain_threshold:
                high_date = to_day_date(dk)
                for offset in range(1, 8):
                    check_date = (high_date + timedelta(days=offset)).isoformat()
                    check_hrv = rec_map_long.get(check_date)
                    if check_hrv is not None and check_hrv >= target_recovery:
                        recovery_times.append(offset)
                        break
        if recovery_times:
            half_life = sum(recovery_times) / len(recovery_times)

    return RecoveryEnhancedMetrics(
        recovery_debt=recovery_debt,
        strain_recovery_mismatch_7d=mismatch,
        recovery_half_life_days=half_life,
    )


# ============================================
# ORCHESTRATOR
# ============================================


def calculate_advanced_insights(
    hrv_data: list[DataPoint],
    rhr_data: list[DataPoint],
    sleep_data: list[DataPoint],
    sleep_deep: list[DataPoint],
    sleep_rem: list[DataPoint],
    sleep_awake_count: list[DataPoint],
    sleep_efficiency: list[DataPoint],
    strain_data: list[DataPoint],
    stress_data: list[DataPoint],
    steps_data: list[DataPoint],
    weight_data: list[DataPoint],
    recovery_data: list[DataPoint],
    workout_dates: list[DataPoint],
    vo2_max_data: list[DataPoint],
    short_window: int = 7,
    baseline_window: int = 90,
    ref_date: date | None = None,
) -> AdvancedInsights:
    hrv_advanced = calculate_hrv_advanced(
        hrv_data,
        rhr_data,
        short_window,
        baseline_window,
        ref_date,
    )

    sleep_quality = calculate_sleep_quality(
        sleep_data,
        sleep_deep,
        sleep_rem,
        sleep_awake_count,
        sleep_efficiency,
        hrv_data,
        baseline_window,
        short_window,
        ref_date,
    )

    fitness = calculate_fitness_metrics(
        workout_dates,
        strain_data,
        vo2_max_data,
        ref_date,
    )

    metric_maps = {
        "hrv": _build_day_map(hrv_data, baseline_window, "mean", ref_date),
        "rhr": _build_day_map(rhr_data, baseline_window, "mean", ref_date),
        "sleep": _build_day_map(sleep_data, baseline_window, "last", ref_date),
        "strain": _build_day_map(strain_data, baseline_window, "max", ref_date),
        "stress": _build_day_map(stress_data, baseline_window, "mean", ref_date),
        "steps": _build_day_map(steps_data, baseline_window, "last", ref_date),
        "weight": _build_day_map(weight_data, baseline_window, "last", ref_date),
        "recovery": _build_day_map(recovery_data, baseline_window, "last", ref_date),
    }

    lag_correlations = calculate_lag_correlations(metric_maps)
    cross_domain = calculate_cross_domain(metric_maps, ref_date)
    allostatic_load = calculate_allostatic_load(metric_maps, ref_date)
    recovery_enhanced = calculate_recovery_enhanced(
        recovery_data,
        strain_data,
        short_window,
        baseline_window,
        ref_date,
    )

    return AdvancedInsights(
        hrv_advanced=hrv_advanced,
        sleep_quality=sleep_quality,
        fitness=fitness,
        lag_correlations=lag_correlations,
        cross_domain=cross_domain,
        allostatic_load=allostatic_load,
        recovery_enhanced=recovery_enhanced,
    )
