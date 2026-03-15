export interface User {
  id: number;
  username: string;
}

export interface AuthResponse {
  user: User;
}

export interface VersionInfo {
  version: string;
  buildDate: string;
  commit: string;
  commitFull: string;
}

export interface HealthData {
  sleep: SleepData[];
  hrv: HRVData[];
  weight: WeightData[];
  heart_rate: HeartRateData[];
  stress: StressData[];
  steps: StepsData[];
  energy: EnergyData[];
  workouts: WorkoutData[];
  whoop_recovery: WhoopRecoveryData[];
  whoop_sleep: WhoopSleepData[];
  whoop_workout: WhoopWorkoutData[];
  whoop_cycle: WhoopCycleData[];
  garmin_training_status: GarminTrainingStatusData[];
  garmin_activity: GarminActivityData[];
  garmin_race_prediction: GarminRacePredictionData[];
}

export interface SleepData {
  date: string;
  deep_minutes: number | null;
  light_minutes: number | null;
  rem_minutes: number | null;
  awake_minutes: number | null;
  total_sleep_minutes: number | null;
  sleep_score: number | null;
  skin_temp_celsius: number | null;
  awake_count: number | null;
  sleep_quality_score: number | null;
  sleep_recovery_score: number | null;
  spo2_avg: number | null;
  spo2_min: number | null;
  respiratory_rate: number | null;
}

export interface HRVData {
  date: string;
  hrv_avg: number | null;
  hrv_status: string | null;
}

export interface WeightData {
  date: string;
  weight_kg: number | null;
  bmi: number | null;
  body_fat_pct: number | null;
  muscle_mass_kg: number | null;
  bone_mass_kg: number | null;
  water_pct: number | null;
}

export interface HeartRateData {
  date: string;
  resting_hr: number | null;
  max_hr: number | null;
  avg_hr: number | null;
  spo2_avg: number | null;
  spo2_min: number | null;
  waking_respiratory_rate: number | null;
  lowest_respiratory_rate: number | null;
  highest_respiratory_rate: number | null;
}

export interface StressData {
  date: string;
  avg_stress: number | null;
  max_stress: number | null;
  stress_level: string | null;
  rest_stress: number | null;
  activity_stress: number | null;
}

export interface StepsData {
  date: string;
  total_steps: number | null;
  total_distance: number | null;
  step_goal: number | null;
}

export interface EnergyData {
  date: string;
  active_energy: number | null;
  basal_energy: number | null;
}

export interface WorkoutData {
  date: string;
  total_volume: number | null;
  total_sets: number | null;
}

export interface WhoopRecoveryData {
  date: string;
  recovery_score: number | null;
  resting_heart_rate: number | null;
  hrv_rmssd: number | null;
  spo2_percentage: number | null;
  skin_temp_celsius: number | null;
  user_calibrating: number | null;
}

export interface WhoopSleepData {
  date: string;
  sleep_performance_percentage: number | null;
  sleep_consistency_percentage: number | null;
  sleep_efficiency_percentage: number | null;
  total_sleep_duration_minutes: number | null;
  deep_sleep_minutes: number | null;
  light_sleep_minutes: number | null;
  rem_sleep_minutes: number | null;
  awake_minutes: number | null;
  respiratory_rate: number | null;
  sleep_need_baseline_minutes: number | null;
  sleep_need_debt_minutes: number | null;
  sleep_need_strain_minutes: number | null;
  sleep_need_nap_minutes: number | null;
  sleep_cycle_count: number | null;
  disturbance_count: number | null;
  no_data_minutes: number | null;
}

export interface WhoopWorkoutData {
  date: string;
  start_time: string | null;
  end_time: string | null;
  strain: number | null;
  avg_heart_rate: number | null;
  max_heart_rate: number | null;
  kilojoules: number | null;
  distance_meters: number | null;
  altitude_gain_meters: number | null;
  sport_name: string | null;
  percent_recorded: number | null;
  altitude_change_meters: number | null;
  zone_zero_millis: number | null;
  zone_one_millis: number | null;
  zone_two_millis: number | null;
  zone_three_millis: number | null;
  zone_four_millis: number | null;
  zone_five_millis: number | null;
}

export interface WhoopCycleData {
  date: string;
  strain: number | null;
  kilojoules: number | null;
  avg_heart_rate: number | null;
  max_heart_rate: number | null;
}

