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
  sync: () => [...healthKeys.all, "sync"] as const,
  syncStatus: () => [...healthKeys.sync(), "status"] as const,
  backoffStatus: () => [...healthKeys.sync(), "backoff"] as const,
  analytics: (mode: string) => [...healthKeys.all, "analytics", mode] as const,
};

export const settingsKeys = {
  all: ["settings"] as const,
  thresholds: () => [...settingsKeys.all, "thresholds"] as const,
  credentials: () => [...settingsKeys.all, "credentials"] as const,
};
