from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from .advanced import AdvancedInsightsInput, calculate_advanced_insights
from .clinical import (
    calculate_clinical_alerts,
    calculate_decorrelation_alert,
    calculate_illness_risk_signal,
    calculate_overreaching_metrics,
    calculate_recovery_capacity,
    detect_anomalies,
)
from .constants import SCORE_QUALITY_WINDOW, TREND_MODES
from .correlations import calculate_correlation_metrics, calculate_velocity_metrics
from .data_loader import load_ml_insights, load_raw_health_data
from .fusion import (
    create_fused_health_data,
    get_data_source_summary,
    get_latest_fused_input,
)
from .longevity import LongevityInsightsInput, calculate_longevity_insights
from .metric_series import FusedHealthData, FusedMetric, MetricSeries
from .metrics import (
    HealthScoreInput,
    baseline_cache_scope,
    calculate_activity_metrics,
    calculate_baseline_metrics,
    calculate_calories_metrics,
    calculate_data_quality,
    calculate_day_completeness,
    calculate_day_over_day_metrics,
    calculate_energy_balance,
    calculate_health_score,
    calculate_last_n_days_metrics,
    calculate_recovery_metrics,
    calculate_sleep_metrics,
    calculate_weight_metrics,
    should_use_today_metric,
)
from .series import to_daily_series_for_metric
from .types import (
    AnomalyMetrics,
    AnomalyResult,
    BaselineOptions,
    DataPoint,
    FusedZScoreInput,
    HealthAnalysis,
    MetricBaseline,
    TrendMode,
    TrendModeConfig,
)


def _get_chronological_age(
    db: Session, user_id: int, ref_date: date | None = None
) -> float | None:
    from models import UserSettings

    from .date_utils import local_today

    settings = db.query(UserSettings).filter_by(user_id=user_id).first()
    if not settings or not settings.birth_date:
        return None
    anchor = ref_date or local_today()
    birth = settings.birth_date
    delta = anchor - birth
    return float(delta.days / 365.25)


def get_baseline_options(mode: TrendMode, config: TrendModeConfig) -> BaselineOptions:
    return BaselineOptions(
        exclude_recent_days_from_baseline=(
            config.short_term if config.use_shifted_z_score else 1
        ),
        regression_uses_real_days=mode in (TrendMode.YEAR, TrendMode.ALL),
        winsorize_trend=True,
    )


def _compute_metric_baselines(
    metric_data: dict[str, list[DataPoint]],
    baseline_window: int,
    short_term_window: int,
    trend_window: int,
    options: BaselineOptions,
    ref_date: date | None,
) -> dict[str, MetricBaseline]:
    result: dict[str, MetricBaseline] = {}
    for key, data in metric_data.items():
        if not data:
            continue
        baseline = calculate_baseline_metrics(
            data,
            baseline_window=baseline_window,
            short_term_window=short_term_window,
            metric_name=key,
            trend_window=trend_window,
            options=options,
            ref_date=ref_date,
        )
        quality = calculate_data_quality(data, baseline_window, key, ref_date=ref_date)
        result[key] = MetricBaseline(
            key=key,
            current_value=baseline.current_value,
            mean=baseline.mean,
            std=baseline.std,
            z_score=baseline.z_score,
            shifted_z_score=baseline.shifted_z_score,
            trend_slope=baseline.trend_slope,
            percentile=baseline.long_term_percentile,
            quality_coverage=quality.coverage,
            quality_confidence=quality.confidence,
            short_term_mean=baseline.short_term_mean,
            cv=baseline.cv,
            valid_points=quality.valid_points,
            outlier_rate=quality.outlier_rate,
            latency_days=quality.latency_days,
        )
    return result


def _source_points(metric: FusedMetric, source: str) -> list[DataPoint]:
    src = getattr(metric, source, None)
    return src.points if src else []


