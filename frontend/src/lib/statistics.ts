import {
  getLocalToday,
  toLocalDayKey,
  toLocalDayDate,
  toTimeMs,
} from "./health/date";
import {
  calculateMedian,
  meanOrNull,
  calculateStd,
  sumOrNull,
} from "./health/stats";

function getDaysBetween(date1: string, date2: string): number {
  const d1 = new Date(date1);
  const d2 = new Date(date2);
  return Math.abs(
    Math.round((d2.getTime() - d1.getTime()) / (1000 * 60 * 60 * 24)),
  );
}

export function calculateEMA<
  T extends { date: string } & Record<string, unknown>,
>(
  data: T[],
  period: number,
  valueKey: keyof T,
): (T & { ema: number | null })[] {
  if (data.length === 0) return [];

  const timescale = period;
  let ema: number | null = null;
  let prevValue: number | null = null;
  let prevDate: string | null = null;
  let validCount = 0;
  const warmupPeriod = Math.floor(period / 2);
  const maxGapDays = period * 2;

  return data.map((point) => {
    const value = point[valueKey] as number | null | undefined;
    const currentDate = point.date;

    if (value === null || value === undefined) {
      return { ...point, ema: null };
    }

    validCount++;

    if (ema === null || prevDate === null || prevValue === null) {
      ema = value;
      prevValue = value;
      prevDate = currentDate;
      return { ...point, ema: validCount < warmupPeriod ? null : ema };
    }

    const daysDelta = getDaysBetween(prevDate, currentDate);

    if (daysDelta > maxGapDays) {
      ema = value;
      validCount = 1;
      prevValue = value;
      prevDate = currentDate;
      return { ...point, ema: null };
    }

    if (daysDelta <= 0) {
      prevValue = value;
      prevDate = currentDate;
      return { ...point, ema: validCount < warmupPeriod ? null : ema };
    }

    const a = daysDelta / timescale;
    const u = Math.exp(-a);
    const v = (1 - u) / a;
    ema = u * ema + (v - u) * prevValue + (1 - v) * value;

    prevValue = value;
    prevDate = currentDate;

    if (validCount < warmupPeriod) {
      return { ...point, ema: null };
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
      .map((d) => d[valueKey] as number | null | undefined)
      .filter((v): v is number => v !== null && v !== undefined);

    if (values.length < window * 0.5) {
      return { ...point, sma: null };
    }

    const sum = sumOrNull(values) ?? 0;
    return { ...point, sma: sum / values.length };
  });
}

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
    .map((d) => d[valueKey] as number | null | undefined)
    .filter((v): v is number => v !== null && v !== undefined);

  if (values.length < windowDays * 0.5) {
    return null;
  }

  const mean = meanOrNull(values) ?? 0;
  const median = values.length > 0 ? calculateMedian(values) : mean;
  const deviation = calculateStd(values);

  return { baseline: mean, median, deviation };
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

function extractMeasurements<
  T extends { date: string } & Record<string, unknown>,
>(sortedData: T[], valueKey: keyof T, firstDate: Date): MeasurementPoint[] {
  const measurements: MeasurementPoint[] = [];
  for (const point of sortedData) {
    const value = point[valueKey] as number | null | undefined;
    if (value !== null && value !== undefined) {
      const date = new Date(point.date);
      const dayIndex = Math.round(
        (date.getTime() - firstDate.getTime()) / (1000 * 60 * 60 * 24),
      );
      measurements.push({ date, dateStr: point.date, value, dayIndex });
    }
  }
  return measurements;
}

function buildSmoothedByDay(
  measurements: MeasurementPoint[],
): Map<number, number> {
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
      smoothedByDay.set(day, catmullRomSpline(p0, p1, p2, p3, t));
    }
  }
  return smoothedByDay;
}

function resolveSmoothedWeight(
  dayIndex: number,
  smoothedByDay: Map<number, number>,
  firstMeasurement: MeasurementPoint,
  lastMeasurement: MeasurementPoint,
): number | null {
  const smoothed = smoothedByDay.get(dayIndex) ?? null;
  if (smoothed !== null) return smoothed;
  if (dayIndex < firstMeasurement.dayIndex) return firstMeasurement.value;
  if (dayIndex > lastMeasurement.dayIndex) return lastMeasurement.value;
  return null;
}

export function calculateBiologicalWeightSmoothing<
  T extends { date: string } & Record<string, unknown>,
>(data: T[], valueKey: keyof T): WeightSmoothedPoint[] {
  const sortedData = [...data].sort(
    (a, b) => toTimeMs(a.date) - toTimeMs(b.date),
  );

  if (sortedData.length === 0) {
    return [];
  }

  const firstDate = new Date(sortedData[0].date);
  const measurements = extractMeasurements(sortedData, valueKey, firstDate);

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

  const smoothedByDay = buildSmoothedByDay(measurements);
  const firstMeasurement = measurements[0];
  const lastMeasurement = measurements.at(-1) ?? measurements[0];

  return sortedData.map((point) => {
    const rawValue = point[valueKey] as number | null;
    const date = new Date(point.date);
    const dayIndex = Math.round(
      (date.getTime() - firstDate.getTime()) / (1000 * 60 * 60 * 24),
    );
    return {
      date: point.date,
      rawWeight: rawValue,
      smoothedWeight: resolveSmoothedWeight(
        dayIndex,
        smoothedByDay,
        firstMeasurement,
        lastMeasurement,
      ),
    };
  });
}

export interface LoessPoint {
  x: number;
  y: number;
  index: number;
}

const tricube = (d: number): number => {
  const absD = Math.abs(d);
  return absD < 1 ? Math.pow(1 - Math.pow(absD, 3), 3) : 0;
};

export function loessSmooth<
  T extends { date: string } & Record<string, unknown>,
>(
  data: T[],
  valueKey: keyof T,
  bandwidth: number = 0.25,
): (T & { loess: number | null })[] {
  const points: LoessPoint[] = [];

  for (let i = 0; i < data.length; i++) {
    const val = data[i][valueKey] as number | null;
    if (val !== null) {
      points.push({
        x: new Date(data[i].date).getTime(),
        y: val,
        index: i,
      });
    }
  }

  if (points.length < 3) {
    return data.map((d) => ({ ...d, loess: d[valueKey] as number | null }));
  }

  const windowSize = Math.max(3, Math.floor(points.length * bandwidth));
  const smoothed = new Map<number, number>();

  for (const target of points) {
    const distances = points
      .map((p) => ({ p, dist: Math.abs(p.x - target.x) }))
      .sort((a, b) => a.dist - b.dist)
      .slice(0, windowSize);

    const maxDist = distances.at(-1)?.dist ?? 1;

    let sumW = 0,
      sumWX = 0,
      sumWY = 0,
      sumWXX = 0,
      sumWXY = 0;

    for (const { p, dist } of distances) {
      const w = tricube(dist / maxDist);
      const dx = p.x - target.x;
      sumW += w;
      sumWX += w * dx;
      sumWY += w * p.y;
      sumWXX += w * dx * dx;
      sumWXY += w * dx * p.y;
    }

    const denom = sumW * sumWXX - sumWX * sumWX;
    smoothed.set(
      target.index,
      denom !== 0 ? (sumWXX * sumWY - sumWX * sumWXY) / denom : sumWY / sumW,
    );
  }

  return data.map((d, i) => ({ ...d, loess: smoothed.get(i) ?? null }));
}
