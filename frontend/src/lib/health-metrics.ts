import type { DataProvider } from "./providers";
import {
  getLocalDateString,
  getLocalToday,
  toLocalDayKey,
  toLocalDayDate,
  toTimeMs,
  toDayNumber,
} from "./health/date";
import {
  MIN_SAMPLE_SIZE,
  MIN_STD_THRESHOLD,
  MAD_SCALE_FACTOR,
  sumOrNull,
  meanOrNull,
  calculatePercentile,
  winsorize,
  calculateMedian,
  calculateMAD,
  calculateRobustStats,
  calculateStd,
  calculateEMAValue,
} from "./health/stats";
import {
  filterDataByWindow,
  filterDataByWindowRange,
  getDatesInWindow,
} from "./health/windows";
import {
  toDailySeries,
  toDailySeriesForMetric,
  getWindowValues,
  getWindowRangeValues,
  type MetricName,
} from "./health/series";

export { type MetricName } from "./health/series";
export {
  formatZScore,
  getZScoreColor,
  getHealthScoreLabel,
  getHealthScoreColor,
} from "./health/format";

interface DataPoint {
  date: string;
  value: number | null;
}

// ============================================
// 1) DATA QUALITY METRICS
// ============================================

export interface DataQuality {
  coverage: number;
  latencyDays: number | null;
  outlierRate: number;
  missingStreak: number;
  totalPoints: number;
  validPoints: number;
  confidence: number;
  freshnessScore: number;
}

export function calculateDataQuality(
  data: DataPoint[],
  windowDays: number,
  metricName: MetricName = "hrv",
): DataQuality {
  const today = getLocalToday();
  const datesInWindow = getDatesInWindow(windowDays);

  const daily = toDailySeriesForMetric(data, metricName);
  const dataInWindow = filterDataByWindow(daily, windowDays);
  const validDataInWindow = dataInWindow.filter((d) => d.value !== null);
  const datesWithData = new Set(
    validDataInWindow.map((d) => toLocalDayKey(d.date)),
  );

  let daysWithData = 0;
  datesInWindow.forEach((date) => {
    if (datesWithData.has(date)) daysWithData++;
  });

  const actualWindowSize = datesInWindow.size;
  const coverage = actualWindowSize > 0 ? daysWithData / actualWindowSize : 0;

  let latencyDays: number | null = null;
  if (validDataInWindow.length > 0) {
    const sortedDates = validDataInWindow
      .map((d) => toLocalDayDate(toLocalDayKey(d.date)))
      .sort((a, b) => b.getTime() - a.getTime());
    const lastDate = sortedDates[0];
    latencyDays = Math.floor(
      (today.getTime() - lastDate.getTime()) / (1000 * 60 * 60 * 24),
    );
  }

  const valuesInWindow = validDataInWindow
    .filter((d): d is typeof d & { value: number } => d.value !== null)
    .map((d) => d.value);
  const outlierRate = calculateOutlierRate(valuesInWindow);

  const missingStreak = calculateMissingStreak(datesInWindow, datesWithData);

  const freshnessScore = calculateFreshnessScore(latencyDays);
  const outlierPenalty = 1 - outlierRate;

  // Balanced approach: coverage matters, but having enough data points also matters
  // - coverage: what % of the window has data (penalizes sparse data)
  // - dataSufficiency: do we have enough absolute points for statistics (min 14)
  const MIN_POINTS_FOR_STATS = 14; // 2 weeks minimum for meaningful statistics
  const dataSufficiency = Math.min(1, daysWithData / MIN_POINTS_FOR_STATS);

  // Weighted combination: coverage is primary (70%), sufficiency is secondary (30%)
  // This way: low coverage = low confidence, even with many absolute points
  const effectiveCoverage = 0.7 * coverage + 0.3 * dataSufficiency;

  const rawConfidence = effectiveCoverage * outlierPenalty * freshnessScore;
  const confidence = Math.min(1, rawConfidence);

  return {
    coverage,
    latencyDays,
    outlierRate,
    missingStreak,
    totalPoints: actualWindowSize,
    validPoints: daysWithData,
    confidence,
    freshnessScore,
  };
}

function calculateFreshnessScore(
  latencyDays: number | null,
  tau: number = 5,
): number {
  if (latencyDays === null) return 0;
  return Math.exp(-latencyDays / tau);
}

export function calculateDayCompleteness(now: Date = new Date()): number {
  const hoursElapsed = now.getHours() + now.getMinutes() / 60;
  const completeCutoff = 20;
  if (hoursElapsed >= completeCutoff) return 1;
  const wakingHours = 16;
  return Math.min(1, hoursElapsed / wakingHours);
}

export type AccumulatingMetricType = "steps" | "calories" | "strain" | "stress";

const METRIC_COMPLETENESS_THRESHOLDS: Record<AccumulatingMetricType, number> = {
  steps: 0.8,
  calories: 0.85,
  strain: 0.85,
  stress: 0.9,
};

export function shouldUseTodayMetric(
  data: DataPoint[],
  metricType: AccumulatingMetricType,
  now: Date = new Date(),
): { useToday: boolean; adjustedData: DataPoint[]; reason: string } {
  const today = getLocalDateString(now);
  const completeness = calculateDayCompleteness(now);
  const threshold = METRIC_COMPLETENESS_THRESHOLDS[metricType];

  const todayEntry = data.find((d) => toLocalDayKey(d.date) === today);
  const hasToday = todayEntry !== undefined && todayEntry.value !== null;

  if (!hasToday) {
    return {
      useToday: false,
      adjustedData: data,
      reason: `No today ${metricType} data`,
    };
  }

  if (completeness >= threshold) {
    return {
      useToday: true,
      adjustedData: data,
      reason: `Day ${String(Math.round(completeness * 100))}% complete`,
    };
  }

  const filteredData = data.filter((d) => toLocalDayKey(d.date) !== today);

  return {
    useToday: false,
    adjustedData: filteredData,
    reason: `Day ${String(Math.round(completeness * 100))}% complete - using yesterday for ${metricType}`,
  };
}

function calculateOutlierRate(values: number[]): number {
  if (values.length < 4) return 0;

  const median = calculateMedian(values);
  const mad = calculateMAD(values);
  const scaledMAD = MAD_SCALE_FACTOR * mad;

  if (scaledMAD < MIN_STD_THRESHOLD) {
    // Use proper percentile calculation for smoother, less sample-size-sensitive results
    const sorted = [...values].sort((a, b) => a - b);
    const q1 = calculatePercentile(sorted, 25);
    const q3 = calculatePercentile(sorted, 75);
    const iqr = q3 - q1;
    const lowerBound = q1 - 1.5 * iqr;
    const upperBound = q3 + 1.5 * iqr;
    const outliers = values.filter((v) => v < lowerBound || v > upperBound);
    return values.length > 0 ? outliers.length / values.length : 0;
  }

  const outliers = values.filter((v) => {
    const robustZ = Math.abs((v - median) / scaledMAD);
    return robustZ > 3;
  });
  return outliers.length / values.length;
}

function calculateMissingStreak(
  datesInWindow: Set<string>,
  datesWithData: Set<string>,
): number {
  const sortedDates = Array.from(datesInWindow).sort();
  let maxStreak = 0;
  let currentStreak = 0;

  for (const date of sortedDates) {
    if (!datesWithData.has(date)) {
      currentStreak++;
      maxStreak = Math.max(maxStreak, currentStreak);
    } else {
      currentStreak = 0;
    }
  }

  return maxStreak;
}

// ============================================
// 2) BASELINE & DEVIATION METRICS
// ============================================

export interface BaselineMetrics {
  mean: number;
  std: number;
  median: number;
  cv: number;
  currentValue: number | null;
  zScore: number | null;
  shiftedZScore: number | null;
  percentChange: number | null;
  trendSlope: number | null;
  shortTermMean: number | null;
  longTermMean: number | null;
}

export interface BaselineOptions {
  excludeRecentDaysFromBaseline?: number;
  regressionUsesRealDays?: boolean;
  winsorizeTrend?: boolean;
}

