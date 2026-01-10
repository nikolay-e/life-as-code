import { format } from "date-fns";
import type { HealthData } from "../../types/api";
import {
  toTimeMs,
  toLocalDayKey,
  getLocalDateString,
  toDailySeries,
  calculateMedian,
  filterDataByWindow,
} from "../health";
import {
  calculateDataQuality,
  calculateBaselineMetrics,
  shouldUseTodayMetric,
  calculateHealthScore,
  calculateRecoveryMetrics,
  calculateSleepMetrics,
  calculateActivityMetrics,
  calculateWeightMetrics,
  calculateDayCompleteness,
  type DataQuality,
  type BaselineMetrics,
  type BaselineOptions,
  type HealthScore,
  type RecoveryMetrics,
  type SleepMetrics,
  type ActivityMetrics,
  type WeightMetrics,
  type FusedZScoreInput,
} from "../health-metrics";
import {
  createFusedHealthData,
  getDataSourceSummary,
  type UnifiedMetricPoint,
} from "../data-fusion";
import type {
  MetricDef,
  MetricData,
  MetricCardVM,
  TrendConfig,
  TrendMode,
  TrendModeConfig,
  SeriesResult,
  DisplayValue,
} from "./types";
import { METRIC_REGISTRY, resolveMetric, getMetricByKey } from "./registry";
import { DASHBOARD_METRIC_KEYS } from "./keys";

export const TREND_MODES: Record<TrendMode, TrendModeConfig> = {
  recent: {
    label: "6W",
    rangeDays: 42,
    shortTerm: 7,
    longTerm: 14,
    baseline: 42,
    trendWindow: 7,
    bandwidthShort: 0.17,
    bandwidthLong: 0.33,
    useShiftedZScore: false,
    description: "Daily",
  },
  quarter: {
    label: "6M",
    rangeDays: 180,
    shortTerm: 14,
    longTerm: 30,
    baseline: 90,
    trendWindow: 14,
    bandwidthShort: 0.08,
    bandwidthLong: 0.17,
    useShiftedZScore: true,
    description: "Training",
  },
  year: {
    label: "2Y",
    rangeDays: 730,
    shortTerm: 30,
    longTerm: 90,
    baseline: 180,
    trendWindow: 30,
    bandwidthShort: 0.04,
    bandwidthLong: 0.12,
    useShiftedZScore: true,
    description: "Seasonal",
  },
  all: {
    label: "5Y",
    rangeDays: 1825,
    shortTerm: 90,
    longTerm: 180,
    baseline: 365,
    trendWindow: 60,
    bandwidthShort: 0.05,
    bandwidthLong: 0.1,
    useShiftedZScore: true,
    description: "Lifetime",
  },
};

export const MODE_ORDER: TrendMode[] = ["recent", "quarter", "year", "all"];

export const MAX_BASELINE_DAYS = Math.max(
  ...MODE_ORDER.map((m) => TREND_MODES[m].baseline),
);

function aggregationMethodFromDef(
  def: MetricDef,
): "last" | "mean" | "max" | "sum" {
  return def.aggregation;
}

export function getSeries(
  def: MetricDef,
  data: HealthData | null,
  now: Date = new Date(),
  forceToday: boolean = false,
): SeriesResult {
  const raw = def.selectRaw(data);

  const daily = toDailySeries(raw, aggregationMethodFromDef(def));

  let adjusted = daily;
  if (def.accumulating && !forceToday) {
    const check = shouldUseTodayMetric(daily, def.accumulating, now);
    adjusted = check.adjustedData;
  }

  return { raw, daily, adjusted };
}

