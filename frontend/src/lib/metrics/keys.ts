export const DASHBOARD_METRIC_KEYS = [
  "hrv",
  "sleep",
  "weight",
  "steps",
  "calories",
  "rhr",
] as const;

export const TRENDS_METRIC_KEYS = [
  "hrv",
  "rhr",
  "sleep",
  "stress",
  "steps",
  "weight",
  "recovery",
  "strain",
  "calories",
  "dailyStrain",
  "respiratory_rate",
  "sleep_deep",
  "sleep_rem",
  "sleep_score",
  "bed_temp",
  "room_temp",
  "sleep_latency",
  "sleep_fitness",
  "sleep_routine",
  "sleep_quality_es",
  "toss_and_turn",
] as const;

export type DashboardMetricKey = (typeof DASHBOARD_METRIC_KEYS)[number];
export type TrendsMetricKey = (typeof TRENDS_METRIC_KEYS)[number];