export function calculateBaselineMetrics(
  data: DataPoint[],
  baselineWindow: number = 30,
  shortTermWindow: number = 7,
  metricName: MetricName = "hrv",
  trendWindow: number = 7,
  options?: BaselineOptions,
): BaselineMetrics {
  const daily = toDailySeriesForMetric(data, metricName);

  // FIX 1: Exclude recent days from baseline to prevent leakage
  // For shiftedZScore, we compare shortTermWindow avg vs baseline WITHOUT those days
  const excludeDays = Math.max(0, options?.excludeRecentDaysFromBaseline ?? 0);

  const baselineSlice =
    excludeDays > 0
      ? filterDataByWindowRange(
          daily,
          baselineWindow + excludeDays,
          excludeDays,
        )
      : filterDataByWindow(daily, baselineWindow);

  const baselineData = baselineSlice.filter((d) => d.value !== null);
  const shortTermData = filterDataByWindow(daily, shortTermWindow).filter(
    (d) => d.value !== null,
  );

  // FIX 2: currentValue should ALWAYS be the latest valid value from daily
  // Not from baselineData (which may exclude recent days)
  const sortedDaily = [...daily]
    .filter((d) => d.value !== null)
    .sort((a, b) => toTimeMs(a.date) - toTimeMs(b.date));
  const currentValue =
    sortedDaily.length > 0 ? sortedDaily[sortedDaily.length - 1].value : null;

  if (baselineData.length === 0) {
    return {
      mean: 0,
      std: 0,
      median: 0,
      cv: 0,
      currentValue,
      zScore: null,
      shiftedZScore: null,
      percentChange: null,
      trendSlope: null,
      shortTermMean: null,
      longTermMean: null,
    };
  }

  const rawValues = baselineData
    .filter((d): d is typeof d & { value: number } => d.value !== null)
    .map((d) => d.value);
  const baselineValues = winsorize(rawValues, 5, 95);

  const stats = calculateRobustStats(baselineValues);
  const mean = stats.mean;
  const std = stats.std;
  const median = stats.median;
  const cv = mean !== 0 ? std / Math.abs(mean) : 0;

  const adaptiveMinSamples = Math.min(
    MIN_SAMPLE_SIZE,
    Math.max(3, Math.floor(baselineWindow * 0.5)),
  );
  const hasSufficientData = baselineValues.length >= adaptiveMinSamples;
  const hasValidStd = std >= MIN_STD_THRESHOLD;

  let zScore: number | null = null;
  if (currentValue !== null && hasSufficientData && hasValidStd) {
    zScore = (currentValue - mean) / std;
  }

  const percentChange =
    currentValue !== null && mean !== 0
      ? ((currentValue - mean) / Math.abs(mean)) * 100
      : null;

  const shortTermValues = shortTermData
    .filter((d): d is typeof d & { value: number } => d.value !== null)
    .map((d) => d.value);
  const shortTermMean = meanOrNull(shortTermValues);

  // Shifted Z-Score: compare shortTermMean vs baseline mean
  // This shows lifestyle shifts rather than day-to-day volatility
  let shiftedZScore: number | null = null;
  if (shortTermMean !== null && hasSufficientData && hasValidStd) {
    shiftedZScore = (shortTermMean - mean) / std;
  }

  // Trend calculation
  const trendData = filterDataByWindow(daily, trendWindow).filter(
    (d) => d.value !== null,
  );
  const prevTrendData = filterDataByWindowRange(
    daily,
    trendWindow * 2,
    trendWindow,
  ).filter((d) => d.value !== null);

  const rawTrendValues = trendData
    .filter((d): d is typeof d & { value: number } => d.value !== null)
    .map((d) => d.value);
  const rawPrevTrendValues = prevTrendData
    .filter((d): d is typeof d & { value: number } => d.value !== null)
    .map((d) => d.value);
  const trendValues = options?.winsorizeTrend
    ? winsorize(rawTrendValues, 5, 95)
    : rawTrendValues;
  const prevTrendValues = options?.winsorizeTrend
    ? winsorize(rawPrevTrendValues, 5, 95)
    : rawPrevTrendValues;

  // Require at least 70% of the trend window to have data
  const minDataForTrend = Math.max(3, Math.floor(trendWindow * 0.7));
  const hasValidTrendData =
    trendValues.length >= minDataForTrend &&
    prevTrendValues.length >= minDataForTrend;

  let trendSlope: number | null = null;
  if (hasValidTrendData) {
    // For longer windows (>14 days), use linear regression for more accurate trend
    if (trendWindow > 14 && trendValues.length >= 7) {
      // FIX 4: Use real dates for regression if option is set
      if (options?.regressionUsesRealDays) {
        trendSlope = linearSlopePerDay(
          trendData,
          options.winsorizeTrend ? [5, 95] : undefined,
        );
      } else {
        // Legacy: index-based regression
        const n = trendValues.length;
        const xMean = (n - 1) / 2;
        const yMean = meanOrNull(trendValues) ?? 0;
        let numerator = 0;
        let denominator = 0;
        for (let i = 0; i < n; i++) {
          const xDiff = i - xMean;
          numerator += xDiff * (trendValues[i] - yMean);
          denominator += xDiff * xDiff;
        }
        trendSlope = denominator !== 0 ? numerator / denominator : null;
      }
    } else {
      // For shorter windows, use median comparison (more robust to outliers)
      const currentMedian = calculateMedian(trendValues);
      const prevMedian = calculateMedian(prevTrendValues);
      // Change per day over the trend period
      trendSlope = (currentMedian - prevMedian) / trendWindow;
    }
  }

  return {
    mean,
    std,
    median,
    cv,
    currentValue,
    zScore,
    shiftedZScore,
    percentChange,
    trendSlope,
    shortTermMean,
    longTermMean: mean,
  };
}

function linearSlopePerDay(
  points: DataPoint[],
  winsorizePct?: [number, number],
): number | null {
  const pts = points.filter(
    (p): p is typeof p & { value: number } => p.value !== null,
  );
  if (pts.length < 7) return null;

  const xs = pts.map((p) => toDayNumber(p.date));
  const ysRaw = pts.map((p) => p.value);
  const ys = winsorizePct
    ? winsorize(ysRaw, winsorizePct[0], winsorizePct[1])
    : ysRaw;

  const xMean = meanOrNull(xs) ?? 0;
  const yMean = meanOrNull(ys) ?? 0;

  let num = 0;
  let den = 0;
  for (let i = 0; i < xs.length; i++) {
    const xDiff = xs[i] - xMean;
    num += xDiff * (ys[i] - yMean);
    den += xDiff * xDiff;
  }
  return den !== 0 ? num / den : null;
}

// ============================================
// 3) RECOVERY / READINESS METRICS
// ============================================

export interface RecoveryMetrics {
  hrvRhrImbalance: number | null;
  recoveryCV: number;
  stressLoadShort: number | null;
  stressLoadLong: number | null;
  stressTrend: number | null;
  shortTermWindow: number;
  longTermWindow: number;
}

export function calculateRecoveryMetrics(
  hrvData: DataPoint[],
  rhrData: DataPoint[],
  stressData: DataPoint[],
  recoveryData: DataPoint[],
  shortTermWindow: number = 7,
  longTermWindow: number = 30,
  trendWindow: number = 7,
): RecoveryMetrics {
  const hrvBaseline = calculateBaselineMetrics(
    hrvData,
    longTermWindow,
    shortTermWindow,
    "hrv",
    trendWindow,
  );
  const rhrBaseline = calculateBaselineMetrics(
    rhrData,
    longTermWindow,
    shortTermWindow,
    "rhr",
    trendWindow,
  );

  let hrvRhrImbalance: number | null = null;
  if (hrvBaseline.zScore !== null && rhrBaseline.zScore !== null) {
    hrvRhrImbalance = -hrvBaseline.zScore + rhrBaseline.zScore;
  }

  const recoveryBaseline = calculateBaselineMetrics(
    recoveryData,
    longTermWindow,
    shortTermWindow,
    "recovery",
    trendWindow,
  );
  const recoveryCV = recoveryBaseline.cv;

  const dailyStress = toDailySeries(stressData, "mean");
  const stressShortValues = getWindowValues(dailyStress, shortTermWindow);
  const stressLongValues = getWindowValues(dailyStress, longTermWindow);
  const stressTrendValues = getWindowValues(dailyStress, trendWindow);
  const stressPrevTrendValues = getWindowRangeValues(
    dailyStress,
    trendWindow * 2,
    trendWindow,
  );

  const stressLoadShort = sumOrNull(stressShortValues);
  const stressLoadLong = sumOrNull(stressLongValues);
  const stressTrendMean = meanOrNull(stressTrendValues);
  const stressPrevTrendMean = meanOrNull(stressPrevTrendValues);

  const minDataForTrend = Math.min(
    14,
    Math.max(3, Math.floor(trendWindow * 0.7)),
  );
  const hasValidStressTrend =
    stressTrendMean !== null &&
    stressPrevTrendMean !== null &&
    stressTrendValues.length >= minDataForTrend &&
    stressPrevTrendValues.length >= minDataForTrend;

  const stressTrend = hasValidStressTrend
    ? stressTrendMean - stressPrevTrendMean
    : null;

  return {
    hrvRhrImbalance,
    recoveryCV,
    stressLoadShort,
    stressLoadLong,
    stressTrend,
    shortTermWindow,
    longTermWindow,
  };
}

// ============================================
// 4) SLEEP METRICS
// ============================================

export interface SleepMetrics {
  sleepDebtShort: number;
  sleepSurplusShort: number;
  sleepCV: number;
  targetSleep: number;
  avgSleepShort: number | null;
  avgSleepLong: number | null;
  shortTermWindow: number;
  longTermWindow: number;
}

