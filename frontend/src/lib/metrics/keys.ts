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
] as const;

export type DashboardMetricKey = (typeof DASHBOARD_METRIC_KEYS)[number];
export type TrendsMetricKey = (typeof TRENDS_METRIC_KEYS)[number];