export interface GarminTrainingStatusData {
  date: string;
  vo2_max: number | null;
  vo2_max_precise: number | null;
  fitness_age: number | null;
  training_load_7_day: number | null;
  acute_training_load: number | null;
  training_status: string | null;
  training_status_description: string | null;
  primary_training_effect: number | null;
  anaerobic_training_effect: number | null;
  endurance_score: number | null;
  training_readiness_score: number | null;
  total_kilocalories: number | null;
  active_kilocalories: number | null;
}

export interface UserThresholds {
  hrv_good_threshold: number;
  hrv_moderate_threshold: number;
  deep_sleep_good_threshold: number;
  deep_sleep_moderate_threshold: number;
  total_sleep_good_threshold: number;
  total_sleep_moderate_threshold: number;
  training_high_volume_threshold: number;
}

export interface CredentialsStatus {
  garmin_configured: boolean;
  hevy_configured: boolean;
  whoop_configured: boolean;
  whoop_token_expired: boolean;
  whoop_auth_url?: string;
  message: string;
}

export interface SyncStatus {
  source: string;
  data_type: string;
  last_sync_date: string | null;
  last_sync_timestamp: string | null;
  records_synced: number;
  status: string;
  error_message: string | null;
}

export interface SyncResponse {
  message: string;
  success?: boolean;
}

export interface WorkoutSetDetail {
  set_index: number;
  weight_kg: number | null;
  reps: number | null;
  rpe: number | null;
  set_type: string | null;
}

export interface WorkoutExerciseDetail {
  date: string;
  exercise: string;
  sets: WorkoutSetDetail[];
  total_volume: number;
  total_sets: number;
  avg_rpe: number | null;
}

export interface HRVAdvancedMetrics {
  ln_rmssd_current: number | null;
  ln_rmssd_mean_7d: number | null;
  ln_rmssd_sd_7d: number | null;
  hrv_rhr_rolling_r_14d: number | null;
  hrv_rhr_rolling_r_60d: number | null;
  divergence_rate: number | null;
}

export interface SleepQualityMetrics {
  deep_sleep_pct: number | null;
  rem_sleep_pct: number | null;
  efficiency: number | null;
  fragmentation_index: number | null;
  sleep_hrv_responsiveness: number | null;
  sleep_hrv_p_value: number | null;
  consistency_score: number | null;
}

export interface FitnessMetrics {
  days_since_last_workout: number | null;
  training_frequency_7d: number;
  training_frequency_30d: number;
  ctl: number | null;
  atl: number | null;
  tsb: number | null;
  monotony: number | null;
  strain_index: number | null;
  detraining_score: number | null;
  vo2_max_current: number | null;
  vo2_max_trend: number | null;
}

export interface LagCorrelationPair {
  metric_a: string;
  metric_b: string;
  lag_days: number;
  correlation: number | null;
  p_value: number | null;
  sample_size: number;
}

export interface LagCorrelationMetrics {
  pairs: LagCorrelationPair[];
  strongest_positive: LagCorrelationPair | null;
  strongest_negative: LagCorrelationPair | null;
}

export interface HRVResidualMetrics {
  predicted: number | null;
  actual: number | null;
  actual_date: string | null;
  residual: number | null;
  residual_z: number | null;
  r_squared: number | null;
  model_features: string[];
}

export interface DayOfWeekProfile {
  day: number;
  day_name: string;
  mean: number | null;
  count: number;
}

export interface WeekdayWeekendSplit {
  weekday_mean: number | null;
  weekend_mean: number | null;
  delta: number | null;
}

export interface CrossDomainMetrics {
  weight_hrv_coupling: number | null;
  weight_hrv_p_value: number | null;
  weekday_weekend: Record<string, WeekdayWeekendSplit>;
  day_of_week_profiles: Record<string, DayOfWeekProfile[]>;
  hrv_residual: HRVResidualMetrics;
}

export interface AllostaticLoadMetrics {
  composite_score: number | null;
  breach_rates: Record<string, number>;
  trend: number | null;
}

export interface RecoveryEnhancedMetrics {
  recovery_debt: number | null;
  strain_recovery_mismatch_7d: number | null;
  recovery_half_life_days: number | null;
}

export interface AdvancedInsights {
  hrv_advanced: HRVAdvancedMetrics;
  sleep_quality: SleepQualityMetrics;
  fitness: FitnessMetrics;
  lag_correlations: LagCorrelationMetrics;
  cross_domain: CrossDomainMetrics;
  allostatic_load: AllostaticLoadMetrics;
  recovery_enhanced: RecoveryEnhancedMetrics;
}