const MAX_SLEEP_TARGET_WINDOW = 90;

export function calculateSleepMetrics(
  sleepData: DataPoint[],
  shortTermWindow: number = 7,
  longTermWindow: number = 30,
  targetMinutes?: number,
): SleepMetrics {
  const dailySleep = toDailySeries(sleepData, "last");

  const targetWindow = Math.min(longTermWindow, MAX_SLEEP_TARGET_WINDOW);
  const targetBaselineValues = getWindowValues(dailySleep, targetWindow);
  const personalTarget =
    targetMinutes ??
    (targetBaselineValues.length > 0
      ? [...targetBaselineValues].sort((a, b) => a - b)[
          Math.floor(targetBaselineValues.length / 2)
        ]
      : 480);

  const shortValues = getWindowValues(dailySleep, shortTermWindow);
  const longValues = getWindowValues(dailySleep, longTermWindow);

  let sleepDebtShort = 0;
  let sleepSurplusShort = 0;
  for (const sleep of shortValues) {
    if (sleep < personalTarget) {
      sleepDebtShort += personalTarget - sleep;
    } else {
      sleepSurplusShort += sleep - personalTarget;
    }
  }

  const avgSleepShort = meanOrNull(shortValues);
  const avgSleepLong = meanOrNull(longValues);

  const meanLong = avgSleepLong ?? 0;
  const stdLong = calculateStd(longValues);
  const sleepCV = meanLong !== 0 ? stdLong / Math.abs(meanLong) : 0;

  return {
    sleepDebtShort,
    sleepSurplusShort,
    sleepCV,
    targetSleep: personalTarget,
    avgSleepShort,
    avgSleepLong,
    shortTermWindow,
    longTermWindow,
  };
}

// ============================================
// 5) ACTIVITY / TRAINING LOAD METRICS
// ============================================

export interface ActivityMetrics {
  acuteLoad: number | null;
  chronicLoad: number | null;
  acwr: number | null;
  stepsAvgShort: number | null;
  stepsAvgLong: number | null;
  stepsChange: number | null;
  stepsCV: number;
  shortTermWindow: number;
  longTermWindow: number;
}

export function calculateActivityMetrics(
  strainData: DataPoint[],
  stepsData: DataPoint[],
  shortTermWindow: number = 7,
  longTermWindow: number = 30,
  trendWindow: number = 7,
): ActivityMetrics {
  const dailyStrain = toDailySeries(strainData, "max");
  const strainShortValues = getWindowValues(dailyStrain, shortTermWindow);
  const strainLongValues = getWindowValues(dailyStrain, longTermWindow);

  const acuteLoad = meanOrNull(strainShortValues);
  const chronicLoad = meanOrNull(strainLongValues);
  const acwr =
    acuteLoad !== null && chronicLoad !== null && chronicLoad > 0
      ? acuteLoad / chronicLoad
      : null;

  const dailySteps = toDailySeries(stepsData, "last");
  const stepsShortValues = getWindowValues(dailySteps, shortTermWindow);
  const stepsLongValues = getWindowValues(dailySteps, longTermWindow);
  const stepsTrendValues = getWindowValues(dailySteps, trendWindow);
  const stepsPrevTrendValues = getWindowRangeValues(
    dailySteps,
    trendWindow * 2,
    trendWindow,
  );

  const stepsAvgShort = meanOrNull(stepsShortValues);
  const stepsAvgLong = meanOrNull(stepsLongValues);
  const stepsTrendMean = meanOrNull(stepsTrendValues);
  const stepsPrevTrendMean = meanOrNull(stepsPrevTrendValues);

  const minDataForTrend = Math.min(
    14,
    Math.max(3, Math.floor(trendWindow * 0.7)),
  );
  const hasValidStepsTrend =
    stepsTrendMean !== null &&
    stepsPrevTrendMean !== null &&
    stepsTrendValues.length >= minDataForTrend &&
    stepsPrevTrendValues.length >= minDataForTrend;

  const stepsChange = hasValidStepsTrend
    ? stepsTrendMean - stepsPrevTrendMean
    : null;

  const stepsMean = stepsAvgLong ?? 0;
  const stepsStd = calculateStd(stepsLongValues);
  const stepsCV = stepsMean !== 0 ? stepsStd / Math.abs(stepsMean) : 0;

  return {
    acuteLoad,
    chronicLoad,
    acwr,
    stepsAvgShort,
    stepsAvgLong,
    stepsChange,
    stepsCV,
    shortTermWindow,
    longTermWindow,
  };
}

// ============================================
// 6) WEIGHT METRICS
// ============================================

export interface WeightMetrics {
  emaShort: number | null;
  emaLong: number | null;
  periodChange: number | null;
  volatilityShort: number;
  volatilityLong: number;
}

export function calculateWeightMetrics(
  weightData: DataPoint[],
  shortTermWindow: number = 7,
  longTermWindow: number = 30,
  trendWindow: number = 7,
): WeightMetrics {
  const dailyWeight = toDailySeries(weightData, "last");

  if (dailyWeight.length === 0) {
    return {
      emaShort: null,
      emaLong: null,
      periodChange: null,
      volatilityShort: 0,
      volatilityLong: 0,
    };
  }

  const allValues = dailyWeight
    .filter((d): d is typeof d & { value: number } => d.value !== null)
    .map((d) => d.value);
  const emaShort = calculateEMAValue(allValues, shortTermWindow);
  const emaLong = calculateEMAValue(allValues, longTermWindow);

  const lastShortValues = getWindowValues(dailyWeight, shortTermWindow);
  const trendValues = getWindowValues(dailyWeight, trendWindow);
  const prevTrendValues = getWindowRangeValues(
    dailyWeight,
    trendWindow * 2,
    trendWindow,
  );
  const lastLongValues = getWindowValues(dailyWeight, longTermWindow);

  const meanTrend = meanOrNull(trendValues);
  const meanPrevTrend = meanOrNull(prevTrendValues);
  const periodChange =
    meanTrend !== null && meanPrevTrend !== null
      ? meanTrend - meanPrevTrend
      : null;

  const volatilityShort = calculateStd(lastShortValues);
  const volatilityLong = calculateStd(lastLongValues);

  return {
    emaShort,
    emaLong,
    periodChange,
    volatilityShort,
    volatilityLong,
  };
}

// ============================================
// 7) CALORIES METRICS (Fused Garmin + Whoop)
// ============================================

export interface CaloriesMetrics {
  avg7: number | null;
  avg30: number | null;
  delta: number | null;
  cv30: number;
  zScore: number | null;
  trend: "increasing" | "decreasing" | "stable" | null;
}

export function calculateCaloriesMetrics(
  caloriesData: DataPoint[],
): CaloriesMetrics {
  const daily = toDailySeries(caloriesData, "last");

  if (daily.length === 0) {
    return {
      avg7: null,
      avg30: null,
      delta: null,
      cv30: 0,
      zScore: null,
      trend: null,
    };
  }

  const last7 = getWindowValues(daily, 7);
  const last30 = getWindowValues(daily, 30);

  const avg7 = meanOrNull(last7);
  const avg30 = meanOrNull(last30);

  const delta = avg7 !== null && avg30 !== null ? avg7 - avg30 : null;

  const mean30 = avg30 ?? 0;
  const std30 = calculateStd(last30);
  const cv30 = mean30 !== 0 ? std30 / Math.abs(mean30) : 0;

  const sortedDaily = [...daily].sort(
    (a, b) => toTimeMs(a.date) - toTimeMs(b.date),
  );
  const currentValue = sortedDaily[sortedDaily.length - 1]?.value ?? null;
  const zScore =
    currentValue !== null && std30 > 0 ? (currentValue - mean30) / std30 : null;

  let trend: "increasing" | "decreasing" | "stable" | null = null;
  if (delta !== null) {
    if (delta > mean30 * 0.05) trend = "increasing";
    else if (delta < -mean30 * 0.05) trend = "decreasing";
    else trend = "stable";
  }

  return { avg7, avg30, delta, cv30, zScore, trend };
}

// ============================================
// 8) ENERGY BALANCE PROXY
// ============================================

export interface EnergyBalanceMetrics {
  caloriesTrend: "surplus" | "deficit" | "maintenance" | null;
  weightTrend: "gaining" | "losing" | "stable" | null;
  balanceSignal: "surplus_confirmed" | "deficit_confirmed" | "mixed" | null;
  calDelta: number | null;
  weightDelta: number | null;
}

