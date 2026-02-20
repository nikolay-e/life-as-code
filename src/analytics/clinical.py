from __future__ import annotations

from datetime import date, timedelta

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


def calculate_clinical_alerts(
    rhr_data: list[DataPoint],
    hrv_data: list[DataPoint],
    weight_data: list[DataPoint],
    strain_data: list[DataPoint],
    steps_data: list[DataPoint] | None = None,
    baseline_window: int = 30,
    ref_date: date | None = None,
) -> ClinicalAlerts:
    rhr_bl = calculate_baseline_metrics(
        rhr_data, baseline_window, 7, "rhr", ref_date=ref_date
    )
    hrv_bl = calculate_baseline_metrics(
        hrv_data, baseline_window, 7, "hrv", ref_date=ref_date
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
    persistent_tachycardia = tachycardia_days >= TACHYCARDIA_MIN_DAYS

    daily_hrv = to_daily_series(hrv_data, "mean")
    recent_hrv_window = sorted(
        [
            d
            for d in filter_by_window(daily_hrv, 7, ref_date=ref_date)
            if d.value is not None
        ],
        key=lambda d: d.date,
    )
    hrv_drop_percent: float | None = None
    acute_hrv_drop = False
    if len(recent_hrv_window) >= 3:
        latest_avg = mean_or_none(
            [d.value for d in recent_hrv_window[-2:] if d.value is not None]
        )
        prior_avg = mean_or_none(
            [d.value for d in recent_hrv_window[:-2] if d.value is not None]
        )
        if latest_avg is not None and prior_avg is not None and prior_avg > 0:
            hrv_drop_percent = (prior_avg - latest_avg) / prior_avg
            acute_hrv_drop = hrv_drop_percent > HRV_DROP_THRESHOLD

    daily_weight = to_daily_series(weight_data, "last")
    last30_weight = sorted(
        [
            d
            for d in filter_by_window(daily_weight, 30, ref_date=ref_date)
            if d.value is not None
        ],
        key=lambda d: d.date,
    )
    weight_loss_percent: float | None = None
    progressive_weight_loss = False
    if len(last30_weight) >= 6:
        early_vals = [d.value for d in last30_weight[:3] if d.value is not None]
        late_vals = [d.value for d in last30_weight[-3:] if d.value is not None]
        earliest_avg = mean_or_none(early_vals)
        latest_avg = mean_or_none(late_vals)
        if earliest_avg is not None and latest_avg is not None and earliest_avg > 0:
            weight_loss_percent = (earliest_avg - latest_avg) / earliest_avg
            progressive_weight_loss = weight_loss_percent > WEIGHT_LOSS_THRESHOLD

    activity = calculate_activity_metrics(
        strain_data, steps_data or [], 7, 28, 7, ref_date=ref_date
    )
    hrv_z = hrv_bl.z_score
    severe_overtraining = False
    overtraining_score: float | None = None
    if activity.acwr is not None and hrv_z is not None:
        acwr_excess = max(0, activity.acwr - 1.0)
        hrv_deficit = max(0, -hrv_z)
        overtraining_score = acwr_excess * hrv_deficit
        severe_overtraining = (
            activity.acwr > ACWR_DANGER_THRESHOLD and hrv_z < HRV_LOW_SIGMA
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
    if hrv_bl.std > MIN_STD_THRESHOLD:
        for d in recent_hrv:
            if d.value is not None:
                z = (d.value - hrv_bl.mean) / hrv_bl.std
                if z < -1:
                    consecutive_low += 1
                else:
                    break

    weights = {"strain": 0.3, "hrv": 0.3, "sleep": 0.25, "rhr": 0.15}
    total_weight = sum(weights.values())
    score: float | None = None
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
    if available >= 2:
        raw_score = weighted_sum / total_weight
        score = min(1.0, raw_score / 3.0)
    else:
        raw_score = None

    risk_level = None
    if score is not None:
        if score < OVERREACHING_THRESHOLDS["low"]:
            risk_level = "low"
        elif score < OVERREACHING_THRESHOLDS["moderate"]:
            risk_level = "moderate"
        elif score < OVERREACHING_THRESHOLDS["high"]:
            risk_level = "high"
        else:
            risk_level = "critical"

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


def detect_anomalies(
    hrv_data: list[DataPoint],
    rhr_data: list[DataPoint],
    sleep_data: list[DataPoint],
    stress_data: list[DataPoint],
    baseline_window: int = 30,
    lookback_days: int = 7,
    ref_date: date | None = None,
) -> AnomalyMetrics:
    anomalies: list[AnomalyResult] = []
    today = ref_date or local_today()

    def check_metric(
        data: list[DataPoint],
        metric_name: str,
        display_name: str,
        invert: bool = False,
        both_directions: bool = True,
    ):
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
            return
        for d in recent:
            if d.value is None:
                continue
            raw_z = (d.value - bl.mean) / bl.std
            directional_z = -raw_z if invert else raw_z
            if not both_directions and directional_z < 0:
                continue
            abs_z = abs(raw_z)
            if abs_z >= ANOMALY_THRESHOLDS["warning"]:
                if abs_z >= ANOMALY_THRESHOLDS["critical"]:
                    severity = "critical"
                elif abs_z >= ANOMALY_THRESHOLDS["alert"]:
                    severity = "alert"
                else:
                    severity = "warning"
                anomalies.append(
                    AnomalyResult(
                        date=d.date,
                        metric=display_name,
                        value=d.value,
                        z_score=raw_z,
                        severity=severity,
                    )
                )

    check_metric(hrv_data, "hrv", "HRV", invert=True)
    check_metric(rhr_data, "rhr", "Resting HR", both_directions=False)
    check_metric(sleep_data, "sleep", "Sleep", invert=True)
    check_metric(stress_data, "stress", "Stress", both_directions=False)

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

    daily_hrv = to_daily_series(hrv_data, "mean")
    daily_rhr = to_daily_series(rhr_data, "mean")
    daily_sleep = to_daily_series(sleep_data, "last")

    recent_hrv = filter_by_window(daily_hrv, lookback_days, ref_date=ref_date)
    recent_rhr = filter_by_window(daily_rhr, lookback_days, ref_date=ref_date)
    recent_sleep = filter_by_window(daily_sleep, lookback_days, ref_date=ref_date)

    hrv_vals = [d.value for d in recent_hrv if d.value is not None]
    rhr_vals = [d.value for d in recent_rhr if d.value is not None]
    sleep_vals = [d.value for d in recent_sleep if d.value is not None]

    hrv_drop: float | None = None
    rhr_rise: float | None = None
    sleep_drop: float | None = None

    if hrv_vals and hrv_bl.std > MIN_STD_THRESHOLD:
        avg_hrv = sum(hrv_vals) / len(hrv_vals)
        hrv_drop = max(0, -(avg_hrv - hrv_bl.mean) / hrv_bl.std)
    if rhr_vals and rhr_bl.std > MIN_STD_THRESHOLD:
        avg_rhr = sum(rhr_vals) / len(rhr_vals)
        rhr_rise = max(0, (avg_rhr - rhr_bl.mean) / rhr_bl.std)
    if sleep_vals and sleep_bl.std > MIN_STD_THRESHOLD:
        avg_sleep = sum(sleep_vals) / len(sleep_vals)
        sleep_drop = max(0, -(avg_sleep - sleep_bl.mean) / sleep_bl.std)

    components = [v for v in [hrv_drop, rhr_rise, sleep_drop] if v is not None]
    combined_deviation = sum(components) if components else None

    hrv_map = {to_day_key(d.date): d.value for d in recent_hrv if d.value is not None}
    rhr_map = {to_day_key(d.date): d.value for d in recent_rhr if d.value is not None}
    all_dates = sorted(set(hrv_map.keys()) | set(rhr_map.keys()), reverse=True)

    consecutive = 0
    for dk in all_dates:
        day_dev = 0.0
        hrv_v = hrv_map.get(dk)
        rhr_v = rhr_map.get(dk)
        if hrv_v is not None and hrv_bl.std > MIN_STD_THRESHOLD:
            day_dev += max(0, -(hrv_v - hrv_bl.mean) / hrv_bl.std)
        if rhr_v is not None and rhr_bl.std > MIN_STD_THRESHOLD:
            day_dev += max(0, (rhr_v - rhr_bl.mean) / rhr_bl.std)
        if day_dev >= ELEVATED_DAY_THRESHOLD:
            consecutive += 1
        else:
            break

    risk_level = None
    if combined_deviation is not None:
        if combined_deviation >= ILLNESS_RISK_THRESHOLDS["high"]:
            risk_level = "high"
        elif combined_deviation >= ILLNESS_RISK_THRESHOLDS["moderate"]:
            risk_level = "moderate"
        else:
            risk_level = "low"

    return IllnessRiskSignal(
        combined_deviation=combined_deviation,
        consecutive_days_elevated=consecutive,
        risk_level=risk_level,
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

    daily_hrv = to_daily_series(hrv_data, "mean")
    daily_strain = to_daily_series(strain_data, "max")
    hrv_map = {to_day_key(d.date): d.value for d in daily_hrv if d.value is not None}
    strain_map = {
        to_day_key(d.date): d.value for d in daily_strain if d.value is not None
    }

    sorted_strain_dates = sorted(strain_map.keys())
    recovery_times: list[float] = []
    efficiencies: list[float] = []
    high_strain_events = 0

    for dk in sorted_strain_dates:
        strain_val = strain_map[dk]
        strain_z = (strain_val - strain_bl.mean) / strain_bl.std
        if strain_z > HIGH_STRAIN_Z_THRESHOLD:
            high_strain_events += 1
            start_date = to_day_date(dk)
            start_hrv = hrv_map.get(dk)
            start_hrv_z = (
                (start_hrv - hrv_bl.mean) / hrv_bl.std
                if start_hrv is not None
                else None
            )

            data_days_seen = 0
            for offset in range(1, RECOVERY_LOOKBACK_DAYS + 1):
                check_date = start_date + timedelta(days=offset)
                check_key = check_date.isoformat()
                check_hrv = hrv_map.get(check_key)
                if check_hrv is None:
                    continue
                data_days_seen += 1
                hrv_z = (check_hrv - hrv_bl.mean) / hrv_bl.std
                if hrv_z >= RECOVERED_Z_THRESHOLD:
                    recovery_times.append(data_days_seen)
                    if start_hrv_z is not None and strain_z != 0:
                        efficiencies.append((hrv_z - start_hrv_z) / strain_z)
                    break

    return RecoveryCapacityMetrics(
        avg_recovery_days=mean_or_none(recovery_times),
        recovery_efficiency=mean_or_none(efficiencies),
        high_strain_events=high_strain_events,
        recovered_events=len(recovery_times),
    )
