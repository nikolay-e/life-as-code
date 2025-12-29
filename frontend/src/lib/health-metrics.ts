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
  const validDataInWindow = dataInWindow.filter(
    (d) => d.value !== null && d.value !== undefined,
  );
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

  const valuesInWindow = validDataInWindow.map((d) => d.value!);
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
      reason: `Day ${Math.round(completeness * 100)}% complete`,
    };
  }

  const filteredData = data.filter((d) => toLocalDayKey(d.date) !== today);

  return {
    useToday: false,
    adjustedData: filteredData,
    reason: `Day ${Math.round(completeness * 100)}% complete - using yesterday for ${metricType}`,
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

  const rawValues = baselineData.map((d) => d.value!);
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

  const shortTermValues = shortTermData.map((d) => d.value!);
  const shortTermMean =
    shortTermValues.length > 0
      ? shortTermValues.reduce((a, b) => a + b, 0) / shortTermValues.length
      : null;

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

  // FIX 3: Apply winsorize to trend values if option is set
  const rawTrendValues = trendData.map((d) => d.value!);
  const rawPrevTrendValues = prevTrendData.map((d) => d.value!);
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
          options?.winsorizeTrend ? [5, 95] : undefined,
        );
      } else {
        // Legacy: index-based regression
        const n = trendValues.length;
        const xMean = (n - 1) / 2;
        const yMean = trendValues.reduce((a, b) => a + b, 0) / n;
        let numerator = 0;
        let denominator = 0;
        for (let i = 0; i < n; i++) {
          numerator += (i - xMean) * (trendValues[i] - yMean);
          denominator += Math.pow(i - xMean, 2);
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
  const pts = points.filter((p) => p.value !== null);
  if (pts.length < 7) return null;

  const xs = pts.map((p) => toDayNumber(p.date));
  const ysRaw = pts.map((p) => p.value!);
  const ys = winsorizePct
    ? winsorize(ysRaw, winsorizePct[0], winsorizePct[1])
    : ysRaw;

  const xMean = xs.reduce((a, b) => a + b, 0) / xs.length;
  const yMean = ys.reduce((a, b) => a + b, 0) / ys.length;

  let num = 0;
  let den = 0;
  for (let i = 0; i < xs.length; i++) {
    num += (xs[i] - xMean) * (ys[i] - yMean);
    den += Math.pow(xs[i] - xMean, 2);
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
  const varianceLong =
    longValues.length > 1
      ? longValues.reduce((sum, v) => sum + Math.pow(v - meanLong, 2), 0) /
        (longValues.length - 1)
      : 0;
  const stdLong = Math.sqrt(varianceLong);
  const sleepCV = meanLong !== 0 ? stdLong / meanLong : 0;

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
  const stepsVariance =
    stepsLongValues.length > 1
      ? stepsLongValues.reduce(
          (sum, v) => sum + Math.pow(v - stepsMean, 2),
          0,
        ) /
        (stepsLongValues.length - 1)
      : 0;
  const stepsStd = Math.sqrt(stepsVariance);
  const stepsCV = stepsMean !== 0 ? stepsStd / stepsMean : 0;

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

  const allValues = dailyWeight.map((d) => d.value!);
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
  const std30 =
    last30.length > 1
      ? Math.sqrt(
          last30.reduce((sum, v) => sum + Math.pow(v - mean30, 2), 0) /
            (last30.length - 1),
        )
      : 0;
  const cv30 = mean30 !== 0 ? std30 / mean30 : 0;

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