export function calculateEnergyBalance(
  caloriesMetrics: CaloriesMetrics,
  weightMetrics: WeightMetrics,
): EnergyBalanceMetrics {
  const calDelta = caloriesMetrics.delta;
  const weightDelta = weightMetrics.periodChange;

  let caloriesTrend: "surplus" | "deficit" | "maintenance" | null = null;
  if (calDelta !== null) {
    if (calDelta > 100) caloriesTrend = "surplus";
    else if (calDelta < -100) caloriesTrend = "deficit";
    else caloriesTrend = "maintenance";
  }

  let weightTrend: "gaining" | "losing" | "stable" | null = null;
  if (weightDelta !== null) {
    if (weightDelta > 0.2) weightTrend = "gaining";
    else if (weightDelta < -0.2) weightTrend = "losing";
    else weightTrend = "stable";
  }

  let balanceSignal:
    | "surplus_confirmed"
    | "deficit_confirmed"
    | "mixed"
    | null = null;
  if (caloriesTrend !== null && weightTrend !== null) {
    if (
      (caloriesTrend === "surplus" && weightTrend === "gaining") ||
      (caloriesTrend === "maintenance" && weightTrend === "gaining")
    ) {
      balanceSignal = "surplus_confirmed";
    } else if (
      (caloriesTrend === "deficit" && weightTrend === "losing") ||
      (caloriesTrend === "maintenance" && weightTrend === "losing")
    ) {
      balanceSignal = "deficit_confirmed";
    } else {
      balanceSignal = "mixed";
    }
  }

  return {
    caloriesTrend,
    weightTrend,
    balanceSignal,
    calDelta,
    weightDelta,
  };
}

// ============================================
// 11) COMPOSITE HEALTH SCORE
// ============================================

export interface HealthScore {
  overall: number | null;
  recoveryCore: number | null;
  behaviorSupport: number | null;
  contributors: {
    name: string;
    rawZScore: number | null;
    goodnessZScore: number | null;
    weight: number;
    contribution: number | null;
    confidence: number;
    isGated: boolean;
    gateReason: string;
    source?: DataProvider;
  }[];
  stepsStatus: {
    useToday: boolean;
    reason: string;
  };
}

const CONFIDENCE_THRESHOLD = 0.6;

function capConfidence(conf: number): number {
  return Math.max(0, Math.min(1, conf));
}

export interface FusedZScoreInput {
  zScore: number | null;
  confidence: number;
  source: DataProvider;
}

export function calculateHealthScore(
  hrvData: DataPoint[],
  rhrData: DataPoint[],
  sleepData: DataPoint[],
  stressData: DataPoint[],
  stepsData: DataPoint[],
  strainData: DataPoint[],
  hrvQuality?: DataQuality,
  rhrQuality?: DataQuality,
  sleepQuality?: DataQuality,
  stressQuality?: DataQuality,
  stepsQuality?: DataQuality,
  strainQuality?: DataQuality,
  fusedInputs?: {
    hrv?: FusedZScoreInput;
    rhr?: FusedZScoreInput;
    sleep?: FusedZScoreInput;
    calories?: FusedZScoreInput;
  },
  caloriesData?: DataPoint[],
  baselineWindow: number = 30,
  shortTermWindow: number = 7,
  trendWindow: number = 7,
  options?: BaselineOptions,
  useShiftedZScore: boolean = false,
): HealthScore {
  const stepsCheck = shouldUseTodayMetric(stepsData, "steps");
  const adjustedStepsData = stepsCheck.adjustedData;

  const strainCheck = shouldUseTodayMetric(strainData, "strain");
  const adjustedStrainData = strainCheck.adjustedData;

  const caloriesCheck = caloriesData
    ? shouldUseTodayMetric(caloriesData, "calories")
    : { useToday: false, adjustedData: [], reason: "No calories data" };
  const adjustedCaloriesData = caloriesCheck.adjustedData;

  const hrvBaseline = calculateBaselineMetrics(
    hrvData,
    baselineWindow,
    shortTermWindow,
    "hrv",
    trendWindow,
    options,
  );
  const rhrBaseline = calculateBaselineMetrics(
    rhrData,
    baselineWindow,
    shortTermWindow,
    "rhr",
    trendWindow,
    options,
  );
  const sleepBaseline = calculateBaselineMetrics(
    sleepData,
    baselineWindow,
    shortTermWindow,
    "sleep",
    trendWindow,
    options,
  );
  const stressBaseline = calculateBaselineMetrics(
    stressData,
    baselineWindow,
    shortTermWindow,
    "stress",
    trendWindow,
    options,
  );
  const stepsBaseline = calculateBaselineMetrics(
    adjustedStepsData,
    baselineWindow,
    shortTermWindow,
    "steps",
    trendWindow,
    options,
  );
  const strainBaseline = calculateBaselineMetrics(
    adjustedStrainData,
    baselineWindow,
    shortTermWindow,
    "strain",
    trendWindow,
    options,
  );
  const caloriesBaseline =
    adjustedCaloriesData.length > 0
      ? calculateBaselineMetrics(
          adjustedCaloriesData,
          baselineWindow,
          shortTermWindow,
          "calories",
          trendWindow,
          options,
        )
      : null;

  const hrvConf = capConfidence(
    fusedInputs?.hrv?.confidence ?? hrvQuality?.confidence ?? 1,
  );
  const rhrConf = capConfidence(
    fusedInputs?.rhr?.confidence ?? rhrQuality?.confidence ?? 1,
  );
  const sleepConf = capConfidence(
    fusedInputs?.sleep?.confidence ?? sleepQuality?.confidence ?? 1,
  );
  const stressConf = capConfidence(stressQuality?.confidence ?? 1);
  const stepsConf = capConfidence(stepsQuality?.confidence ?? 1);
  const strainConf = capConfidence(strainQuality?.confidence ?? 1);
  const caloriesConf = capConfidence(
    fusedInputs?.calories?.confidence ??
      (caloriesBaseline !== null && caloriesBaseline.zScore !== null ? 0.7 : 0),
  );

  // For Mid/Long modes, use shiftedZScore (period vs baseline) instead of point z-score
  // This makes HealthScore less "jumpy" from day-to-day noise
  const selectZScore = (
    baseline: BaselineMetrics,
    fused?: number | null,
  ): number | null => {
    if (fused !== undefined && fused !== null) return fused;
    return useShiftedZScore ? baseline.shiftedZScore : baseline.zScore;
  };

  const rawZHRV = selectZScore(hrvBaseline, fusedInputs?.hrv?.zScore);
  const rawZRHR = selectZScore(rhrBaseline, fusedInputs?.rhr?.zScore);
  const rawZSleep = selectZScore(sleepBaseline, fusedInputs?.sleep?.zScore);
  const rawZStress = useShiftedZScore
    ? stressBaseline.shiftedZScore
    : stressBaseline.zScore;
  const rawZSteps = useShiftedZScore
    ? stepsBaseline.shiftedZScore
    : stepsBaseline.zScore;
  const rawZLoad = useShiftedZScore
    ? strainBaseline.shiftedZScore
    : strainBaseline.zScore;
  const rawZCalories = selectZScore(
    caloriesBaseline ?? {
      mean: 0,
      std: 0,
      median: 0,
      cv: 0,
      currentValue: null,
      zScore: null,
      shiftedZScore: null,
      percentChange: null,
      trendSlope: null,
      shortTermMean: null,
      longTermMean: null,
    },
    fusedInputs?.calories?.zScore,
  );

  const zHRV = rawZHRV;
  const zRHR = rawZRHR !== null ? -rawZRHR : null;
  const zSleep = rawZSleep;
  const zStress = rawZStress !== null ? -rawZStress : null;
  const zSteps = rawZSteps;
  const zLoad = rawZLoad !== null ? -Math.abs(rawZLoad) : null;
  const zCalories = rawZCalories !== null ? -Math.abs(rawZCalories) : null;

  const coreWeights = { hrv: 0.35, rhr: 0.25, sleep: 0.25, stress: 0.15 };
  const supportWeights = { steps: 0.5, calories: 0.5 };

  const hrvGated = hrvConf < CONFIDENCE_THRESHOLD;
  const rhrGated = rhrConf < CONFIDENCE_THRESHOLD;
  const sleepGated = sleepConf < CONFIDENCE_THRESHOLD;
  const stressGated = stressConf < CONFIDENCE_THRESHOLD;
  const stepsGated = stepsConf < CONFIDENCE_THRESHOLD;
  const strainGated = strainConf < CONFIDENCE_THRESHOLD;
  const caloriesGated = caloriesConf < CONFIDENCE_THRESHOLD;

  let recoveryCore: number | null = null;
  let coreSum = 0;
  let coreWeightSum = 0;

  if (zHRV !== null && !hrvGated) {
    const effectiveWeight = coreWeights.hrv * hrvConf;
    coreSum += zHRV * effectiveWeight;
    coreWeightSum += effectiveWeight;
  }
  if (zRHR !== null && !rhrGated) {
    const effectiveWeight = coreWeights.rhr * rhrConf;
    coreSum += zRHR * effectiveWeight;
    coreWeightSum += effectiveWeight;
  }
  if (zSleep !== null && !sleepGated) {
    const effectiveWeight = coreWeights.sleep * sleepConf;
    coreSum += zSleep * effectiveWeight;
    coreWeightSum += effectiveWeight;
  }
  if (zStress !== null && !stressGated) {
    const effectiveWeight = coreWeights.stress * stressConf;
    coreSum += zStress * effectiveWeight;
    coreWeightSum += effectiveWeight;
  }

  if (coreWeightSum > 0) {
    recoveryCore = coreSum / coreWeightSum;
  }

  let behaviorSupport: number | null = null;
  let supportSum = 0;
  let supportWeightSum = 0;

  if (zSteps !== null && !stepsGated) {
    const effectiveWeight = supportWeights.steps * stepsConf;
    supportSum += zSteps * effectiveWeight;
    supportWeightSum += effectiveWeight;
  }
  if (zCalories !== null && !caloriesGated) {
    const effectiveWeight = supportWeights.calories * caloriesConf;
    supportSum += zCalories * effectiveWeight;
    supportWeightSum += effectiveWeight;
  }

  if (supportWeightSum === 0 && zLoad !== null && !strainGated) {
    supportSum = zLoad * strainConf;
    supportWeightSum = strainConf;
  }

  if (supportWeightSum > 0) {
    behaviorSupport = supportSum / supportWeightSum;
  }

  let overall: number | null = null;
  if (recoveryCore !== null && behaviorSupport !== null) {
    overall = 0.7 * recoveryCore + 0.3 * behaviorSupport;
  } else if (recoveryCore !== null) {
    overall = recoveryCore;
  } else if (behaviorSupport !== null) {
    overall = behaviorSupport;
  }

  function gateReason(conf: number, gated: boolean): string {
    if (!gated) return "";
    return `Conf ${(conf * 100).toFixed(0)}% < ${(CONFIDENCE_THRESHOLD * 100).toFixed(0)}%`;
  }

  const contributors = [
    {
      name: "HRV",
      rawZScore: rawZHRV,
      goodnessZScore: zHRV,
      weight: coreWeights.hrv,
      contribution:
        zHRV !== null && !hrvGated ? zHRV * coreWeights.hrv * hrvConf : null,
      confidence: hrvConf,
      isGated: hrvGated,
      gateReason: gateReason(hrvConf, hrvGated),
      source: fusedInputs?.hrv?.source,
    },
    {
      name: "Resting HR",
      rawZScore: rawZRHR,
      goodnessZScore: zRHR,
      weight: coreWeights.rhr,
      contribution:
        zRHR !== null && !rhrGated ? zRHR * coreWeights.rhr * rhrConf : null,
      confidence: rhrConf,
      isGated: rhrGated,
      gateReason: gateReason(rhrConf, rhrGated),
      source: fusedInputs?.rhr?.source,
    },
    {
      name: "Sleep",
      rawZScore: rawZSleep,
      goodnessZScore: zSleep,
      weight: coreWeights.sleep,
      contribution:
        zSleep !== null && !sleepGated
          ? zSleep * coreWeights.sleep * sleepConf
          : null,
      confidence: sleepConf,
      isGated: sleepGated,
      gateReason: gateReason(sleepConf, sleepGated),
      source: fusedInputs?.sleep?.source,
    },
    {
      name: "Stress",
      rawZScore: rawZStress,
      goodnessZScore: zStress,
      weight: coreWeights.stress,
      contribution:
        zStress !== null && !stressGated
          ? zStress * coreWeights.stress * stressConf
          : null,
      confidence: stressConf,
      isGated: stressGated,
      gateReason: gateReason(stressConf, stressGated),
      source: "garmin" as const,
    },
    {
      name: "Steps",
      rawZScore: rawZSteps,
      goodnessZScore: zSteps,
      weight: supportWeights.steps,
      contribution:
        zSteps !== null && !stepsGated
          ? zSteps * supportWeights.steps * stepsConf
          : null,
      confidence: stepsConf,
      isGated: stepsGated,
      gateReason: stepsGated
        ? gateReason(stepsConf, stepsGated)
        : stepsCheck.reason,
      source: "garmin" as const,
    },
    {
      name: "Calories",
      rawZScore: rawZCalories,
      goodnessZScore: zCalories,
      weight: supportWeights.calories,
      contribution:
        zCalories !== null && !caloriesGated
          ? zCalories * supportWeights.calories * caloriesConf
          : null,
      confidence: caloriesConf,
      isGated: caloriesGated,
      gateReason: gateReason(caloriesConf, caloriesGated),
      source: fusedInputs?.calories?.source,
    },
  ];

  return {
    overall,
    recoveryCore,
    behaviorSupport,
    contributors,
    stepsStatus: {
      useToday: stepsCheck.useToday,
      reason: stepsCheck.reason,
    },
  };
}

