import type {
  HealthData,
  HRVData,
  SleepData,
  HeartRateData,
  WhoopRecoveryData,
  WhoopSleepData,
  WhoopCycleData,
  GarminTrainingStatusData,
} from "../types/api";
import { type DataProvider, PROVIDER_CONFIGS } from "./providers";
import { getLocalToday, toLocalDayKey, toLocalDayDate } from "./health/date";

// Re-export for backward compatibility
export type { DataProvider } from "./providers";

export interface UnifiedMetricPoint {
  date: string;
  value: number | null;
  zScore: number | null;
  garminValue: number | null;
  whoopValue: number | null;
  garminZScore: number | null;
  whoopZScore: number | null;
  provider: DataProvider;
  confidence: number;
}

export interface FusedHealthData {
  hrv: UnifiedMetricPoint[];
  sleep: UnifiedMetricPoint[];
  restingHr: UnifiedMetricPoint[];
  strain: UnifiedMetricPoint[];
  calories: UnifiedMetricPoint[];
}

interface ProviderValue {
  date: string;
  value: number | null;
}

interface SourceStats {
  mean: number;
  std: number;
  count: number;
  coverage: number;
}

interface PhysiologicalLimits {
  min: number;
  max: number;
  typicalMin: number;
  typicalMax: number;
}

const PHYSIOLOGICAL_LIMITS: Record<string, PhysiologicalLimits> = {
  hrv: { min: 5, max: 300, typicalMin: 15, typicalMax: 150 },
  sleep: { min: 0, max: 840, typicalMin: 240, typicalMax: 660 },
  restingHr: { min: 30, max: 120, typicalMin: 40, typicalMax: 90 },
  strain: { min: 0, max: 21, typicalMin: 0, typicalMax: 21 },
  calories: { min: 500, max: 10000, typicalMin: 1500, typicalMax: 4000 },
};

const MIN_OVERLAP_FOR_BLENDING = 7;
const MIN_OVERLAP_FOR_NORMALIZATION = 14;

function isPhysiologicallyValid(value: number, metricType: string): boolean {
  const limits = PHYSIOLOGICAL_LIMITS[metricType];
  if (!limits) return true;
  return value >= limits.min && value <= limits.max;
}

function calculateSourceStats(
  values: ProviderValue[],
  windowDays: number = 30,
): SourceStats {
  const today = getLocalToday();
  const windowStart = new Date(today);
  windowStart.setDate(windowStart.getDate() - (windowDays - 1));

  const windowValues = values.filter((v) => {
    if (v.value === null) return false;
    const dayKey = toLocalDayKey(v.date);
    const d = toLocalDayDate(dayKey);
    return d >= windowStart && d <= today;
  });

  const nums = windowValues.map((v) => v.value as number);
  if (nums.length === 0) {
    return { mean: 0, std: 1, count: 0, coverage: 0 };
  }

  const mean = nums.reduce((a, b) => a + b, 0) / nums.length;
  const variance =
    nums.length > 1
      ? nums.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) /
        (nums.length - 1)
      : 0;
  const std = Math.sqrt(variance) || 1;
  const coverage = Math.min(1, nums.length / windowDays);

  return { mean, std, count: nums.length, coverage };
}

function calculateSourceWeight(
  stats: SourceStats,
  value: number | null,
  metricType: string,
): number {
  if (stats.count === 0 || value === null) return 0;

  let weight = 1.0;

  if (stats.count < 7) weight *= 0.5;
  else if (stats.count < 14) weight *= 0.75;
  else if (stats.count < 21) weight *= 0.9;

  weight *= 0.3 + 0.7 * stats.coverage;

  if (!isPhysiologicallyValid(value, metricType)) {
    weight *= 0.1;
  }

  const zAbs = Math.abs((value - stats.mean) / stats.std);
  if (zAbs > 3) weight *= 0.3;
  else if (zAbs > 2) weight *= 0.6;
  else if (zAbs > 1.5) weight *= 0.8;

  return Math.max(0, Math.min(1, weight));
}

function getPercentile(value: number, sortedValues: number[]): number {
  if (sortedValues.length === 0) return 0.5;
  let count = 0;
  for (const v of sortedValues) {
    if (v < value) count++;
    else if (v === value) count += 0.5;
  }
  return count / sortedValues.length;
}

function getValueAtPercentile(
  percentile: number,
  sortedValues: number[],
): number {
  if (sortedValues.length === 0) return 0;
  const clampedP = Math.max(0, Math.min(1, percentile));
  const index = clampedP * (sortedValues.length - 1);
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return sortedValues[lower];
  const fraction = index - lower;
  return sortedValues[lower] * (1 - fraction) + sortedValues[upper] * fraction;
}

