export interface SleepData {
  date: string;
  deep_minutes: number | null;
  light_minutes: number | null;
  rem_minutes: number | null;
  awake_minutes: number | null;
  total_sleep_minutes: number | null;
  sleep_score: number | null;
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
}

export interface EnergyData {
  date: string;
  active_energy: number | null;
  basal_energy: number | null;
}

export interface StepsData {
  date: string;
  total_steps: number | null;
  total_distance: number | null;
  step_goal: number | null;
}

export interface WorkoutData {
  date: string;
  total_volume: number;
  total_sets: number;
}

export interface HealthData {
  sleep: SleepData[];
  hrv: HRVData[];
  weight: WeightData[];
  heart_rate: HeartRateData[];
  stress: StressData[];
  energy: EnergyData[];
  steps: StepsData[];
  workouts: WorkoutData[];
}

export interface UserSettings {
  hrv_good_threshold: number;
  hrv_moderate_threshold: number;
  deep_sleep_good_threshold: number;
  deep_sleep_moderate_threshold: number;
  total_sleep_good_threshold: number;
  total_sleep_moderate_threshold: number;
  training_high_volume_threshold: number;
}

export interface UserCredentials {
  garmin_email: string;
  hevy_api_key: string;
}

export interface SyncStatus {
  source: string;
  data_type: string;
  last_sync_date: string | null;
  records_synced: number;
  status: string;
  error_message: string | null;
}