// ============================================
// 12) CLINICAL ALERTS
// ============================================

export interface ClinicalAlerts {
  persistentTachycardia: boolean;
  tachycardiaDays: number;
  acuteHRVDrop: boolean;
  hrvDropPercent: number | null;
  progressiveWeightLoss: boolean;
  weightLossPercent: number | null;
  severeOvertraining: boolean;
  overtrainingScore: number | null;
  anyAlert: boolean;
}

const TACHYCARDIA_SIGMA = 2;
const TACHYCARDIA_MIN_DAYS = 3;
const HRV_DROP_THRESHOLD = 0.3;
const WEIGHT_LOSS_THRESHOLD = 0.05;
const ACWR_DANGER_THRESHOLD = 1.5;
const HRV_LOW_SIGMA = -1.5;

export function calculateClinicalAlerts(
  rhrData: DataPoint[],
  hrvData: DataPoint[],
  weightData: DataPoint[],
  strainData: DataPoint[],
  baselineWindow: number = 30,
): ClinicalAlerts {
  const rhrBaseline = calculateBaselineMetrics(
    rhrData,
    baselineWindow,
    7,
    "rhr",
  );
  const hrvBaseline = calculateBaselineMetrics(
    hrvData,
    baselineWindow,
    7,
    "hrv",
  );

  // 1. Persistent Tachycardia: RHR > baseline + 2σ for 3+ consecutive days
  const dailyRHR = toDailySeries(rhrData, "mean");
  const recentRHR = filterDataByWindow(dailyRHR, 7)
    .filter((d) => d.value !== null)
    .sort((a, b) => toTimeMs(a.date) - toTimeMs(b.date));

  let tachycardiaDays = 0;
  const rhrThreshold = rhrBaseline.mean + TACHYCARDIA_SIGMA * rhrBaseline.std;

  if (rhrBaseline.std > MIN_STD_THRESHOLD) {
    let currentStreak = 0;
    for (const d of recentRHR) {
      if (d.value !== null && d.value > rhrThreshold) {
        currentStreak++;
        tachycardiaDays = Math.max(tachycardiaDays, currentStreak);
      } else {
        currentStreak = 0;
      }
    }
  }
  const persistentTachycardia = tachycardiaDays >= TACHYCARDIA_MIN_DAYS;

  // 2. Acute HRV Drop: >30% drop day-over-day
  const dailyHRV = toDailySeries(hrvData, "mean");
  const sortedHRV = [...dailyHRV]
    .filter((d) => d.value !== null)
    .sort((a, b) => toTimeMs(a.date) - toTimeMs(b.date));

  let hrvDropPercent: number | null = null;
  let acuteHRVDrop = false;

  if (sortedHRV.length >= 2) {
    const latest = sortedHRV[sortedHRV.length - 1].value!;
    const previous = sortedHRV[sortedHRV.length - 2].value!;
    if (previous > 0) {
      hrvDropPercent = (previous - latest) / previous;
      acuteHRVDrop = hrvDropPercent > HRV_DROP_THRESHOLD;
    }
  }

  // 3. Progressive Weight Loss: >5% over 30 days
  const dailyWeight = toDailySeries(weightData, "last");
  const last30Weight = filterDataByWindow(dailyWeight, 30).filter(
    (d) => d.value !== null,
  );
  const sortedWeight = [...last30Weight].sort(
    (a, b) => toTimeMs(a.date) - toTimeMs(b.date),
  );

  let weightLossPercent: number | null = null;
  let progressiveWeightLoss = false;

  if (sortedWeight.length >= 2) {
    const earliest = sortedWeight[0].value!;
    const latest = sortedWeight[sortedWeight.length - 1].value!;
    if (earliest > 0) {
      weightLossPercent = (earliest - latest) / earliest;
      progressiveWeightLoss = weightLossPercent > WEIGHT_LOSS_THRESHOLD;
    }
  }

  // 4. Severe Overtraining: ACWR > 1.5 + low HRV
  const activityMetrics = calculateActivityMetrics(strainData, [], 7, 28, 7);
  const hrvZScore = hrvBaseline.zScore;

  let severeOvertraining = false;
  let overtrainingScore: number | null = null;

  if (activityMetrics.acwr !== null && hrvZScore !== null) {
    const acwrExcess = Math.max(0, activityMetrics.acwr - 1.0);
    const hrvDeficit = Math.max(0, -hrvZScore);
    overtrainingScore = acwrExcess * hrvDeficit;
    severeOvertraining =
      activityMetrics.acwr > ACWR_DANGER_THRESHOLD && hrvZScore < HRV_LOW_SIGMA;
  }

  const anyAlert =
    persistentTachycardia ||
    acuteHRVDrop ||
    progressiveWeightLoss ||
    severeOvertraining;

  return {
    persistentTachycardia,
    tachycardiaDays,
    acuteHRVDrop,
    hrvDropPercent,
    progressiveWeightLoss,
    weightLossPercent,
    severeOvertraining,
    overtrainingScore,
    anyAlert,
  };
}

