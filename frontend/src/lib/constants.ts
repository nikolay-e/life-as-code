export const STEP_GOAL_DEFAULT = 10000;
export const STEP_FLOOR_FALLBACK = 4000;
export const SYNC_REFETCH_INTERVAL = 30_000;
export const HEALTH_DATA_STALE_TIME = 5 * 60 * 1000;
export const DEFAULT_SYNC_DAYS = 90;

export const WHOOP_MAX_STRAIN = 21;
export const DEFAULT_ACTIVITY_NAME = "Workout";

export type PeriodDays = 7 | 30 | 90;

export const PERIOD_OPTIONS: { days: PeriodDays; label: string }[] = [
  { days: 7, label: "7 Days" },
  { days: 30, label: "30 Days" },
  { days: 90, label: "90 Days" },
];

export const ACTIVITY_COLORS = {
  strength: "text-blue-500",
  strengthBorder: "border-blue-500/30",
  cardio: "text-orange-500",
  activity: "text-green-500",
} as const;