export function getDisplayValue(
  def: MetricDef,
  adjustedData: MetricData[],
  isToday: boolean,
  now: Date = new Date(),
  windowDays?: number,
): DisplayValue {
  const today = getLocalDateString(now);
  const validData = adjustedData.filter((d) => d.value !== null);

  if (validData.length === 0) {
    return { value: null, latestDate: null, usedFallback: false };
  }

  if (isToday) {
    const sorted = [...validData].sort(
      (a, b) => toTimeMs(b.date) - toTimeMs(a.date),
    );
    const latestEntry = sorted[0];
    const latestDayKey = toLocalDayKey(latestEntry.date);
    const usedFallback = def.accumulating ? latestDayKey !== today : false;

    return {
      value: latestEntry.value,
      latestDate: usedFallback ? latestEntry.date : null,
      usedFallback,
    };
  }

  const dataForMedian =
    windowDays !== undefined
      ? filterDataByWindow(validData, windowDays)
      : validData;

  const values = dataForMedian
    .filter((d): d is typeof d & { value: number } => d.value !== null)
    .map((d) => d.value);
  return {
    value: calculateMedian(values),
    latestDate: null,
    usedFallback: false,
  };
}

export function generateSubtitle(
  isToday: boolean,
  selectedDays: number,
  usedFallback: boolean,
  latestDate: string | null,
): string {
  if (usedFallback && latestDate) {
    const fallbackDate = new Date(toTimeMs(latestDate));
    return `${format(fallbackDate, "MMM d")} (day incomplete)`;
  }
  return isToday ? "Latest" : `${String(selectedDays)}d median`;
}

export function buildDashboardCards(
  data: HealthData | null,
  selectedDays: number,
  now: Date = new Date(),
): MetricCardVM[] {
  const isToday = selectedDays === 1;

  return DASHBOARD_METRIC_KEYS.map((key) => {
    const def = getMetricByKey(key);
    if (!def) {
      return {
        key,
        title: key,
        value: "—",
        subtitle: "",
        icon: METRIC_REGISTRY[0].icon,
        colorClass: "",
        bgClass: "",
      };
    }

    const { adjusted } = getSeries(def, data, now, isToday);
    const { value, latestDate, usedFallback } = getDisplayValue(
      def,
      adjusted,
      isToday,
      now,
      isToday ? undefined : selectedDays,
    );
    const subtitle = generateSubtitle(
      isToday,
      selectedDays,
      usedFallback,
      latestDate,
    );

    return {
      key,
      title: def.title,
      value: def.format(value),
      subtitle,
      icon: def.icon,
      colorClass: def.iconColorClass,
      bgClass: def.iconBgClass,
    };
  });
}

function normalizeCssVar(v: string): string {
  const trimmed = v.trim();
  if (trimmed.startsWith("--")) {
    return trimmed.split(/[\s,]/)[0];
  }
  if (trimmed.startsWith("var(")) {
    const inner = trimmed.slice(4).replace(/\)$/, "").trim();
    const varName = inner.split(/[\s,]/)[0];
    if (varName.startsWith("--")) return varName;
  }
  throw new Error(`Invalid CSS variable format: "${v}" (expected "--name")`);
}

export function getTrendConfig(def: MetricDef): TrendConfig {
  const normalizedVar = normalizeCssVar(def.colorVar);
  return {
    method: def.trendMethod,
    shortTermWindow: 7,
    longTermWindow: 30,
    longerTermWindow: 90,
    baselineWindow: 14,
    color: `hsl(var(${normalizedVar}))`,
    trendColor: `hsl(var(${normalizedVar}) / 0.6)`,
    longTermTrendColor: `hsl(var(${normalizedVar}) / 0.4)`,
    longerTermTrendColor: `hsl(var(${normalizedVar}) / 0.25)`,
    gradientId: def.gradientId,
    colorVar: normalizedVar,
  };
}

export function getTrendConfigByKey(
  keyOrAlias: string,
): TrendConfig | undefined {
  const def = resolveMetric(keyOrAlias);
  return def ? getTrendConfig(def) : undefined;
}

const trendConfigCache = new Map<string, TrendConfig>();
for (const m of METRIC_REGISTRY) {
  const config = getTrendConfig(m);
  trendConfigCache.set(m.key, config);
  for (const alias of m.aliases ?? []) {
    trendConfigCache.set(alias, config);
  }
}