// ============================================
// 13) OVERREACHING SCORE
// ============================================

export interface OverreachingMetrics {
  score: number | null;
  riskLevel: "low" | "moderate" | "high" | "critical" | null;
  components: {
    strainComponent: number | null;
    hrvComponent: number | null;
    sleepComponent: number | null;
    rhrComponent: number | null;
  };
  consecutiveLowRecoveryDays: number;
}

const OVERREACHING_THRESHOLDS = {
  low: 1.0,
  moderate: 2.0,
  high: 3.0,
};

export function calculateOverreachingMetrics(
  hrvData: DataPoint[],
  rhrData: DataPoint[],
  sleepData: DataPoint[],
  strainData: DataPoint[],
  baselineWindow: number = 30,
  shortTermWindow: number = 7,
): OverreachingMetrics {
  const hrvBaseline = calculateBaselineMetrics(
    hrvData,
    baselineWindow,
    shortTermWindow,
    "hrv",
  );
  const rhrBaseline = calculateBaselineMetrics(
    rhrData,
    baselineWindow,
    shortTermWindow,
    "rhr",
  );
  const sleepBaseline = calculateBaselineMetrics(
    sleepData,
    baselineWindow,
    shortTermWindow,
    "sleep",
  );
  const strainBaseline = calculateBaselineMetrics(
    strainData,
    baselineWindow,
    shortTermWindow,
    "strain",
  );

  // Components: positive = bad (contributing to overreaching)
  // strain↑ = bad, HRV↓ = bad, sleep↓ = bad, RHR↑ = bad
  const strainComponent =
    strainBaseline.zScore !== null ? Math.max(0, strainBaseline.zScore) : null;
  const hrvComponent =
    hrvBaseline.zScore !== null ? Math.max(0, -hrvBaseline.zScore) : null;
  const sleepComponent =
    sleepBaseline.zScore !== null ? Math.max(0, -sleepBaseline.zScore) : null;
  const rhrComponent =
    rhrBaseline.zScore !== null ? Math.max(0, rhrBaseline.zScore) : null;

  // Consecutive low recovery days (HRV z-score < -1)
  const dailyHRV = toDailySeries(hrvData, "mean");
  const recentHRV = filterDataByWindow(dailyHRV, 14)
    .filter((d) => d.value !== null)
    .sort((a, b) => toTimeMs(b.date) - toTimeMs(a.date)); // Most recent first

  let consecutiveLowRecoveryDays = 0;
  if (hrvBaseline.std > MIN_STD_THRESHOLD) {
    for (const d of recentHRV) {
      if (d.value !== null) {
        const zScore = (d.value - hrvBaseline.mean) / hrvBaseline.std;
        if (zScore < -1) {
          consecutiveLowRecoveryDays++;
        } else {
          break;
        }
      }
    }
  }

  // Combined score: weighted sum of components
  const weights = { strain: 0.3, hrv: 0.3, sleep: 0.25, rhr: 0.15 };
  let score: number | null = null;
  let totalWeight = 0;
  let weightedSum = 0;

  if (strainComponent !== null) {
    weightedSum += strainComponent * weights.strain;
    totalWeight += weights.strain;
  }
  if (hrvComponent !== null) {
    weightedSum += hrvComponent * weights.hrv;
    totalWeight += weights.hrv;
  }
  if (sleepComponent !== null) {
    weightedSum += sleepComponent * weights.sleep;
    totalWeight += weights.sleep;
  }
  if (rhrComponent !== null) {
    weightedSum += rhrComponent * weights.rhr;
    totalWeight += weights.rhr;
  }

  if (totalWeight > 0) {
    score = weightedSum / totalWeight;
  }

  let riskLevel: "low" | "moderate" | "high" | "critical" | null = null;
  if (score !== null) {
    if (score < OVERREACHING_THRESHOLDS.low) riskLevel = "low";
    else if (score < OVERREACHING_THRESHOLDS.moderate) riskLevel = "moderate";
    else if (score < OVERREACHING_THRESHOLDS.high) riskLevel = "high";
    else riskLevel = "critical";
  }

  return {
    score,
    riskLevel,
    components: {
      strainComponent,
      hrvComponent,
      sleepComponent,
      rhrComponent,
    },
    consecutiveLowRecoveryDays,
  };
}

// ============================================
// 14) CORRELATION METRICS
// ============================================

export interface CorrelationMetrics {
  hrvRhrCorrelation: number | null;
  sleepHrvLagCorrelation: number | null;
  strainRecoveryCorrelation: number | null;
  sampleSize: number;
}

function calculatePearsonCorrelation(x: number[], y: number[]): number | null {
  if (x.length !== y.length || x.length < 7) return null;

  const n = x.length;
  const xMean = meanOrNull(x) ?? 0;
  const yMean = meanOrNull(y) ?? 0;

  let numerator = 0;
  let xDenominator = 0;
  let yDenominator = 0;

  for (let i = 0; i < n; i++) {
    const xDiff = x[i] - xMean;
    const yDiff = y[i] - yMean;
    numerator += xDiff * yDiff;
    xDenominator += xDiff * xDiff;
    yDenominator += yDiff * yDiff;
  }

  const denominator = Math.sqrt(xDenominator * yDenominator);
  if (denominator < MIN_STD_THRESHOLD) return null;

  return numerator / denominator;
}

export function calculateCorrelationMetrics(
  hrvData: DataPoint[],
  rhrData: DataPoint[],
  sleepData: DataPoint[],
  strainData: DataPoint[],
  windowDays: number = 30,
): CorrelationMetrics {
  const dailyHRV = toDailySeries(hrvData, "mean");
  const dailyRHR = toDailySeries(rhrData, "mean");
  const dailySleep = toDailySeries(sleepData, "last");
  const dailyStrain = toDailySeries(strainData, "max");

  const hrvMap = new Map(
    filterDataByWindow(dailyHRV, windowDays)
      .filter((d) => d.value !== null)
      .map((d) => [toLocalDayKey(d.date), d.value!]),
  );
  const rhrMap = new Map(
    filterDataByWindow(dailyRHR, windowDays)
      .filter((d) => d.value !== null)
      .map((d) => [toLocalDayKey(d.date), d.value!]),
  );
  const sleepMap = new Map(
    filterDataByWindow(dailySleep, windowDays)
      .filter((d) => d.value !== null)
      .map((d) => [toLocalDayKey(d.date), d.value!]),
  );
  const strainMap = new Map(
    filterDataByWindow(dailyStrain, windowDays)
      .filter((d) => d.value !== null)
      .map((d) => [toLocalDayKey(d.date), d.value!]),
  );

  // 1. HRV↔RHR correlation (same day) - should be negative
  const hrvRhrPairs: { hrv: number; rhr: number }[] = [];
  for (const [date, hrv] of hrvMap) {
    const rhr = rhrMap.get(date);
    if (rhr !== undefined) {
      hrvRhrPairs.push({ hrv, rhr });
    }
  }
  const hrvRhrCorrelation = calculatePearsonCorrelation(
    hrvRhrPairs.map((p) => p.hrv),
    hrvRhrPairs.map((p) => p.rhr),
  );

  // 2. Sleep→HRV lag correlation (sleep today → HRV tomorrow)
  const sleepHrvPairs: { sleep: number; hrv: number }[] = [];
  const allDates = Array.from(sleepMap.keys()).sort();
  for (const date of allDates) {
    const sleep = sleepMap.get(date);
    if (sleep === undefined) continue;

    // Get next day's HRV
    const d = toLocalDayDate(date);
    d.setDate(d.getDate() + 1);
    const nextDayKey = toLocalDayKey(d.toISOString());
    const nextDayHRV = hrvMap.get(nextDayKey);

    if (nextDayHRV !== undefined) {
      sleepHrvPairs.push({ sleep, hrv: nextDayHRV });
    }
  }
  const sleepHrvLagCorrelation = calculatePearsonCorrelation(
    sleepHrvPairs.map((p) => p.sleep),
    sleepHrvPairs.map((p) => p.hrv),
  );

  // 3. Strain→Recovery correlation (strain today → HRV tomorrow) - should be negative
  const strainRecoveryPairs: { strain: number; hrv: number }[] = [];
  const strainDates = Array.from(strainMap.keys()).sort();
  for (const date of strainDates) {
    const strain = strainMap.get(date);
    if (strain === undefined) continue;

    const d = toLocalDayDate(date);
    d.setDate(d.getDate() + 1);
    const nextDayKey = toLocalDayKey(d.toISOString());
    const nextDayHRV = hrvMap.get(nextDayKey);

    if (nextDayHRV !== undefined) {
      strainRecoveryPairs.push({ strain, hrv: nextDayHRV });
    }
  }
  const strainRecoveryCorrelation = calculatePearsonCorrelation(
    strainRecoveryPairs.map((p) => p.strain),
    strainRecoveryPairs.map((p) => p.hrv),
  );

  return {
    hrvRhrCorrelation,
    sleepHrvLagCorrelation,
    strainRecoveryCorrelation,
    sampleSize: Math.min(hrvRhrPairs.length, sleepHrvPairs.length),
  };
}