def _detect_source_anomalies(
    fused: FusedHealthData,
    source: str,
    stress_data: list[DataPoint],
    baseline_window: int,
    ref_date: date | None,
) -> AnomalyMetrics:
    return detect_anomalies(
        _source_points(fused.hrv, source),
        _source_points(fused.resting_hr, source),
        _source_points(fused.sleep, source),
        stress_data if source == "garmin" else [],
        baseline_window,
        ref_date=ref_date,
    )


def _detect_multi_source_anomalies(
    fused: FusedHealthData,
    stress_data: list[DataPoint],
    baseline_window: int,
    ref_date: date | None = None,
) -> AnomalyMetrics:
    from .date_utils import local_today, to_day_date, to_day_key

    today = ref_date or local_today()

    source_results = [
        (
            name,
            _detect_source_anomalies(
                fused, name, stress_data, baseline_window, ref_date
            ),
        )
        for name in ("garmin", "whoop", "eight_sleep")
    ]

    all_anomalies: list[AnomalyResult] = []
    seen: set[tuple[str, str]] = set()
    for source_name, result in source_results:
        for a in result.anomalies:
            key = (a.date, a.metric)
            if key not in seen:
                all_anomalies.append(a.model_copy(update={"source": source_name}))
                seen.add(key)

    severity_order = {"critical": 0, "alert": 1, "warning": 2}
    all_anomalies.sort(
        key=lambda a: (a.date, severity_order.get(a.severity, 3)), reverse=True
    )
    has_recent = any(
        (today - to_day_date(to_day_key(a.date))).days <= 2 for a in all_anomalies
    )
    most_severe = next(
        (a for a in all_anomalies if a.severity == "critical"),
        all_anomalies[0] if all_anomalies else None,
    )

    return AnomalyMetrics(
        anomalies=all_anomalies,
        anomaly_count=len(all_anomalies),
        has_recent_anomaly=has_recent,
        most_severe=most_severe,
    )


def compute_health_analysis(
    db: Session,
    user_id: int,
    mode: TrendMode = TrendMode.RECENT,
    target_date: date | None = None,
) -> HealthAnalysis:
    with baseline_cache_scope():
        return _compute_health_analysis_impl(db, user_id, mode, target_date)