export const TREND_CONFIGS: Readonly<Record<string, TrendConfig>> =
  Object.freeze(Object.fromEntries(trendConfigCache));

export interface ComputedMetric {
  raw: MetricData[];
  adjusted: MetricData[];
  baseline: BaselineMetrics;
  quality: DataQuality;
}

export function computeMetric(
  def: MetricDef,
  data: HealthData | null,
  baselineWindow: number,
  shortTermWindow: number,
  trendWindow: number,
  options: BaselineOptions,
  now: Date = new Date(),
): ComputedMetric {
  const { raw, adjusted } = getSeries(def, data, now);

  const baseline = calculateBaselineMetrics(
    adjusted,
    baselineWindow,
    shortTermWindow,
    def.metricName,
    trendWindow,
    options,
  );
  const quality = calculateDataQuality(
    adjusted,
    baselineWindow,
    def.metricName,
  );

  return { raw, adjusted, baseline, quality };
}

export function computeAllMetrics(
  data: HealthData | null,
  baselineWindow: number,
  shortTermWindow: number,
  trendWindow: number,
  options: BaselineOptions,
  now: Date = new Date(),
): Record<string, ComputedMetric> {
  const result: Record<string, ComputedMetric> = {};
  for (const def of METRIC_REGISTRY) {
    result[def.key] = computeMetric(
      def,
      data,
      baselineWindow,
      shortTermWindow,
      trendWindow,
      options,
      now,
    );
  }
  return result;
}

export function getBaselineOptions(
  mode: TrendMode,
  modeConfig: TrendModeConfig,
): BaselineOptions {
  return {
    excludeRecentDaysFromBaseline: modeConfig.useShiftedZScore
      ? modeConfig.shortTerm
      : 1,
    regressionUsesRealDays: mode === "year" || mode === "all",
    winsorizeTrend: true,
  };
}

export interface DataSourceSummary {
  metric: string;
  total: number;
  garminOnly: number;
  whoopOnly: number;
  blended: number;
  avgConfidence: number;
}

function unifiedToMetricData(data: UnifiedMetricPoint[]): MetricData[] {
  return data.map((d) => ({
    date: d.date,
    value: d.value,
  }));
}

function getLatestFusedInput(
  data: UnifiedMetricPoint[],
): FusedZScoreInput | undefined {
  if (data.length === 0) return undefined;

  const sorted = [...data].sort((a, b) => toTimeMs(b.date) - toTimeMs(a.date));
  const latest = sorted.find((d) => d.value !== null);
  if (!latest || latest.provider === "hevy") return undefined;

  // IMPORTANT: Do NOT pass zScore from fusion layer - it uses hardcoded 30-day window
  // which doesn't match mode-specific baseline windows (84/252/730 days).
  // HealthScore should always calculate z-score via calculateBaselineMetrics
  // using the correct mode window. We only pass confidence and source for fusion metadata.
  return {
    zScore: null,
    confidence: latest.confidence,
    source: latest.provider,
  };
}

export interface HealthAnalysis {
  healthScore: HealthScore;
  recoveryMetrics: RecoveryMetrics;
  sleepMetrics: SleepMetrics;
  activityMetrics: ActivityMetrics;
  weightMetrics: WeightMetrics;
  dayCompleteness: number;
  dataSourceSummary: DataSourceSummary[];
}

const SCORE_QUALITY_WINDOW = 30;

