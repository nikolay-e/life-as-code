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
  start_time: string;
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