export interface DataPoint {
  date: string;
  value: number | null;
}

export interface MetricBaseline {
  key: string;
  current_value: number | null;
  mean: number | null;
  std: number | null;
  z_score: number | null;
  shifted_z_score: number | null;
  trend_slope: number | null;
  percentile: number | null;
  quality_coverage: number;
  quality_confidence: number;
  short_term_mean: number | null;
  cv: number;
  valid_points: number;
  outlier_rate: number;
  latency_days: number | null;
}

export interface HealthScoreContributor {
  name: string;
  raw_z_score: number | null;
  goodness_z_score: number | null;
  weight: number;
  contribution: number | null;
  confidence: number;
  gate_factor: number;
  gate_reason: string;
  source: string | null;
  long_term_percentile: number | null;
  is_gated: boolean;
}

export interface OverreachingMetrics {
  score: number | null;
  risk_level: "low" | "moderate" | "high" | "critical" | null;
  components: Record<string, number | null>;
  consecutive_low_recovery_days: number;
}

export interface CorrelationMetrics {
  hrv_rhr_correlation: number | null;
  hrv_rhr_p_value: number | null;
  sleep_hrv_lag_correlation: number | null;
  sleep_hrv_p_value: number | null;
  strain_recovery_correlation: number | null;
  strain_recovery_p_value: number | null;
  sample_size: number;
  is_significant: boolean;
}

export interface VelocityMetrics {
  hrv_velocity: number | null;
  rhr_velocity: number | null;
  weight_velocity: number | null;
  sleep_velocity: number | null;
  interpretation: Record<string, string>;
}

export interface RecoveryCapacityMetrics {
  avg_recovery_days: number | null;
  recovery_efficiency: number | null;
  high_strain_events: number;
  recovered_events: number;
}

export interface IllnessRiskSignal {
  combined_deviation: number | null;
  consecutive_days_elevated: number;
  risk_level: "low" | "moderate" | "high" | null;
  components: Record<string, number | null>;
}

export interface DecorrelationAlert {
  is_decorrelated: boolean;
  current_correlation: number | null;
  baseline_correlation: number | null;
  correlation_delta: number | null;
}

export interface DayMetrics {
  date: string;
  hrv: number | null;
  rhr: number | null;
  sleep: number | null;
  recovery: number | null;
  steps: number | null;
  weight: number | null;
  strain: number | null;
  stress: number | null;
  calories: number | null;
}

export interface HealthScore {
  overall: number | null;
  recovery_core: number | null;
  training_load: number | null;
  behavior_support: number | null;
  contributors: HealthScoreContributor[];
  steps_status: Record<string, unknown>;
  data_confidence: number | null;
}

export interface RecoveryMetrics {
  hrv_rhr_imbalance: number | null;
  recovery_cv: number | null;
  has_recovery_data: boolean;
  stress_load_short: number | null;
  stress_load_long: number | null;
  stress_trend: number | null;
  short_term_window: number;
  long_term_window: number;
}

export interface SleepMetrics {
  sleep_debt_short: number;
  sleep_surplus_short: number;
  sleep_cv: number;
  target_sleep: number;
  avg_sleep_short: number | null;
  avg_sleep_long: number | null;
  short_term_window: number;
  long_term_window: number;
}

export interface ActivityMetrics {
  acute_load: number | null;
  chronic_load: number | null;
  acwr: number | null;
  steps_avg_short: number | null;
  steps_avg_long: number | null;
  steps_change: number | null;
  steps_cv: number;
  short_term_window: number;
  long_term_window: number;
}

export interface WeightMetrics {
  ema_short: number | null;
  ema_long: number | null;
  period_change: number | null;
  volatility_short: number;
  volatility_long: number;
}

export interface CaloriesMetrics {
  avg_7: number | null;
  avg_30: number | null;
  delta: number | null;
  cv_30: number;
  z_score: number | null;
  trend: "increasing" | "decreasing" | "stable" | null;
}

export interface EnergyBalanceMetrics {
  calories_trend: "surplus" | "deficit" | "maintenance" | null;
  weight_trend: "gaining" | "losing" | "stable" | null;
  balance_signal: "surplus_confirmed" | "deficit_confirmed" | "mixed" | null;
  cal_delta: number | null;
  weight_delta: number | null;
}