function normalizeGarminStrainToWhoopScale(
  garminValues: ProviderValue[],
  whoopValues: ProviderValue[],
): ProviderValue[] {
  const garminByDay = new Map(
    garminValues
      .filter((v) => v.value !== null)
      .map((v) => [toLocalDayKey(v.date), v.value as number]),
  );
  const whoopByDay = new Map(
    whoopValues
      .filter((v) => v.value !== null)
      .map((v) => [toLocalDayKey(v.date), v.value as number]),
  );

  const overlapGarmin: number[] = [];
  const overlapWhoop: number[] = [];
  for (const [dayKey, gVal] of garminByDay) {
    const wVal = whoopByDay.get(dayKey);
    if (wVal !== undefined) {
      overlapGarmin.push(gVal);
      overlapWhoop.push(wVal);
    }
  }

  if (overlapGarmin.length < MIN_OVERLAP_FOR_NORMALIZATION) {
    return garminValues;
  }

  const sortedOverlapGarmin = [...overlapGarmin].sort((a, b) => a - b);
  const sortedOverlapWhoop = [...overlapWhoop].sort((a, b) => a - b);

  return garminValues.map((gv) => {
    if (gv.value === null) return gv;
    const percentile = getPercentile(gv.value, sortedOverlapGarmin);
    const normalizedValue = getValueAtPercentile(
      percentile,
      sortedOverlapWhoop,
    );
    return { date: gv.date, value: normalizedValue };
  });
}

function blendedMerge(
  garminData: ProviderValue[],
  whoopData: ProviderValue[],
  metricType: string,
  normalizedGarminData?: ProviderValue[],
): UnifiedMetricPoint[] {
  const effectiveGarminData = normalizedGarminData ?? garminData;

  const garminStats = calculateSourceStats(effectiveGarminData);
  const whoopStats = calculateSourceStats(whoopData);

  const garminMap = new Map(
    effectiveGarminData
      .filter((v) => v.value !== null)
      .map((v) => [toLocalDayKey(v.date), v.value]),
  );
  const whoopMap = new Map(
    whoopData
      .filter((v) => v.value !== null)
      .map((v) => [toLocalDayKey(v.date), v.value]),
  );

  let overlapDays = 0;
  for (const dayKey of garminMap.keys()) {
    if (whoopMap.has(dayKey)) {
      overlapDays++;
    }
  }
  const hasEnoughOverlap = overlapDays >= MIN_OVERLAP_FOR_BLENDING;

  const allDates = new Set([...garminMap.keys(), ...whoopMap.keys()]);
  const result: UnifiedMetricPoint[] = [];

  for (const date of allDates) {
    const gVal = garminMap.get(date) ?? null;
    const wVal = whoopMap.get(date) ?? null;

    const gWeight = calculateSourceWeight(garminStats, gVal, metricType);
    const wWeight = calculateSourceWeight(whoopStats, wVal, metricType);

    let gZ: number | null = null;
    let wZ: number | null = null;

    if (gVal !== null && garminStats.std > 0) {
      gZ = (gVal - garminStats.mean) / garminStats.std;
    }
    if (wVal !== null && whoopStats.std > 0) {
      wZ = (wVal - whoopStats.mean) / whoopStats.std;
    }

    let fusedValue: number | null = null;
    let fusedZ: number | null = null;
    let confidence = 0;
    let provider: DataProvider = "garmin";

    const totalWeight = gWeight + wWeight;

    if (gVal !== null && wVal !== null && totalWeight > 0 && hasEnoughOverlap) {
      fusedValue = (gVal * gWeight + wVal * wWeight) / totalWeight;
      fusedZ =
        gZ !== null && wZ !== null
          ? (gZ * gWeight + wZ * wWeight) / totalWeight
          : (gZ ?? wZ);
      confidence = Math.min(1, totalWeight / 2);
      provider = "blended";
    } else if (gVal !== null && wVal !== null && !hasEnoughOverlap) {
      const preferWhoop = wWeight >= gWeight;
      fusedValue = preferWhoop ? wVal : gVal;
      fusedZ = preferWhoop ? wZ : gZ;
      confidence = Math.min(1, Math.max(gWeight, wWeight) * 0.6);
      provider = preferWhoop ? "whoop" : "garmin";
    } else if (gVal !== null) {
      fusedValue = gVal;
      fusedZ = gZ;
      confidence = Math.min(1, gWeight * 0.8);
      provider = "garmin";
    } else if (wVal !== null) {
      fusedValue = wVal;
      fusedZ = wZ;
      confidence = Math.min(1, wWeight * 0.8);
      provider = "whoop";
    }

    result.push({
      date,
      value: fusedValue,
      zScore: fusedZ,
      garminValue: gVal,
      whoopValue: wVal,
      garminZScore: gZ,
      whoopZScore: wZ,
      provider,
      confidence,
    });
  }

  return result.sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
  );
}

function extractProviderValues<T extends { date: string }>(
  items: T[],
  getValue: (item: T) => number | null,
): ProviderValue[] {
  return items.map((item) => ({
    date: item.date,
    value: getValue(item),
  }));
}

export function fuseHRVData(
  garminHRV: HRVData[],
  whoopRecovery: WhoopRecoveryData[],
): UnifiedMetricPoint[] {
  const garminValues = extractProviderValues(garminHRV, (d) => d.hrv_avg);
  const whoopValues = extractProviderValues(whoopRecovery, (d) => d.hrv_rmssd);
  return blendedMerge(garminValues, whoopValues, "hrv");
}

