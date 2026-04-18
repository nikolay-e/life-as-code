import { useMemo } from "react";
import {
  calculateEMA,
  calculateSMA,
  calculateBaseline,
  loessSmooth,
} from "../lib/statistics";
import { sortByDateAsc, dateToTimestamp } from "../lib/chart-utils";
import { extractDatePart } from "../lib/health/date";
import { LOESS_BANDWIDTH_SHORT, LOESS_BANDWIDTH_LONG } from "../lib/constants";

type TrendMethod = "ema" | "sma" | "loess";

export interface TrendOptions<T extends { date: string }> {
  method?: TrendMethod;
  shortTermWindow?: number;
  longTermWindow?: number;
  showBaseline?: boolean;
  baselineWindow?: number;
  bandwidthShort?: number;
  bandwidthLong?: number;
  trendValueKey?: string;
  baselineValueKey?: string;
  preprocessor?: (
    deduped: T[],
  ) => ({ date: string } & Record<string, unknown>)[];
}

export interface TrendDataPoint {
  date: string;
  timestamp: number;
  value: number | null;
  trendShort: number | null;
  trendLong: number | null;
}

export type BaselineData = {
  baseline: number;
  median: number;
  deviation: number;
};

export interface TrendResult<T> {
  chartData: (T & TrendDataPoint)[];
  baseline: BaselineData | null;
  hasData: boolean;
}

function deduplicateByDate<T extends { date: string }>(sortedData: T[]): T[] {
  const deduped = new Map<string, T>();
  for (const d of sortedData) {
    deduped.set(extractDatePart(d.date), d);
  }
  return Array.from(deduped.values());
}

function computeTrends(
  data: ({ date: string } & Record<string, unknown>)[],
  trendKey: string,
  method: TrendMethod,
  shortTermWindow: number,
  longTermWindow: number,
  bandwidthShort: number,
  bandwidthLong: number,
): { trendShort: number | null; trendLong: number | null }[] {
  if (method === "loess") {
    const shortResult = loessSmooth(data, trendKey, bandwidthShort);
    const longResult = loessSmooth(data, trendKey, bandwidthLong);
    return data.map((_, idx) => ({
      trendShort: shortResult[idx]?.loess ?? null,
      trendLong: longResult[idx]?.loess ?? null,
    }));
  }

  if (method === "ema") {
    const shortResult = calculateEMA(data, shortTermWindow, trendKey);
    const longResult = calculateEMA(data, longTermWindow, trendKey);
    return data.map((_, idx) => ({
      trendShort: shortResult[idx]?.ema ?? null,
      trendLong: longResult[idx]?.ema ?? null,
    }));
  }

  const shortResult = calculateSMA(data, shortTermWindow, trendKey);
  const longResult = calculateSMA(data, longTermWindow, trendKey);
  return data.map((_, idx) => ({
    trendShort: shortResult[idx]?.sma ?? null,
    trendLong: longResult[idx]?.sma ?? null,
  }));
}

export function useTrendData<T extends { date: string }>(
  data: T[],
  valueKey: keyof T,
  options: TrendOptions<T> = {},
): TrendResult<T> {
  const {
    method = "loess",
    shortTermWindow = 7,
    longTermWindow = 30,
    showBaseline = false,
    baselineWindow = 14,
    bandwidthShort = LOESS_BANDWIDTH_SHORT,
    bandwidthLong = LOESS_BANDWIDTH_LONG,
    trendValueKey,
    baselineValueKey,
    preprocessor,
  } = options;

  return useMemo(() => {
    if (data.length === 0) {
      return { chartData: [], baseline: null, hasData: false };
    }

    const sortedData = sortByDateAsc(data);
    const dedupedData = deduplicateByDate(sortedData);

    const processed = preprocessor
      ? preprocessor(dedupedData)
      : (dedupedData as ({ date: string } & Record<string, unknown>)[]);

    const effectiveTrendKey = trendValueKey ?? "value";

    const normalized = processed.map((d) => {
      const dateOnly = extractDatePart(d.date);
      return {
        ...d,
        date: dateOnly,
        timestamp: dateToTimestamp(dateOnly),
        value: trendValueKey
          ? (d[trendValueKey] as number | null)
          : (d[valueKey as string] as number | null),
      };
    });

    const trends = computeTrends(
      normalized,
      effectiveTrendKey,
      method,
      shortTermWindow,
      longTermWindow,
      bandwidthShort,
      bandwidthLong,
    );

    const chartData = normalized.map((d, idx) => ({
      ...d,
      trendShort: trends[idx].trendShort,
      trendLong: trends[idx].trendLong,
    })) as (T & TrendDataPoint)[];

    const effectiveBaselineKey = baselineValueKey ?? (valueKey as string);
    const baselineInput = preprocessor ? processed : normalized;
    const baseline = showBaseline
      ? calculateBaseline(baselineInput, baselineWindow, effectiveBaselineKey)
      : null;

    const hasData = chartData.some((d) => d.value !== null);

    return { chartData, baseline, hasData };
  }, [
    data,
    valueKey,
    method,
    shortTermWindow,
    longTermWindow,
    showBaseline,
    baselineWindow,
    bandwidthShort,
    bandwidthLong,
    trendValueKey,
    baselineValueKey,
    preprocessor,
  ]);
}
