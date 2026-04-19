from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel


class TrendMode(str, Enum):
    RECENT = "recent"
    QUARTER = "quarter"
    YEAR = "year"
    ALL = "all"


class TrendModeConfig(BaseModel):
    range_days: int
    short_term: int
    long_term: int
    baseline: int
    trend_window: int
    use_shifted_z_score: bool


class DataPoint(BaseModel):
    date: str
    value: float | None


class DataQuality(BaseModel):
    coverage: float
    latency_days: int | None
    outlier_rate: float
    missing_streak: int
    total_points: int
    valid_points: int
    confidence: float
    freshness_score: float


class BaselineMetrics(BaseModel):
    mean: float
    std: float
    median: float
    cv: float
    current_value: float | None
    z_score: float | None
    shifted_z_score: float | None
    percent_change: float | None
    trend_slope: float | None
    short_term_mean: float | None
    long_term_mean: float | None
    long_term_percentile: float | None = None


class BaselineOptions(BaseModel):
    exclude_recent_days_from_baseline: int = 0
    regression_uses_real_days: bool = False
    winsorize_trend: bool = False


class RecoveryMetrics(BaseModel):
    hrv_rhr_imbalance: float | None
    recovery_cv: float | None
    has_recovery_data: bool = True
    stress_load_short: float | None
    stress_load_long: float | None
    stress_trend: float | None
    short_term_window: int
    long_term_window: int


class SleepMetrics(BaseModel):
    sleep_debt_short: float
    sleep_surplus_short: float
    sleep_cv: float
    target_sleep: float
    avg_sleep_short: float | None
    avg_sleep_long: float | None
    short_term_window: int
    long_term_window: int


class ActivityMetrics(BaseModel):
    acute_load: float | None
    chronic_load: float | None
    acwr: float | None
    steps_avg_short: float | None
    steps_avg_long: float | None
    steps_change: float | None
    steps_cv: float
    short_term_window: int
    long_term_window: int


class WeightMetrics(BaseModel):
    ema_short: float | None
    ema_long: float | None
    period_change: float | None
    volatility_short: float
    volatility_long: float


class CaloriesMetrics(BaseModel):
    avg_7: float | None
    avg_30: float | None
    delta: float | None
    cv_30: float
    z_score: float | None
    trend: Literal["increasing", "decreasing", "stable"] | None


class EnergyBalanceMetrics(BaseModel):
    calories_trend: Literal["surplus", "deficit", "maintenance"] | None
    weight_trend: Literal["gaining", "losing", "stable"] | None
    balance_signal: Literal["surplus_confirmed", "deficit_confirmed", "mixed"] | None
    cal_delta: float | None
    weight_delta: float | None


DataProvider = Literal["garmin", "whoop", "eight_sleep", "google", "blended"]


class HealthScoreContributor(BaseModel):
    name: str
    raw_z_score: float | None
    goodness_z_score: float | None
    weight: float
    contribution: float | None
    confidence: float
    gate_factor: float = 1.0
    gate_reason: str = ""
    source: DataProvider | None = None
    long_term_percentile: float | None = None

    @property
    def is_gated(self) -> bool:
        return self.gate_factor < 0.1


class HealthScore(BaseModel):
    overall: float | None
    recovery_core: float | None
    training_load: float | None = None
    behavior_support: float | None
    contributors: list[HealthScoreContributor]
    steps_status: dict
    data_confidence: float | None = None


class ClinicalAlerts(BaseModel):
    persistent_tachycardia: bool
    tachycardia_days: int
    acute_hrv_drop: bool
    hrv_drop_percent: float | None
    progressive_weight_loss: bool
    weight_loss_percent: float | None
    severe_overtraining: bool
    overtraining_score: float | None
    any_alert: bool


class OverreachingMetrics(BaseModel):
    score: float | None
    risk_level: Literal["low", "moderate", "high", "critical"] | None
    components: dict
    consecutive_low_recovery_days: int


class CorrelationMetrics(BaseModel):
    hrv_rhr_correlation: float | None
    hrv_rhr_p_value: float | None = None
    sleep_hrv_lag_correlation: float | None
    sleep_hrv_p_value: float | None = None
    strain_recovery_correlation: float | None
    strain_recovery_p_value: float | None = None
    sample_size: int
    sample_size_hrv_rhr: int = 0
    sample_size_sleep_hrv: int = 0
    sample_size_strain_recovery: int = 0
    is_significant: bool = False


class AnomalyResult(BaseModel):
    date: str
    metric: str
    value: float
    z_score: float
    severity: Literal["warning", "alert", "critical"]
    source: DataProvider | None = None


