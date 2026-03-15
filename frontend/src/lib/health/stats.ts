export const MIN_SAMPLE_SIZE = 10;
export const MIN_STD_THRESHOLD = 1e-6;
export const MAD_SCALE_FACTOR = 1.4826;

export function sumOrNull(values: number[]): number | null {
  return values.length > 0 ? values.reduce((a, b) => a + b, 0) : null;
}

export function meanOrNull(values: number[]): number | null {
  if (values.length === 0) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

export function calculatePercentile(
  sortedValues: number[],
  percentile: number,
): number {
  if (sortedValues.length === 0) return 0;
  const index = (percentile / 100) * (sortedValues.length - 1);
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return sortedValues[lower];
  return (
    sortedValues[lower] +
    (sortedValues[upper] - sortedValues[lower]) * (index - lower)
  );
}

export function winsorize(
  values: number[],
  lowerPercentile: number = 5,
  upperPercentile: number = 95,
): number[] {
  if (values.length < 4) return values;
  const sorted = [...values].sort((a, b) => a - b);
  const lowerBound = calculatePercentile(sorted, lowerPercentile);
  const upperBound = calculatePercentile(sorted, upperPercentile);
  return values.map((v) => Math.min(Math.max(v, lowerBound), upperBound));
}

export function calculateMedian(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0
    ? sorted[mid]
    : (sorted[mid - 1] + sorted[mid]) / 2;
}

export function calculateMAD(values: number[]): number {
  if (values.length < 2) return 0;
  const median = calculateMedian(values);
  const absoluteDeviations = values.map((v) => Math.abs(v - median));
  return calculateMedian(absoluteDeviations);
}

export interface RobustStats {
  median: number;
  mad: number;
  scaledMAD: number;
  mean: number;
  std: number;
}

export function calculateRobustStats(values: number[]): RobustStats {
  if (values.length === 0) {
    return { median: 0, mad: 0, scaledMAD: 0, mean: 0, std: 0 };
  }
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const variance =
    values.length > 1
      ? values.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) /
        (values.length - 1)
      : 0;
  const std = Math.sqrt(variance);
  const median = calculateMedian(values);
  const mad = calculateMAD(values);
  return {
    median,
    mad,
    scaledMAD: MAD_SCALE_FACTOR * mad,
    mean,
    std,
  };
}

export function calculateStd(values: number[]): number {
  if (values.length < 2) return 0;
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const variance =
    values.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) /
    (values.length - 1);
  return Math.sqrt(variance);
}

export function calculateEMAValue(
  values: number[],
  span: number,
): number | null {
  if (values.length === 0) return null;

  const k = 2 / (span + 1);
  let ema = values[0];

  for (let i = 1; i < values.length; i++) {
    ema = values[i] * k + ema * (1 - k);
  }

  return ema;
}
