export type {
  MetricData,
  MetricDef,
  MetricCardVM,
  TrendConfig,
  TrendMethod,
  TrendMode,
  TrendModeConfig,
  ViewMode,
  AccumulatingMetricType,
  MetricAggregation,
  MetricName,
  SeriesResult,
  DisplayValue,
} from "./types";

export {
  METRIC_REGISTRY,
  METRIC_KEYS,
  resolveMetric,
  resolveMetricKey,
  getMetricByKey,
  formatSleepMinutes,
} from "./registry";

export { DASHBOARD_METRIC_KEYS, TRENDS_METRIC_KEYS } from "./keys";

export {
  TREND_MODES,
  MODE_ORDER,
  MAX_BASELINE_DAYS,
  TREND_CONFIGS,
  getSeries,
  getDisplayValue,
  generateSubtitle,
  buildDashboardCards,
  getTrendConfig,
  getTrendConfigByKey,
  computeMetric,
  computeAllMetrics,
  getBaselineOptions,
  computeHealthAnalysis,
  type ComputedMetric,
  type HealthAnalysis,
  type DataSourceSummary,
} from "./service";
