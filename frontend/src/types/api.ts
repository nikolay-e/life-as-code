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
}

export interface WhoopWorkoutData {
  date: string;
  start_time: string | null;
  strain: number | null;
  avg_heart_rate: number | null;
  max_heart_rate: number | null;
  kilojoules: number | null;
  distance_meters: number | null;
  altitude_gain_meters: number | null;
  sport_name: string | null;
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
  ln_rmssd_cv_7d: number | null;
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

export interface AnalyticsResponse {
  advanced_insights?: AdvancedInsights;
  mode: string;
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
}