// ============================================
// 15) ANOMALY DETECTION
// ============================================

export interface AnomalyResult {
  date: string;
  metric: string;
  value: number;
  zScore: number;
  severity: "warning" | "alert" | "critical";
}

export interface AnomalyMetrics {
  anomalies: AnomalyResult[];
  anomalyCount: number;
  hasRecentAnomaly: boolean;
  mostSevere: AnomalyResult | null;
}

const ANOMALY_THRESHOLDS = {
  warning: 2.0,
  alert: 2.5,
  critical: 3.0,
};

export function detectAnomalies(
  hrvData: DataPoint[],
  rhrData: DataPoint[],
  sleepData: DataPoint[],
  stressData: DataPoint[],
  baselineWindow: number = 30,
  lookbackDays: number = 7,
): AnomalyMetrics {
  const anomalies: AnomalyResult[] = [];

  const checkMetric = (
    data: DataPoint[],
    metricName: MetricName,
    displayName: string,
    invertDirection: boolean = false,
  ) => {
    const daily = toDailySeriesForMetric(data, metricName);
    const baseline = calculateBaselineMetrics(
      daily,
      baselineWindow,
      7,
      metricName,
    );
    const recent = filterDataByWindow(daily, lookbackDays).filter(
      (d) => d.value !== null,
    );

    if (baseline.std < MIN_STD_THRESHOLD) return;

    for (const d of recent) {
      if (d.value === null) continue;
      const rawZ = (d.value - baseline.mean) / baseline.std;
      const zScore = invertDirection ? -rawZ : rawZ;
      const absZ = Math.abs(zScore);

      if (absZ >= ANOMALY_THRESHOLDS.warning) {
        let severity: "warning" | "alert" | "critical" = "warning";
        if (absZ >= ANOMALY_THRESHOLDS.critical) severity = "critical";
        else if (absZ >= ANOMALY_THRESHOLDS.alert) severity = "alert";

        anomalies.push({
          date: d.date,
          metric: displayName,
          value: d.value,
          zScore,
          severity,
        });
      }
    }
  };

  checkMetric(hrvData, "hrv", "HRV", true); // Low HRV is bad
  checkMetric(rhrData, "rhr", "Resting HR", false); // High RHR is bad
  checkMetric(sleepData, "sleep", "Sleep", true); // Low sleep is bad
  checkMetric(stressData, "stress", "Stress", false); // High stress is bad

  // Sort by date descending, then by severity
  const severityOrder = { critical: 0, alert: 1, warning: 2 };
  anomalies.sort((a, b) => {
    const dateCompare = toTimeMs(b.date) - toTimeMs(a.date);
    if (dateCompare !== 0) return dateCompare;
    return severityOrder[a.severity] - severityOrder[b.severity];
  });

  const today = getLocalToday();
  const todayMs = today.getTime();
  const hasRecentAnomaly = anomalies.some((a) => {
    const anomalyDate = toLocalDayDate(toLocalDayKey(a.date));
    const daysDiff = (todayMs - anomalyDate.getTime()) / (1000 * 60 * 60 * 24);
    return daysDiff <= 2;
  });

  return {
    anomalies,
    anomalyCount: anomalies.length,
    hasRecentAnomaly,
    mostSevere:
      anomalies.find((a) => a.severity === "critical") ??
      anomalies.at(0) ??
      null,
  };
}

// ============================================
// 16) RATE OF CHANGE (VELOCITY) METRICS
// ============================================

export interface VelocityMetrics {
  hrvVelocity: number | null;
  rhrVelocity: number | null;
  weightVelocity: number | null;
  sleepVelocity: number | null;
  interpretation: {
    hrv: "improving" | "declining" | "stable" | null;
    rhr: "improving" | "declining" | "stable" | null;
    weight: "gaining" | "losing" | "stable" | null;
    sleep: "improving" | "declining" | "stable" | null;
  };
}

const VELOCITY_SIGNIFICANCE = {
  hrv: 0.5, // ms/day
  rhr: 0.3, // bpm/day
  weight: 0.02, // kg/day (~0.14 kg/week)
  sleep: 5, // min/day
};

export function calculateVelocityMetrics(
  hrvData: DataPoint[],
  rhrData: DataPoint[],
  weightData: DataPoint[],
  sleepData: DataPoint[],
  windowDays: number = 14,
): VelocityMetrics {
  const calculateSlope = (
    data: DataPoint[],
    metricName: MetricName,
  ): number | null => {
    const daily = toDailySeriesForMetric(data, metricName);
    const recent = filterDataByWindow(daily, windowDays).filter(
      (d) => d.value !== null,
    );

    if (recent.length < 7) return null;

    const points = recent.map((d) => ({
      x: toDayNumber(d.date),
      y: d.value!,
    }));

    const xMean = meanOrNull(points.map((p) => p.x)) ?? 0;
    const yMean = meanOrNull(points.map((p) => p.y)) ?? 0;

    let numerator = 0;
    let denominator = 0;
    for (const p of points) {
      const xDiff = p.x - xMean;
      numerator += xDiff * (p.y - yMean);
      denominator += xDiff * xDiff;
    }

    return denominator > 0 ? numerator / denominator : null;
  };

  const hrvVelocity = calculateSlope(hrvData, "hrv");
  const rhrVelocity = calculateSlope(rhrData, "rhr");
  const weightVelocity = calculateSlope(weightData, "weight");
  const sleepVelocity = calculateSlope(sleepData, "sleep");

  const interpretVelocity = (
    velocity: number | null,
    threshold: number,
    invertGood: boolean = false,
  ): "improving" | "declining" | "stable" | null => {
    if (velocity === null) return null;
    if (Math.abs(velocity) < threshold) return "stable";
    const isPositive = velocity > 0;
    const isGood = invertGood ? !isPositive : isPositive;
    return isGood ? "improving" : "declining";
  };

  return {
    hrvVelocity,
    rhrVelocity,
    weightVelocity,
    sleepVelocity,
    interpretation: {
      hrv: interpretVelocity(hrvVelocity, VELOCITY_SIGNIFICANCE.hrv),
      rhr: interpretVelocity(rhrVelocity, VELOCITY_SIGNIFICANCE.rhr, true), // Lower RHR is better
      weight:
        weightVelocity === null
          ? null
          : Math.abs(weightVelocity) < VELOCITY_SIGNIFICANCE.weight
            ? "stable"
            : weightVelocity > 0
              ? "gaining"
              : "losing",
      sleep: interpretVelocity(sleepVelocity, VELOCITY_SIGNIFICANCE.sleep),
    },
  };
}

// ============================================
// 17) RECOVERY CAPACITY
// ============================================

export interface RecoveryCapacityMetrics {
  avgRecoveryDays: number | null;
  recoveryEfficiency: number | null;
  highStrainEvents: number;
  recoveredEvents: number;
}

const HIGH_STRAIN_Z_THRESHOLD = 1.5;
const RECOVERY_LOOKBACK_DAYS = 7;
const RECOVERED_Z_THRESHOLD = -0.5;

