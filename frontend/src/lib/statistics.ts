import { getLocalToday, toLocalDayKey, toLocalDayDate } from "./health/date";
import { calculateMedian } from "./health/stats";

export function calculateEMA<T extends Record<string, unknown>>(
  data: T[],
  period: number,
  valueKey: keyof T,
): (T & { ema: number | null })[] {
  const k = 2 / (period + 1);
  let ema: number | null = null;

  return data.map((point) => {
    const value = point[valueKey] as number | null;
    if (value === null || value === undefined) {
      return { ...point, ema: null };
    }

    if (ema === null) {
      ema = value;
    } else {
      ema = value * k + ema * (1 - k);
    }

    return { ...point, ema };
  });
}

export function calculateSMA<T extends Record<string, unknown>>(
  data: T[],
  window: number,
  valueKey: keyof T,
): (T & { sma: number | null })[] {
  return data.map((point, index) => {
    if (index < window - 1) {
      return { ...point, sma: null };
    }

    const values = data
      .slice(index - window + 1, index + 1)
      .map((d) => d[valueKey] as number | null)
      .filter((v): v is number => v !== null && v !== undefined);

    if (values.length < window * 0.5) {
      return { ...point, sma: null };
    }

    const sum = values.reduce((acc, val) => acc + val, 0);
    return { ...point, sma: sum / values.length };
  });
}

export { calculateMedian };

export function calculateBaseline<
  T extends { date: string } & Record<string, unknown>,
>(
  data: T[],
  windowDays: number,
  valueKey: keyof T,
): { baseline: number; median: number; deviation: number } | null {
  const today = getLocalToday();
  const windowStart = new Date(today);
  windowStart.setDate(windowStart.getDate() - (windowDays - 1));

  const windowData = data.filter((d) => {
    const dayKey = toLocalDayKey(d.date);
    const date = toLocalDayDate(dayKey);
    return date >= windowStart && date <= today;
  });

  const values = windowData
    .map((d) => d[valueKey] as number | null)
    .filter((v): v is number => v !== null && v !== undefined);

  if (values.length < windowDays * 0.5) {
    return null;
  }

  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const median = values.length > 0 ? calculateMedian(values) : mean;
  const variance =
    values.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0) /
    values.length;

  return { baseline: mean, median, deviation: Math.sqrt(variance) };
}

export interface WeightSmoothedPoint {
  date: string;
  rawWeight: number | null;
  smoothedWeight: number | null;
}

interface MeasurementPoint {
  date: Date;
  dateStr: string;
  value: number;
  dayIndex: number;
}

function catmullRomSpline(
  p0: number,
  p1: number,
  p2: number,
  p3: number,
  t: number,
  tension: number = 0.5,
): number {
  const t2 = t * t;
  const t3 = t2 * t;

  const m1 = tension * (p2 - p0);
  const m2 = tension * (p3 - p1);

  const a = 2 * p1 - 2 * p2 + m1 + m2;
  const b = -3 * p1 + 3 * p2 - 2 * m1 - m2;
  const c = m1;
  const d = p1;

  return a * t3 + b * t2 + c * t + d;
}

export function calculateBiologicalWeightSmoothing<
  T extends { date: string } & Record<string, unknown>,
>(
  data: T[],
  valueKey: keyof T,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  _options: {
    smoothingDays?: number;
    maxDailyChangeKg?: number;
  } = {},
): WeightSmoothedPoint[] {
  const sortedData = [...data].sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
  );

  if (sortedData.length === 0) {
    return [];
  }

  const measurements: MeasurementPoint[] = [];
  const firstDate = new Date(sortedData[0].date);

  for (const point of sortedData) {
    const value = point[valueKey] as number | null;
    if (value !== null && value !== undefined) {
      const date = new Date(point.date);
      const dayIndex = Math.round(
        (date.getTime() - firstDate.getTime()) / (1000 * 60 * 60 * 24),
      );
      measurements.push({ date, dateStr: point.date, value, dayIndex });
    }
  }

  if (measurements.length === 0) {
    return sortedData.map((d) => ({
      date: d.date,
      rawWeight: null,
      smoothedWeight: null,
    }));
  }

  if (measurements.length === 1) {
    return sortedData.map((d) => ({
      date: d.date,
      rawWeight: (d[valueKey] as number | null) ?? null,
      smoothedWeight: measurements[0].value,
    }));
  }

  const smoothedByDay = new Map<number, number>();

  for (let i = 0; i < measurements.length - 1; i++) {
    const curr = measurements[i];
    const next = measurements[i + 1];

    const p0 = i > 0 ? measurements[i - 1].value : curr.value;
    const p1 = curr.value;
    const p2 = next.value;
    const p3 =
      i < measurements.length - 2 ? measurements[i + 2].value : next.value;

    const startDay = curr.dayIndex;
    const endDay = next.dayIndex;
    const daySpan = endDay - startDay;

    if (daySpan <= 0) continue;

    for (let day = startDay; day <= endDay; day++) {
      const t = (day - startDay) / daySpan;
      const interpolated = catmullRomSpline(p0, p1, p2, p3, t);
      smoothedByDay.set(day, interpolated);
    }
  }

  const firstMeasurement = measurements[0];
  const lastMeasurement = measurements[measurements.length - 1];

  return sortedData.map((point) => {
    const rawValue = point[valueKey] as number | null;
    const date = new Date(point.date);
    const dayIndex = Math.round(
      (date.getTime() - firstDate.getTime()) / (1000 * 60 * 60 * 24),
    );

    let smoothedWeight: number | null = smoothedByDay.get(dayIndex) ?? null;

    if (smoothedWeight === null) {
      if (dayIndex < firstMeasurement.dayIndex) {
        smoothedWeight = firstMeasurement.value;
      } else if (dayIndex > lastMeasurement.dayIndex) {
        smoothedWeight = lastMeasurement.value;
      }
    }

    return {
      date: point.date,
      rawWeight: rawValue,
      smoothedWeight,
    };
  });
}