def _compute_health_analysis_impl(
    db: Session,
    user_id: int,
    mode: TrendMode,
    target_date: date | None,
) -> HealthAnalysis:
    config = TREND_MODES[mode]
    options = get_baseline_options(mode, config)

    raw = load_raw_health_data(
        db,
        user_id,
        days_back=config.range_days + config.baseline + 30,
        ref_date=target_date,
    )

    fused = create_fused_health_data(raw, ref_date=target_date)
    data_source_summary = get_data_source_summary(fused)

    # --- Pipeline A: Smoothed (blended MetricSeries for scores/trends) ---
    hrv_series = fused.hrv.blended
    sleep_series = fused.sleep.blended
    rhr_series = fused.resting_hr.blended
    strain_series = fused.strain.blended
    calories_series = fused.calories.blended
    stress_series = MetricSeries(metric="stress", source="garmin", points=raw.stress)
    steps_series = MetricSeries(metric="steps", source="garmin", points=raw.steps)
    recovery_series = MetricSeries(
        metric="recovery", source="whoop", points=raw.recovery
    )
    weight_series = MetricSeries(metric="weight", source="garmin", points=raw.weight)

    hrv_data = hrv_series.points
    sleep_data = sleep_series.points
    rhr_data = rhr_series.points
    strain_data = strain_series.points
    calories_data = calories_series.points
    stress_data = stress_series.points
    steps_data = steps_series.points
    recovery_data = recovery_series.points
    weight_data = weight_series.points

    fused_inputs_raw = {
        "hrv": get_latest_fused_input(fused.hrv.unified),
        "rhr": get_latest_fused_input(fused.resting_hr.unified),
        "sleep": get_latest_fused_input(fused.sleep.unified),
        "calories": get_latest_fused_input(fused.calories.unified),
    }
    fused_inputs: dict[str, FusedZScoreInput] = {
        k: v for k, v in fused_inputs_raw.items() if v is not None
    }

    hrv_q = calculate_data_quality(
        hrv_data, SCORE_QUALITY_WINDOW, "hrv", ref_date=target_date
    )
    rhr_q = calculate_data_quality(
        rhr_data, SCORE_QUALITY_WINDOW, "rhr", ref_date=target_date
    )
    sleep_q = calculate_data_quality(
        sleep_data, SCORE_QUALITY_WINDOW, "sleep", ref_date=target_date
    )

    _, adjusted_hrv, _ = should_use_today_metric(hrv_data, "hrv", ref_date=target_date)
    _, adjusted_rhr, _ = should_use_today_metric(rhr_data, "rhr", ref_date=target_date)
    _, adjusted_sleep, _ = should_use_today_metric(
        sleep_data, "sleep", ref_date=target_date
    )
    _, adjusted_stress, _ = should_use_today_metric(
        stress_data, "stress", ref_date=target_date
    )
    stress_q = calculate_data_quality(
        adjusted_stress, SCORE_QUALITY_WINDOW, "stress", ref_date=target_date
    )
    _, adjusted_steps, _ = should_use_today_metric(
        steps_data, "steps", ref_date=target_date
    )
    steps_q = calculate_data_quality(
        adjusted_steps, SCORE_QUALITY_WINDOW, "steps", ref_date=target_date
    )
    _, adjusted_strain, _ = should_use_today_metric(
        strain_data, "strain", ref_date=target_date
    )
    strain_q = calculate_data_quality(
        adjusted_strain, SCORE_QUALITY_WINDOW, "strain", ref_date=target_date
    )
    _, adjusted_calories, _ = should_use_today_metric(
        calories_data, "calories", ref_date=target_date
    )

    health_score = calculate_health_score(
        HealthScoreInput(
            hrv_data=adjusted_hrv,
            rhr_data=adjusted_rhr,
            sleep_data=adjusted_sleep,
            stress_data=adjusted_stress,
            steps_data=adjusted_steps,
            strain_data=adjusted_strain,
            hrv_quality=hrv_q,
            rhr_quality=rhr_q,
            sleep_quality=sleep_q,
            stress_quality=stress_q,
            steps_quality=steps_q,
            strain_quality=strain_q,
            fused_inputs=fused_inputs,
            calories_data=adjusted_calories,
            weight_data=weight_data,
            baseline_window=config.baseline,
            short_term_window=config.short_term,
            trend_window=config.trend_window,
            options=options,
            use_shifted_z_score=config.use_shifted_z_score,
            ref_date=target_date,
        )
    )

    recovery_metrics = calculate_recovery_metrics(
        hrv_data,
        rhr_data,
        stress_data,
        recovery_data,
        config.short_term,
        config.baseline,
        config.trend_window,
        ref_date=target_date,
    )
    sleep_metrics = calculate_sleep_metrics(
        sleep_data, config.short_term, config.baseline, ref_date=target_date
    )
    activity_metrics = calculate_activity_metrics(
        strain_data,
        steps_data,
        config.short_term,
        config.baseline,
        config.trend_window,
        ref_date=target_date,
    )
    weight_metrics = calculate_weight_metrics(
        weight_data,
        config.short_term,
        config.baseline,
        config.trend_window,
        ref_date=target_date,
    )
    calories_metrics = calculate_calories_metrics(
        calories_data,
        short_term_window=config.short_term,
        baseline_window=config.baseline,
        ref_date=target_date,
    )
    energy_balance = calculate_energy_balance(calories_metrics, weight_metrics)

    correlations = calculate_correlation_metrics(
        hrv_data,
        rhr_data,
        sleep_data,
        strain_data,
        config.baseline,
        ref_date=target_date,
    )
    velocity = calculate_velocity_metrics(
        hrv_data,
        rhr_data,
        weight_data,
        sleep_data,
        config.trend_window,
        ref_date=target_date,
    )

    # --- Pipeline B: Clinical (per-source MetricSeries) ---
    hrv_clinical = fused.hrv.best_source()
    rhr_clinical = fused.resting_hr.best_source()
    sleep_clinical = fused.sleep.best_source()
    strain_clinical = fused.strain.best_source()

    clinical_alerts = calculate_clinical_alerts(
        rhr_clinical.points,
        hrv_clinical.points,
        weight_data,
        strain_clinical.points,
        steps_data,
        config.baseline,
        ref_date=target_date,
    )
    overreaching = calculate_overreaching_metrics(
        hrv_clinical.points,
        rhr_clinical.points,
        sleep_clinical.points,
        strain_clinical.points,
        config.baseline,
        config.short_term,
        ref_date=target_date,
    )
    illness_risk = calculate_illness_risk_signal(
        hrv_clinical.points,
        rhr_clinical.points,
        sleep_clinical.points,
        config.baseline,
        ref_date=target_date,
    )
    decorrelation = calculate_decorrelation_alert(
        hrv_clinical.points, rhr_clinical.points, ref_date=target_date
    )
    recovery_cap = calculate_recovery_capacity(
        hrv_clinical.points,
        strain_clinical.points,
        config.baseline,
        ref_date=target_date,
    )
    anomalies = _detect_multi_source_anomalies(
        fused, stress_data, config.baseline, ref_date=target_date
    )

    day_over_day = calculate_day_over_day_metrics(
        hrv_data,
        rhr_data,
        sleep_data,
        recovery_data,
        steps_data,
        weight_data,
        strain_data,
        ref_date=target_date,
    )
    recent_days = calculate_last_n_days_metrics(
        hrv_data,
        rhr_data,
        sleep_data,
        recovery_data,
        steps_data,
        weight_data,
        strain_data,
        stress_data,
        calories_data,
        days=3,
        ref_date=target_date,
    )

    sleep_deep = (
        fused.sleep_deep.blended.points
        if fused.sleep_deep
        else raw.sleep_deep_garmin or raw.sleep_deep_whoop
    )
    sleep_rem = (
        fused.sleep_rem.blended.points
        if fused.sleep_rem
        else raw.sleep_rem_garmin or raw.sleep_rem_whoop
    )
    sleep_awake = raw.sleep_awake_count_garmin
    sleep_eff = raw.sleep_efficiency_garmin or raw.sleep_efficiency_whoop

    advanced_insights = calculate_advanced_insights(
        AdvancedInsightsInput(
            hrv_data=hrv_data,
            rhr_data=rhr_data,
            sleep_data=sleep_data,
            sleep_deep=sleep_deep,
            sleep_rem=sleep_rem,
            sleep_awake_count=sleep_awake,
            sleep_efficiency=sleep_eff,
            strain_data=strain_data,
            stress_data=stress_data,
            steps_data=steps_data,
            weight_data=weight_data,
            recovery_data=recovery_data,
            workout_dates=raw.workout_dates,
            vo2_max_data=raw.vo2_max,
            bed_temp_data=raw.bed_temp,
            room_temp_data=raw.room_temp,
            sleep_score_data=raw.sleep_score_eight_sleep,
            sleep_latency_data=raw.sleep_latency,
            short_window=config.short_term,
            baseline_window=config.baseline,
            ref_date=target_date,
        )
    )

    ml_insights = load_ml_insights(db, user_id, ref_date=target_date)

    chronological_age = _get_chronological_age(db, user_id, target_date)
    longevity_insights = calculate_longevity_insights(
        LongevityInsightsInput(
            hrv_data=hrv_data,
            rhr_data=rhr_data,
            vo2_max_data=raw.vo2_max,
            fitness_age_data=raw.fitness_age,
            recovery_data=recovery_data,
            sleep_data=sleep_data,
            weight_data=weight_data,
            body_fat_data=raw.body_fat,
            steps_data=steps_data,
            workout_dates=raw.workout_dates,
            zone2_data=raw.zone2_minutes,
            zone5_data=raw.zone5_minutes,
            total_training_data=raw.total_training_minutes,
            chronological_age=chronological_age,
            baseline_window=config.baseline,
            ref_date=target_date,
        )
    )

    respiratory_rate_data = (
        fused.respiratory_rate.blended.points if fused.respiratory_rate else []
    )

    metric_baselines = _compute_metric_baselines(
        {
            "hrv": hrv_data,
            "rhr": rhr_data,
            "sleep": sleep_data,
            "stress": adjusted_stress,
            "steps": adjusted_steps,
            "weight": weight_data,
            "strain": adjusted_strain,
            "calories": adjusted_calories,
            "respiratory_rate": respiratory_rate_data,
            "sleep_deep": sleep_deep,
            "sleep_rem": sleep_rem,
            "sleep_latency": raw.sleep_latency,
            "sleep_fitness": raw.sleep_fitness_score,
            "sleep_routine": raw.sleep_routine_score,
            "sleep_quality_es": raw.sleep_quality_score_es,
            "toss_and_turn": raw.toss_and_turn,
        },
        config.baseline,
        config.short_term,
        config.trend_window,
        options,
        target_date,
    )
    raw_series = {
        "hrv": to_daily_series_for_metric(hrv_data, "hrv"),
        "rhr": to_daily_series_for_metric(rhr_data, "rhr"),
        "sleep": to_daily_series_for_metric(sleep_data, "sleep"),
        "stress": to_daily_series_for_metric(stress_data, "stress"),
        "steps": to_daily_series_for_metric(adjusted_steps, "steps"),
        "weight": to_daily_series_for_metric(weight_data, "weight"),
        "strain": to_daily_series_for_metric(adjusted_strain, "strain"),
        "calories": to_daily_series_for_metric(calories_data, "calories"),
        "recovery": to_daily_series_for_metric(recovery_data, "recovery"),
        "respiratory_rate": to_daily_series_for_metric(
            respiratory_rate_data, "respiratory_rate"
        ),
        "sleep_deep": to_daily_series_for_metric(sleep_deep, "sleep_deep"),
        "sleep_rem": to_daily_series_for_metric(sleep_rem, "sleep_rem"),
        "bed_temp": to_daily_series_for_metric(raw.bed_temp, "bed_temp"),
        "room_temp": to_daily_series_for_metric(raw.room_temp, "room_temp"),
        "sleep_score": to_daily_series_for_metric(
            raw.sleep_score_eight_sleep, "sleep_score"
        ),
        "sleep_latency": to_daily_series_for_metric(raw.sleep_latency, "sleep_latency"),
        "sleep_fitness": to_daily_series_for_metric(
            raw.sleep_fitness_score, "sleep_fitness"
        ),
        "sleep_routine": to_daily_series_for_metric(
            raw.sleep_routine_score, "sleep_routine"
        ),
        "sleep_quality_es": to_daily_series_for_metric(
            raw.sleep_quality_score_es, "sleep_quality_es"
        ),
        "toss_and_turn": to_daily_series_for_metric(raw.toss_and_turn, "toss_and_turn"),
        "sleep_light": to_daily_series_for_metric(
            raw.sleep_light_eight_sleep, "sleep_light"
        ),
    }

    return HealthAnalysis(
        health_score=health_score,
        recovery_metrics=recovery_metrics,
        sleep_metrics=sleep_metrics,
        activity_metrics=activity_metrics,
        weight_metrics=weight_metrics,
        calories_metrics=calories_metrics,
        energy_balance=energy_balance,
        clinical_alerts=clinical_alerts,
        overreaching=overreaching,
        illness_risk=illness_risk,
        decorrelation=decorrelation,
        correlations=correlations,
        velocity=velocity,
        recovery_capacity=recovery_cap,
        anomalies=anomalies,
        day_over_day=day_over_day,
        recent_days=recent_days,
        advanced_insights=advanced_insights,
        longevity_insights=longevity_insights,
        day_completeness=calculate_day_completeness(ref_date=target_date),
        data_source_summary=data_source_summary,
        metric_baselines=metric_baselines,
        raw_series=raw_series,
        ml_insights=ml_insights,
        mode=mode,
        mode_config=config,
    )