export function fuseSleepData(
  garminSleep: SleepData[],
  whoopSleep: WhoopSleepData[],
): UnifiedMetricPoint[] {
  const garminValues = extractProviderValues(
    garminSleep,
    (d) => d.total_sleep_minutes,
  );
  const whoopValues = extractProviderValues(
    whoopSleep,
    (d) => d.total_sleep_duration_minutes,
  );
  return blendedMerge(garminValues, whoopValues, "sleep");
}

export function fuseRestingHRData(
  garminHR: HeartRateData[],
  whoopRecovery: WhoopRecoveryData[],
): UnifiedMetricPoint[] {
  const garminValues = extractProviderValues(garminHR, (d) => d.resting_hr);
  const whoopValues = extractProviderValues(
    whoopRecovery,
    (d) => d.resting_heart_rate,
  );
  return blendedMerge(garminValues, whoopValues, "restingHr");
}

export function fuseStrainData(
  whoopCycles: WhoopCycleData[],
  garminTraining: GarminTrainingStatusData[],
): UnifiedMetricPoint[] {
  const whoopValues = extractProviderValues(whoopCycles, (d) => d.strain);
  const garminValues = extractProviderValues(
    garminTraining,
    (d) => d.acute_training_load,
  );

  const normalizedGarminValues = normalizeGarminStrainToWhoopScale(
    garminValues,
    whoopValues,
  );

  return blendedMerge(
    garminValues,
    whoopValues,
    "strain",
    normalizedGarminValues,
  );
}

export function fuseCaloriesData(
  garminTraining: GarminTrainingStatusData[],
  whoopCycles: WhoopCycleData[],
): UnifiedMetricPoint[] {
  const whoopKJToKcal = (kj: number | null) =>
    kj !== null ? Math.round(kj / 4.184) : null;

  const garminValues = extractProviderValues(
    garminTraining,
    (d) => d.total_kilocalories,
  );
  const whoopValues = extractProviderValues(whoopCycles, (d) =>
    whoopKJToKcal(d.kilojoules),
  );
  return blendedMerge(garminValues, whoopValues, "calories");
}

export function createFusedHealthData(data: HealthData): FusedHealthData {
  return {
    hrv: fuseHRVData(data.hrv, data.whoop_recovery),
    sleep: fuseSleepData(data.sleep, data.whoop_sleep),
    restingHr: fuseRestingHRData(data.heart_rate, data.whoop_recovery),
    strain: fuseStrainData(data.whoop_cycle, data.garmin_training_status),
    calories: fuseCaloriesData(data.garmin_training_status, data.whoop_cycle),
  };
}

export function getProviderCoverage(
  data: UnifiedMetricPoint[],
): Record<DataProvider, number> {
  // Initialize counts dynamically from provider registry
  const counts = Object.fromEntries(
    Object.keys(PROVIDER_CONFIGS).map((p) => [p, 0]),
  ) as Record<DataProvider, number>;

  for (const point of data) {
    counts[point.provider]++;
  }

  return counts;
}

export function getFusionStats(data: UnifiedMetricPoint[]): {
  total: number;
  garminOnly: number;
  whoopOnly: number;
  blended: number;
  avgConfidence: number;
  garminCoverage: number;
  whoopCoverage: number;
} {
  const garminOnly = data.filter(
    (d) => d.garminValue !== null && d.whoopValue === null,
  ).length;
  const whoopOnly = data.filter(
    (d) => d.whoopValue !== null && d.garminValue === null,
  ).length;
  const blended = data.filter(
    (d) => d.garminValue !== null && d.whoopValue !== null,
  ).length;
  const garminDays = data.filter((d) => d.garminValue !== null).length;
  const whoopDays = data.filter((d) => d.whoopValue !== null).length;

  const avgConfidence =
    data.length > 0
      ? data.reduce((sum, d) => sum + d.confidence, 0) / data.length
      : 0;

  return {
    total: data.length,
    garminOnly,
    whoopOnly,
    blended,
    avgConfidence,
    garminCoverage: data.length > 0 ? garminDays / data.length : 0,
    whoopCoverage: data.length > 0 ? whoopDays / data.length : 0,
  };
}

export function getDataSourceSummary(fusedData: FusedHealthData): {
  metric: string;
  total: number;
  garminOnly: number;
  whoopOnly: number;
  blended: number;
  avgConfidence: number;
}[] {
  const metrics: { name: string; data: UnifiedMetricPoint[] }[] = [
    { name: "HRV", data: fusedData.hrv },
    { name: "Sleep", data: fusedData.sleep },
    { name: "Resting HR", data: fusedData.restingHr },
    { name: "Strain", data: fusedData.strain },
    { name: "Calories", data: fusedData.calories },
  ];

  return metrics.map(({ name, data }) => {
    const stats = getFusionStats(data);
    return {
      metric: name,
      total: stats.total,
      garminOnly: stats.garminOnly,
      whoopOnly: stats.whoopOnly,
      blended: stats.blended,
      avgConfidence: stats.avgConfidence,
    };
  });
}