export function calculateRecoveryCapacity(
  hrvData: DataPoint[],
  strainData: DataPoint[],
  baselineWindow: number = 30,
): RecoveryCapacityMetrics {
  const hrvBaseline = calculateBaselineMetrics(
    hrvData,
    baselineWindow,
    7,
    "hrv",
  );
  const strainBaseline = calculateBaselineMetrics(
    strainData,
    baselineWindow,
    7,
    "strain",
  );

  if (
    hrvBaseline.std < MIN_STD_THRESHOLD ||
    strainBaseline.std < MIN_STD_THRESHOLD
  ) {
    return {
      avgRecoveryDays: null,
      recoveryEfficiency: null,
      highStrainEvents: 0,
      recoveredEvents: 0,
    };
  }

  const dailyHRV = toDailySeries(hrvData, "mean");
  const dailyStrain = toDailySeries(strainData, "max");

  const hrvMap = new Map(
    dailyHRV
      .filter((d) => d.value !== null)
      .map((d) => [toLocalDayKey(d.date), d.value!]),
  );
  const strainMap = new Map(
    dailyStrain
      .filter((d) => d.value !== null)
      .map((d) => [toLocalDayKey(d.date), d.value!]),
  );

  const sortedStrainDates = Array.from(strainMap.keys()).sort();

  const recoveryTimes: number[] = [];
  const efficiencies: number[] = [];
  let highStrainEvents = 0;

  for (const date of sortedStrainDates) {
    const strain = strainMap.get(date)!;
    const strainZ = (strain - strainBaseline.mean) / strainBaseline.std;

    if (strainZ > HIGH_STRAIN_Z_THRESHOLD) {
      highStrainEvents++;

      const startDate = toLocalDayDate(date);
      const startHRV = hrvMap.get(date);
      const startHrvZ =
        startHRV !== undefined
          ? (startHRV - hrvBaseline.mean) / hrvBaseline.std
          : null;

      for (
        let dayOffset = 1;
        dayOffset <= RECOVERY_LOOKBACK_DAYS;
        dayOffset++
      ) {
        const checkDate = new Date(startDate);
        checkDate.setDate(checkDate.getDate() + dayOffset);
        const checkKey = toLocalDayKey(checkDate.toISOString());
        const checkHRV = hrvMap.get(checkKey);

        if (checkHRV !== undefined) {
          const hrvZ = (checkHRV - hrvBaseline.mean) / hrvBaseline.std;
          if (hrvZ >= RECOVERED_Z_THRESHOLD) {
            recoveryTimes.push(dayOffset);
            if (startHrvZ !== null) {
              efficiencies.push((hrvZ - startHrvZ) / strainZ);
            }
            break;
          }
        }
      }
    }
  }

  return {
    avgRecoveryDays:
      recoveryTimes.length > 0 ? meanOrNull(recoveryTimes) : null,
    recoveryEfficiency:
      efficiencies.length > 0 ? meanOrNull(efficiencies) : null,
    highStrainEvents,
    recoveredEvents: recoveryTimes.length,
  };
}

// ============================================
// 18) PRE-ILLNESS RISK SIGNAL
// ============================================

export interface IllnessRiskSignal {
  combinedDeviation: number | null;
  consecutiveDaysElevated: number;
  riskLevel: "low" | "moderate" | "high" | null;
  components: {
    hrvDrop: number | null;
    rhrRise: number | null;
    sleepDrop: number | null;
  };
}

const ILLNESS_RISK_THRESHOLDS = {
  moderate: 3.0,
  high: 5.0,
};
const ELEVATED_DAY_THRESHOLD = 1.5;

export function calculateIllnessRiskSignal(
  hrvData: DataPoint[],
  rhrData: DataPoint[],
  sleepData: DataPoint[],
  baselineWindow: number = 30,
  lookbackDays: number = 3,
): IllnessRiskSignal {
  const hrvBaseline = calculateBaselineMetrics(
    hrvData,
    baselineWindow,
    7,
    "hrv",
  );
  const rhrBaseline = calculateBaselineMetrics(
    rhrData,
    baselineWindow,
    7,
    "rhr",
  );
  const sleepBaseline = calculateBaselineMetrics(
    sleepData,
    baselineWindow,
    7,
    "sleep",
  );

  const dailyHRV = toDailySeries(hrvData, "mean");
  const dailyRHR = toDailySeries(rhrData, "mean");
  const dailySleep = toDailySeries(sleepData, "last");

  const recentHRV = filterDataByWindow(dailyHRV, lookbackDays);
  const recentRHR = filterDataByWindow(dailyRHR, lookbackDays);
  const recentSleep = filterDataByWindow(dailySleep, lookbackDays);

  const hrvValues = recentHRV
    .filter((d) => d.value !== null)
    .map((d) => d.value!);
  const rhrValues = recentRHR
    .filter((d) => d.value !== null)
    .map((d) => d.value!);
  const sleepValues = recentSleep
    .filter((d) => d.value !== null)
    .map((d) => d.value!);

  let hrvDrop: number | null = null;
  let rhrRise: number | null = null;
  let sleepDrop: number | null = null;

  if (hrvValues.length > 0 && hrvBaseline.std > MIN_STD_THRESHOLD) {
    const avgHRV = meanOrNull(hrvValues)!;
    hrvDrop = Math.max(0, -(avgHRV - hrvBaseline.mean) / hrvBaseline.std);
  }
  if (rhrValues.length > 0 && rhrBaseline.std > MIN_STD_THRESHOLD) {
    const avgRHR = meanOrNull(rhrValues)!;
    rhrRise = Math.max(0, (avgRHR - rhrBaseline.mean) / rhrBaseline.std);
  }
  if (sleepValues.length > 0 && sleepBaseline.std > MIN_STD_THRESHOLD) {
    const avgSleep = meanOrNull(sleepValues)!;
    sleepDrop = Math.max(
      0,
      -(avgSleep - sleepBaseline.mean) / sleepBaseline.std,
    );
  }

  const components = [hrvDrop, rhrRise, sleepDrop].filter((v) => v !== null);
  const combinedDeviation =
    components.length > 0 ? sumOrNull(components) : null;

  let consecutiveDaysElevated = 0;
  const allDates = new Set([
    ...recentHRV.map((d) => toLocalDayKey(d.date)),
    ...recentRHR.map((d) => toLocalDayKey(d.date)),
  ]);
  const sortedDates = Array.from(allDates).sort().reverse();

  const hrvMap = new Map(
    recentHRV
      .filter((d) => d.value !== null)
      .map((d) => [toLocalDayKey(d.date), d.value!]),
  );
  const rhrMap = new Map(
    recentRHR
      .filter((d) => d.value !== null)
      .map((d) => [toLocalDayKey(d.date), d.value!]),
  );

  for (const date of sortedDates) {
    const hrv = hrvMap.get(date);
    const rhr = rhrMap.get(date);
    let dayDeviation = 0;

    if (hrv !== undefined && hrvBaseline.std > MIN_STD_THRESHOLD) {
      dayDeviation += Math.max(0, -(hrv - hrvBaseline.mean) / hrvBaseline.std);
    }
    if (rhr !== undefined && rhrBaseline.std > MIN_STD_THRESHOLD) {
      dayDeviation += Math.max(0, (rhr - rhrBaseline.mean) / rhrBaseline.std);
    }

    if (dayDeviation >= ELEVATED_DAY_THRESHOLD) {
      consecutiveDaysElevated++;
    } else {
      break;
    }
  }

  let riskLevel: "low" | "moderate" | "high" | null = null;
  if (combinedDeviation !== null) {
    if (combinedDeviation >= ILLNESS_RISK_THRESHOLDS.high) {
      riskLevel = "high";
    } else if (combinedDeviation >= ILLNESS_RISK_THRESHOLDS.moderate) {
      riskLevel = "moderate";
    } else {
      riskLevel = "low";
    }
  }

  return {
    combinedDeviation,
    consecutiveDaysElevated,
    riskLevel,
    components: { hrvDrop, rhrRise, sleepDrop },
  };
}

// ============================================
// 19) HRV-RHR DECORRELATION ALERT
// ============================================

export interface DecorrelationAlert {
  isDecorrelated: boolean;
  currentCorrelation: number | null;
  baselineCorrelation: number | null;
  correlationDelta: number | null;
}

const DECORRELATION_BASELINE_THRESHOLD = -0.3;
const DECORRELATION_CURRENT_THRESHOLD = -0.15;

export function calculateDecorrelationAlert(
  hrvData: DataPoint[],
  rhrData: DataPoint[],
  recentWindow: number = 14,
  baselineWindow: number = 60,
): DecorrelationAlert {
  const recentCorr = calculateCorrelationMetrics(
    hrvData,
    rhrData,
    [],
    [],
    recentWindow,
  );
  const baselineCorr = calculateCorrelationMetrics(
    hrvData,
    rhrData,
    [],
    [],
    baselineWindow,
  );

  const current = recentCorr.hrvRhrCorrelation;
  const baseline = baselineCorr.hrvRhrCorrelation;

  let correlationDelta: number | null = null;
  let isDecorrelated = false;

  if (current !== null && baseline !== null) {
    correlationDelta = current - baseline;
    isDecorrelated =
      baseline < DECORRELATION_BASELINE_THRESHOLD &&
      current > DECORRELATION_CURRENT_THRESHOLD;
  }

  return {
    isDecorrelated,
    currentCorrelation: current,
    baselineCorrelation: baseline,
    correlationDelta,
  };
}