class AnomalyMetrics(BaseModel):
    anomalies: list[AnomalyResult]
    anomaly_count: int
    has_recent_anomaly: bool
    most_severe: AnomalyResult | None


class VelocityMetrics(BaseModel):
    hrv_velocity: float | None
    rhr_velocity: float | None
    weight_velocity: float | None
    sleep_velocity: float | None
    interpretation: dict


class RecoveryCapacityMetrics(BaseModel):
    avg_recovery_days: float | None
    recovery_efficiency: float | None
    high_strain_events: int
    recovered_events: int


class IllnessRiskSignal(BaseModel):
    combined_deviation: float | None
    consecutive_days_elevated: int
    risk_level: Literal["low", "moderate", "high"] | None
    components: dict


class DecorrelationAlert(BaseModel):
    is_decorrelated: bool
    current_correlation: float | None
    baseline_correlation: float | None
    correlation_delta: float | None


class DayOverDayDelta(BaseModel):
    latest: float | None
    previous: float | None
    delta: float | None
    delta_percent: float | None
    latest_date: str | None
    previous_date: str | None
    gap_days: int | None = None


class DayOverDayMetrics(BaseModel):
    hrv: DayOverDayDelta
    rhr: DayOverDayDelta
    sleep: DayOverDayDelta
    recovery: DayOverDayDelta
    steps: DayOverDayDelta
    weight: DayOverDayDelta
    strain: DayOverDayDelta


class DayMetrics(BaseModel):
    date: str
    hrv: float | None = None
    rhr: float | None = None
    sleep: float | None = None
    recovery: float | None = None
    steps: float | None = None
    weight: float | None = None
    strain: float | None = None
    stress: float | None = None
    calories: float | None = None


class MLForecastPoint(BaseModel):
    target_date: str
    horizon_days: int
    p10: float | None
    p50: float | None
    p90: float | None


class MLForecastMetric(BaseModel):
    metric: str
    forecasts: list[MLForecastPoint]


class MLAnomalyRecord(BaseModel):
    date: str
    anomaly_score: float
    contributing_factors: dict | None


class MLInsights(BaseModel):
    forecasts: list[MLForecastMetric]
    historical_forecasts: list[MLForecastMetric]
    ml_anomalies: list[MLAnomalyRecord]
    has_active_forecasts: bool
    has_historical_forecasts: bool
    has_recent_ml_anomalies: bool


class HRVAdvancedMetrics(BaseModel):
    ln_rmssd_current: float | None
    ln_rmssd_mean_7d: float | None
    ln_rmssd_sd_7d: float | None
    hrv_rhr_rolling_r_14d: float | None
    hrv_rhr_rolling_r_60d: float | None
    divergence_rate: float | None


class SleepQualityMetrics(BaseModel):
    deep_sleep_pct: float | None
    rem_sleep_pct: float | None
    efficiency: float | None
    fragmentation_index: float | None
    sleep_hrv_responsiveness: float | None
    sleep_hrv_p_value: float | None
    consistency_score: float | None


class FitnessMetrics(BaseModel):
    days_since_last_workout: int | None
    training_frequency_7d: int
    training_frequency_30d: int
    ctl: float | None
    atl: float | None
    tsb: float | None
    monotony: float | None
    strain_index: float | None
    detraining_score: float | None
    vo2_max_current: float | None
    vo2_max_trend: float | None


class LagCorrelationPair(BaseModel):
    metric_a: str
    metric_b: str
    lag_days: int
    correlation: float | None
    p_value: float | None
    sample_size: int


class LagCorrelationMetrics(BaseModel):
    pairs: list[LagCorrelationPair]
    strongest_positive: LagCorrelationPair | None
    strongest_negative: LagCorrelationPair | None


class HRVResidualMetrics(BaseModel):
    predicted: float | None
    actual: float | None
    actual_date: str | None = None
    residual: float | None
    residual_z: float | None
    r_squared: float | None
    model_features: list[str]


class DayOfWeekProfile(BaseModel):
    day: int
    day_name: str
    mean: float | None
    count: int


class WeekdayWeekendSplit(BaseModel):
    weekday_mean: float | None
    weekend_mean: float | None
    delta: float | None


class CrossDomainMetrics(BaseModel):
    weight_hrv_coupling: float | None
    weight_hrv_p_value: float | None
    weekday_weekend: dict[str, WeekdayWeekendSplit]
    day_of_week_profiles: dict[str, list[DayOfWeekProfile]]
    hrv_residual: HRVResidualMetrics


