export const healthKeys = {
  all: ["health"] as const,
  data: () => [...healthKeys.all, "data"] as const,
  dataRange: (start: string, end: string) =>
    [...healthKeys.data(), start, end] as const,
  workouts: () => [...healthKeys.all, "workouts"] as const,
  detailedWorkouts: (start: string, end: string) =>
    [...healthKeys.workouts(), "detailed", start, end] as const,
  garminActivities: (start: string, end: string) =>
    [...healthKeys.all, "garmin", "activities", start, end] as const,
  racePredictions: (start: string, end: string) =>
    [...healthKeys.all, "race-predictions", start, end] as const,
  sync: () => [...healthKeys.all, "sync"] as const,
  syncStatus: () => [...healthKeys.sync(), "status"] as const,
  backoffStatus: () => [...healthKeys.sync(), "backoff"] as const,
  analytics: (mode: string) => [...healthKeys.all, "analytics", mode] as const,
  mlForecasts: (metric?: string, horizon?: number) =>
    [
      ...healthKeys.all,
      "ml",
      "forecasts",
      metric ?? null,
      horizon ?? null,
    ] as const,
};

export const settingsKeys = {
  all: ["settings"] as const,
  thresholds: () => [...settingsKeys.all, "thresholds"] as const,
  credentials: () => [...settingsKeys.all, "credentials"] as const,
  profile: () => [...settingsKeys.all, "profile"] as const,
};

export const longevityKeys = {
  all: ["longevity"] as const,
  interventions: () => [...longevityKeys.all, "interventions"] as const,
  biomarkers: () => [...longevityKeys.all, "biomarkers"] as const,
  functionalTests: () => [...longevityKeys.all, "functional-tests"] as const,
  goals: () => [...longevityKeys.all, "goals"] as const,
};

export const clinicalAlertsKeys = {
  all: ["clinical-alerts"] as const,
  list: (status?: string) =>
    [...clinicalAlertsKeys.all, status ?? "all"] as const,
};
