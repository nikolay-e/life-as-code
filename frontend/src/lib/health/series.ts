import { toLocalDayKey, toTimeMs } from "./date";
import { filterDataByWindow, filterDataByWindowRange } from "./windows";

interface DataPoint {
  date: string;
  value: number | null;
}

export type AggregationMethod = "last" | "mean" | "max" | "sum";

export type MetricName =
  | "hrv"
  | "rhr"
  | "sleep"
  | "stress"
  | "steps"
  | "strain"
  | "calories"
  | "weight"
  | "recovery";

export const METRIC_AGGREGATION: Record<MetricName, AggregationMethod> = {
  hrv: "mean",
  rhr: "mean",
  sleep: "last",
  stress: "mean",
  steps: "last",
  strain: "max",
  calories: "last",
  weight: "last",
  recovery: "last",
};

export function toDailySeries(
  data: DataPoint[],
  method: AggregationMethod = "last",
): DataPoint[] {
  const sortedData = [...data]
    .filter((d) => d.value !== null)
    .sort((a, b) => toTimeMs(a.date) - toTimeMs(b.date));

  const dayMap = new Map<string, { values: number[]; lastTimestamp: number }>();

  for (const d of sortedData) {
    const dayKey = toLocalDayKey(d.date);
    const timestamp = toTimeMs(d.date);
    const existing = dayMap.get(dayKey) ?? { values: [], lastTimestamp: 0 };
    existing.values.push(d.value!);
    existing.lastTimestamp = Math.max(existing.lastTimestamp, timestamp);
    dayMap.set(dayKey, existing);
  }

  const result: DataPoint[] = [];
  for (const [date, { values }] of dayMap) {
    let aggregated: number;
    switch (method) {
      case "mean":
        aggregated = values.reduce((a, b) => a + b, 0) / values.length;
        break;
      case "max":
        aggregated = Math.max(...values);
        break;
      case "sum":
        aggregated = values.reduce((a, b) => a + b, 0);
        break;
      case "last":
      default:
        aggregated = values[values.length - 1];
        break;
    }
    result.push({ date, value: aggregated });
  }

  return result.sort((a, b) => toTimeMs(a.date) - toTimeMs(b.date));
}

export function toDailySeriesForMetric(
  data: DataPoint[],
  metric: MetricName,
): DataPoint[] {
  return toDailySeries(data, METRIC_AGGREGATION[metric]);
}

export function getWindowValues(
  data: DataPoint[],
  windowDays: number,
): number[] {
  const windowData = filterDataByWindow(data, windowDays).filter(
    (d) => d.value !== null,
  );
  return windowData.map((d) => d.value!);
}

export function getWindowRangeValues(
  data: DataPoint[],
  daysBack: number,
  daysBackEnd: number,
): number[] {
  const windowData = filterDataByWindowRange(
    data,
    daysBack,
    daysBackEnd,
  ).filter((d) => d.value !== null);
  return windowData.map((d) => d.value!);
}