class AllostaticLoadMetrics(BaseModel):
    composite_score: float | None
    breach_rates: dict[str, float]
    trend: float | None


class RecoveryEnhancedMetrics(BaseModel):
    recovery_debt: float | None
    strain_recovery_mismatch_7d: float | None
    recovery_half_life_days: float | None


class SleepTemperatureCorrelation(BaseModel):
    bed_temp_sleep_score_r: float | None
    bed_temp_deep_pct_r: float | None
    room_temp_sleep_score_r: float | None
    optimal_bed_temp: float | None
    optimal_room_temp: float | None
    sample_size: int


class AdvancedInsights(BaseModel):
    hrv_advanced: HRVAdvancedMetrics
    sleep_quality: SleepQualityMetrics
    fitness: FitnessMetrics
    lag_correlations: LagCorrelationMetrics
    cross_domain: CrossDomainMetrics
    allostatic_load: AllostaticLoadMetrics
    recovery_enhanced: RecoveryEnhancedMetrics
    sleep_temperature: SleepTemperatureCorrelation | None = None


class BiologicalAgeComponent(BaseModel):
    name: str
    estimated_age: float | None
    chronological_age: float
    delta: float | None
    confidence: float
    data_source: str | None = None


class BiologicalAgeMetrics(BaseModel):
    composite_biological_age: float | None
    chronological_age: float
    age_delta: float | None
    components: list[BiologicalAgeComponent]
    pace_of_aging: float | None
    pace_trend: float | None


class TrainingZoneMetrics(BaseModel):
    zone2_minutes_7d: float | None
    zone2_minutes_30d: float | None
    zone2_pct_of_total: float | None
    zone5_minutes_7d: float | None
    zone5_minutes_30d: float | None
    zone5_pct_of_total: float | None
    total_training_minutes_7d: float | None
    total_training_minutes_30d: float | None
    zone2_target_met: bool | None
    zone5_target_met: bool | None


class LongevityScore(BaseModel):
    overall: float | None
    cardiorespiratory: float | None
    recovery_resilience: float | None
    sleep_optimization: float | None
    body_composition: float | None
    activity_consistency: float | None
    trend: float | None


class LongevityInsights(BaseModel):
    biological_age: BiologicalAgeMetrics
    training_zones: TrainingZoneMetrics
    longevity_score: LongevityScore


class UnifiedMetricPoint(BaseModel):
    date: str
    value: float | None
    z_score: float | None
    garmin_value: float | None
    whoop_value: float | None
    eight_sleep_value: float | None = None
    garmin_z_score: float | None
    whoop_z_score: float | None
    eight_sleep_z_score: float | None = None
    provider: DataProvider
    confidence: float


class DataSourceSummary(BaseModel):
    metric: str
    total: int
    garmin_only: int
    whoop_only: int
    eight_sleep_only: int = 0
    blended: int
    avg_confidence: float


class FusedZScoreInput(BaseModel):
    confidence: float
    source: DataProvider


class MetricBaseline(BaseModel):
    key: str
    current_value: float | None
    mean: float | None
    std: float | None
    z_score: float | None
    shifted_z_score: float | None
    trend_slope: float | None
    percentile: float | None
    quality_coverage: float
    quality_confidence: float
    short_term_mean: float | None = None
    cv: float = 0.0
    valid_points: int = 0
    outlier_rate: float = 0.0
    latency_days: int | None = None


class HealthAnalysis(BaseModel):
    health_score: HealthScore
    recovery_metrics: RecoveryMetrics
    sleep_metrics: SleepMetrics
    activity_metrics: ActivityMetrics
    weight_metrics: WeightMetrics
    calories_metrics: CaloriesMetrics
    energy_balance: EnergyBalanceMetrics
    clinical_alerts: ClinicalAlerts
    overreaching: OverreachingMetrics
    illness_risk: IllnessRiskSignal
    decorrelation: DecorrelationAlert
    correlations: CorrelationMetrics
    velocity: VelocityMetrics
    recovery_capacity: RecoveryCapacityMetrics
    anomalies: AnomalyMetrics
    day_over_day: DayOverDayMetrics
    recent_days: list[DayMetrics]
    day_completeness: float
    data_source_summary: list[DataSourceSummary]
    metric_baselines: dict[str, MetricBaseline] = {}
    raw_series: dict[str, list[DataPoint]] = {}
    advanced_insights: AdvancedInsights | None = None
    ml_insights: MLInsights | None = None
    longevity_insights: LongevityInsights | None = None
    mode: TrendMode
    mode_config: TrendModeConfig
