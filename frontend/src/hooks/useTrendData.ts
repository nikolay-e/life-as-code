import { useMemo } from "react";
import {
  calculateEMA,
  calculateSMA,
  calculateBaseline,
} from "../lib/statistics";
import { sortByDateAsc } from "../lib/chart-utils";

type TrendMethod = "ema" | "sma";

interface TrendOptions {
  method?: TrendMethod;
  shortTermWindow?: number;
  longTermWindow?: number;
  longerTermWindow?: number;
  showBaseline?: boolean;
  baselineWindow?: number;
}

export interface TrendDataPoint {
  date: string;
  value: number | null;
  shortTermTrend: number | null;
  longTermTrend: number | null;
  longerTermTrend: number | null;
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
    method = "ema",
    shortTermWindow = 7,
    longTermWindow = 30,
    longerTermWindow = 90,
    showBaseline = false,
    baselineWindow = 14,
  } = options;

  return useMemo(() => {
    if (!data || data.length === 0) {
      return { chartData: [], baseline: null, hasData: false };
    }

    const sortedData = sortByDateAsc(data);

    const deduped = new Map<string, T>();
    for (const d of sortedData) {
      const dateKey = d.date.split("T")[0];
      deduped.set(dateKey, d);
    }

    const normalized = Array.from(deduped.values()).map((d) => ({
      ...d,
      date: d.date.split("T")[0],
      value: d[valueKey] as number | null,
    }));

    let withTrends: Array<
      (typeof normalized)[number] & {
        shortTrend: number | null;
        longTrend: number | null;
        longerTrend: number | null;
      }
    >;

    if (method === "ema") {
      const shortTermResult = calculateEMA(
        normalized,
        shortTermWindow,
        "value",
      );
      const longTermResult = calculateEMA(normalized, longTermWindow, "value");
      const longerTermResult = calculateEMA(
        normalized,
        longerTermWindow,
        "value",
      );

      withTrends = normalized.map((d, idx) => ({
        ...d,
        shortTrend: shortTermResult[idx]?.ema ?? null,
        longTrend: longTermResult[idx]?.ema ?? null,
        longerTrend: longerTermResult[idx]?.ema ?? null,
      }));
    } else {
      const shortTermResult = calculateSMA(
        normalized,
        shortTermWindow,
        "value",
      );
      const longTermResult = calculateSMA(normalized, longTermWindow, "value");
      const longerTermResult = calculateSMA(
        normalized,
        longerTermWindow,
        "value",
      );

      withTrends = normalized.map((d, idx) => ({
        ...d,
        shortTrend: shortTermResult[idx]?.sma ?? null,
        longTrend: longTermResult[idx]?.sma ?? null,
        longerTrend: longerTermResult[idx]?.sma ?? null,
      }));
    }

    const chartData = withTrends.map((d) => ({
      ...d,
      shortTermTrend: d.shortTrend,
      longTermTrend: d.longTrend,
      longerTermTrend: d.longerTrend,
    })) as (T & TrendDataPoint)[];

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
    longerTermWindow,
    showBaseline,
    baselineWindow,
  ]);
}
