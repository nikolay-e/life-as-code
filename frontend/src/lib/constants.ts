export const STEP_GOAL_DEFAULT = 10000;
export const STEP_FLOOR_FALLBACK = 4000;
export const SYNC_REFETCH_INTERVAL = 30_000;
export const HEALTH_DATA_STALE_TIME = 5 * 60 * 1000;
export const DEFAULT_SYNC_DAYS = 90;

export const LOESS_BANDWIDTH_SHORT = 0.17;
export const LOESS_BANDWIDTH_LONG = 0.33;

export const WHOOP_MAX_STRAIN = 21;
export const DEFAULT_ACTIVITY_NAME = "Workout";

export type PeriodDays = 7 | 30 | 90;

export const PERIOD_OPTIONS: { days: PeriodDays; label: string }[] = [
  { days: 7, label: "7 Days" },
  { days: 30, label: "30 Days" },
  { days: 90, label: "90 Days" },
];
