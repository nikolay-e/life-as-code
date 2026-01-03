import { useMemo } from "react";
import { parseISO, startOfDay } from "date-fns";
import {
  calculateEMA,
  calculateSMA,
  calculateBaseline,
  loessSmooth,
} from "../lib/statistics";
import { sortByDateAsc } from "../lib/chart-utils";

function dateToTimestamp(dateStr: string): number {
  return startOfDay(parseISO(dateStr)).getTime();
}

type TrendMethod = "ema" | "sma" | "loess";

interface TrendOptions {
  method?: TrendMethod;
  shortTermWindow?: number;
  longTermWindow?: number;
  showBaseline?: boolean;
  baselineWindow?: number;
  bandwidthShort?: number;
  bandwidthLong?: number;
}

export interface TrendDataPoint {
  date: string;
  timestamp: number;
  value: number | null;
  trendShort: number | null;
  trendLong: number | null;
}

export type TrendChartData = TrendDataPoint;
export type BaselineData = {
  baseline: number;
  median: number;
  deviation: number;
};

interface TrendResult<T> {
  chartData: (T & TrendDataPoint)[];
  baseline: BaselineData | null;
  hasData: boolean;
}

export function useTrendData<T extends { date: string }>(
  data: T[],
  valueKey: keyof T,
  options: TrendOptions = {},
): TrendResult<T> {
  const {
    method = "loess",
    shortTermWindow = 7,
    longTermWindow = 30,
    showBaseline = false,
    baselineWindow = 14,
    bandwidthShort = 0.17,
    bandwidthLong = 0.33,
  } = options;

  return useMemo(() => {
    if (data.length === 0) {
      return { chartData: [], baseline: null, hasData: false };
    }

    const sortedData = sortByDateAsc(data);

    const deduped = new Map<string, T>();
    for (const d of sortedData) {
      const dateKey = d.date.split("T")[0];
      deduped.set(dateKey, d);
    }

    const normalized = Array.from(deduped.values()).map((d) => {
      const dateOnly = d.date.split("T")[0];
      return {
        ...d,
        date: dateOnly,
        timestamp: dateToTimestamp(dateOnly),
        value: d[valueKey] as number | null,
      };
    });

    let withTrends: Array<
      (typeof normalized)[number] & {
        trendShort: number | null;
        trendLong: number | null;
      }
    >;

    if (method === "loess") {
      const shortTermResult = loessSmooth(normalized, "value", bandwidthShort);
      const longTermResult = loessSmooth(normalized, "value", bandwidthLong);

      withTrends = normalized.map((d, idx) => ({
        ...d,
        trendShort: shortTermResult[idx]?.loess ?? null,
        trendLong: longTermResult[idx]?.loess ?? null,
      }));
    } else if (method === "ema") {
      const shortTermResult = calculateEMA(
        normalized,
        shortTermWindow,
        "value",
      );
      const longTermResult = calculateEMA(normalized, longTermWindow, "value");

      withTrends = normalized.map((d, idx) => ({
        ...d,
        trendShort: shortTermResult[idx]?.ema ?? null,
        trendLong: longTermResult[idx]?.ema ?? null,
      }));
    } else {
      const shortTermResult = calculateSMA(
        normalized,
        shortTermWindow,
        "value",
      );
      const longTermResult = calculateSMA(normalized, longTermWindow, "value");

      withTrends = normalized.map((d, idx) => ({
        ...d,
        trendShort: shortTermResult[idx]?.sma ?? null,
        trendLong: longTermResult[idx]?.sma ?? null,
      }));
    }

    const chartData = withTrends as (T & TrendDataPoint)[];

    const baseline = showBaseline
      ? calculateBaseline(normalized, baselineWindow, "value")
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
  ]);
}