export interface ClinicalAlerts {
  persistent_tachycardia: boolean;
  tachycardia_days: number;
  acute_hrv_drop: boolean;
  hrv_drop_percent: number | null;
  progressive_weight_loss: boolean;
  weight_loss_percent: number | null;
  severe_overtraining: boolean;
  overtraining_score: number | null;
  any_alert: boolean;
}

export interface AnomalyResult {
  date: string;
  metric: string;
  value: number;
  z_score: number;
  severity: "warning" | "alert" | "critical";
  source: string | null;
}

export interface AnomalyMetrics {
  anomalies: AnomalyResult[];
  anomaly_count: number;
  has_recent_anomaly: boolean;
  most_severe: AnomalyResult | null;
}

export interface DayOverDayDelta {
  latest: number | null;
  previous: number | null;
  delta: number | null;
  delta_percent: number | null;
  latest_date: string | null;
  previous_date: string | null;
  gap_days: number | null;
}

export interface DayOverDayMetrics {
  hrv: DayOverDayDelta;
  rhr: DayOverDayDelta;
  sleep: DayOverDayDelta;
  recovery: DayOverDayDelta;
  steps: DayOverDayDelta;
  weight: DayOverDayDelta;
  strain: DayOverDayDelta;
}

export interface DataSourceSummary {
  metric: string;
  total: number;
  garmin_only: number;
  whoop_only: number;
  blended: number;
  avg_confidence: number;
}

export interface MLForecastPoint {
  target_date: string;
  horizon_days: number;
  p10: number | null;
  p50: number | null;
  p90: number | null;
}

export interface MLForecastMetric {
  metric: string;
  forecasts: MLForecastPoint[];
}

export interface MLAnomalyRecord {
  date: string;
  anomaly_score: number;
  contributing_factors: Record<string, number> | null;
}

export interface MLInsights {
  forecasts: MLForecastMetric[];
  historical_forecasts: MLForecastMetric[];
  ml_anomalies: MLAnomalyRecord[];
  has_active_forecasts: boolean;
  has_historical_forecasts: boolean;
  has_recent_ml_anomalies: boolean;
}

export interface AnalyticsResponse {
  health_score: HealthScore;
  recovery_metrics: RecoveryMetrics;
  sleep_metrics: SleepMetrics;
  activity_metrics: ActivityMetrics;
  weight_metrics: WeightMetrics;
  calories_metrics: CaloriesMetrics;
  energy_balance: EnergyBalanceMetrics;
  clinical_alerts: ClinicalAlerts;
  overreaching: OverreachingMetrics;
  illness_risk: IllnessRiskSignal;
  decorrelation: DecorrelationAlert;
  correlations: CorrelationMetrics;
  velocity: VelocityMetrics;
  recovery_capacity: RecoveryCapacityMetrics;
  anomalies: AnomalyMetrics;
  day_over_day: DayOverDayMetrics;
  recent_days: DayMetrics[];
  day_completeness: number;
  data_source_summary: DataSourceSummary[];
  metric_baselines: Record<string, MetricBaseline>;
  raw_series: Record<string, DataPoint[]>;
  advanced_insights?: AdvancedInsights;
  ml_insights?: MLInsights;
  mode: string;
  mode_config: {
    range_days: number;
    short_term: number;
    long_term: number;
    baseline: number;
    trend_window: number;
    use_shifted_z_score: boolean;
  };
}

export interface GarminActivityData {
  activity_id: string;
  date: string;
  start_time: string | null;
  activity_type: string | null;
  activity_name: string | null;
  duration_seconds: number | null;
  distance_meters: number | null;
  avg_heart_rate: number | null;
  max_heart_rate: number | null;
  calories: number | null;
  avg_speed_mps: number | null;
  max_speed_mps: number | null;
  elevation_gain_meters: number | null;
  elevation_loss_meters: number | null;
  avg_power_watts: number | null;
  max_power_watts: number | null;
  training_effect_aerobic: number | null;
  training_effect_anaerobic: number | null;
  vo2_max_value: number | null;
  hr_zone_one_seconds: number | null;
  hr_zone_two_seconds: number | null;
  hr_zone_three_seconds: number | null;
  hr_zone_four_seconds: number | null;
  hr_zone_five_seconds: number | null;
}

export interface GarminRacePredictionData {
  date: string;
  prediction_5k_seconds: number | null;
  prediction_10k_seconds: number | null;
  prediction_half_marathon_seconds: number | null;
  prediction_marathon_seconds: number | null;
  vo2_max_value: number | null;
}