export function computeHealthAnalysis(
  data: HealthData | null,
  computedMetrics: Record<string, ComputedMetric>,
  modeConfig: TrendModeConfig,
  baselineOptions: BaselineOptions,
  now: Date = new Date(),
): HealthAnalysis {
  const hrvData = computedMetrics.hrv.raw;
  const sleepData = computedMetrics.sleep.raw;
  const rhrData = computedMetrics.rhr.raw;
  const stressData = computedMetrics.stress.raw;
  const stepsData = computedMetrics.steps.raw;
  const strainData = computedMetrics.strain.raw;
  const recoveryData = computedMetrics.recovery.raw;
  const weightData = computedMetrics.weight.raw;
  const caloriesData = computedMetrics.calories.raw;

  const fusedData = data ? createFusedHealthData(data) : null;
  const fusedHrvData = fusedData ? unifiedToMetricData(fusedData.hrv) : hrvData;
  const fusedSleepData = fusedData
    ? unifiedToMetricData(fusedData.sleep)
    : sleepData;
  const fusedRhrData = fusedData
    ? unifiedToMetricData(fusedData.restingHr)
    : rhrData;
  const fusedStrainData = fusedData
    ? unifiedToMetricData(fusedData.strain)
    : strainData;
  const fusedCaloriesData = fusedData
    ? unifiedToMetricData(fusedData.calories)
    : caloriesData;

  const dataSourceSummary = fusedData ? getDataSourceSummary(fusedData) : [];

  const fusedInputs = fusedData
    ? {
        hrv: getLatestFusedInput(fusedData.hrv),
        rhr: getLatestFusedInput(fusedData.restingHr),
        sleep: getLatestFusedInput(fusedData.sleep),
        calories: getLatestFusedInput(fusedData.calories),
      }
    : undefined;

  const scoreHrvQuality = calculateDataQuality(
    fusedHrvData,
    SCORE_QUALITY_WINDOW,
    "hrv",
  );
  const scoreRhrQuality = calculateDataQuality(
    fusedRhrData,
    SCORE_QUALITY_WINDOW,
    "rhr",
  );
  const scoreSleepQuality = calculateDataQuality(
    fusedSleepData,
    SCORE_QUALITY_WINDOW,
    "sleep",
  );
  const scoreStressQuality = calculateDataQuality(
    stressData,
    SCORE_QUALITY_WINDOW,
    "stress",
  );
  const scoreStepsCheck = shouldUseTodayMetric(stepsData, "steps", now);
  const scoreStepsQuality = calculateDataQuality(
    scoreStepsCheck.adjustedData,
    SCORE_QUALITY_WINDOW,
    "steps",
  );
  const scoreStrainCheck = shouldUseTodayMetric(fusedStrainData, "strain", now);
  const scoreStrainQuality = calculateDataQuality(
    scoreStrainCheck.adjustedData,
    SCORE_QUALITY_WINDOW,
    "strain",
  );

  const healthScore = calculateHealthScore(
    fusedHrvData,
    fusedRhrData,
    fusedSleepData,
    stressData,
    stepsData,
    fusedStrainData,
    scoreHrvQuality,
    scoreRhrQuality,
    scoreSleepQuality,
    scoreStressQuality,
    scoreStepsQuality,
    scoreStrainQuality,
    fusedInputs,
    fusedCaloriesData,
    modeConfig.baseline,
    modeConfig.shortTerm,
    modeConfig.trendWindow,
    baselineOptions,
    modeConfig.useShiftedZScore,
  );

  const dayCompleteness = calculateDayCompleteness(now);

  const recoveryMetrics = calculateRecoveryMetrics(
    fusedHrvData,
    fusedRhrData,
    stressData,
    recoveryData,
    modeConfig.shortTerm,
    modeConfig.baseline,
    modeConfig.trendWindow,
  );

  const sleepMetrics = calculateSleepMetrics(
    fusedSleepData,
    modeConfig.shortTerm,
    modeConfig.baseline,
  );
  const activityMetrics = calculateActivityMetrics(
    fusedStrainData,
    stepsData,
    modeConfig.shortTerm,
    modeConfig.baseline,
    modeConfig.trendWindow,
  );
  const weightMetrics = calculateWeightMetrics(
    weightData,
    modeConfig.shortTerm,
    modeConfig.baseline,
    modeConfig.trendWindow,
  );

  return {
    healthScore,
    recoveryMetrics,
    sleepMetrics,
    activityMetrics,
    weightMetrics,
    dayCompleteness,
    dataSourceSummary,
  };
}
