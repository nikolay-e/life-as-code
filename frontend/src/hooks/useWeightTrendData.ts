import { useCallback, useMemo } from "react";
import { calculateBiologicalWeightSmoothing } from "../lib/statistics";
import type { WeightData } from "../types/api";
import { useTrendData, type BaselineData } from "./useTrendData";
import { LOESS_BANDWIDTH_SHORT, LOESS_BANDWIDTH_LONG } from "../lib/constants";

interface WeightTrendOptions {
  bandwidthShort?: number;
  bandwidthLong?: number;
  showBaseline?: boolean;
  baselineWindow?: number;
}

export interface WeightTrendDataPoint {
  date: string;
  timestamp: number;
  rawWeight: number | null;
  smoothedWeight: number | null;
  trendShort: number | null;
  trendLong: number | null;
}

export type WeightBaselineData = BaselineData;

interface WeightTrendResult {
  chartData: WeightTrendDataPoint[];
  baseline: WeightBaselineData | null;
  minWeight: number;
  maxWeight: number;
  padding: number;
  hasData: boolean;
}

const WEIGHT_PADDING_FACTOR = 0.15;
const WEIGHT_PADDING_FALLBACK = 2;

export function useWeightTrendData(
  data: WeightData[],
  options: WeightTrendOptions = {},
): WeightTrendResult {
  const {
    bandwidthShort = LOESS_BANDWIDTH_SHORT,
    bandwidthLong = LOESS_BANDWIDTH_LONG,
    showBaseline = false,
    baselineWindow = 14,
  } = options;

  const preprocessor = useCallback((deduped: WeightData[]) => {
    const withWeights = deduped
      .filter((d) => d.weight_kg != null)
      .map((d) => ({ date: d.date, weight_kg: d.weight_kg as number }));
    return calculateBiologicalWeightSmoothing(withWeights, "weight_kg");
  }, []);

  const {
    chartData: rawChartData,
    baseline,
    hasData,
  } = useTrendData<WeightData>(data, "weight_kg", {
    method: "loess",
    bandwidthShort,
    bandwidthLong,
    showBaseline,
    baselineWindow,
    trendValueKey: "rawWeight",
    baselineValueKey: "rawWeight",
    preprocessor,
  });

  return useMemo(() => {
    if (!hasData) {
      return {
        chartData: [],
        baseline: null,
        minWeight: 0,
        maxWeight: 100,
        padding: 5,
        hasData: false,
      };
    }

    const validWeights: number[] = [];
    for (const d of rawChartData) {
      const raw = (d as unknown as Record<string, unknown>).rawWeight as
        | number
        | null;
      if (raw !== null) validWeights.push(raw);
    }

    if (validWeights.length === 0) {
      return {
        chartData: [],
        baseline: null,
        minWeight: 0,
        maxWeight: 100,
        padding: 5,
        hasData: false,
      };
    }

    const min = Math.min(...validWeights);
    const max = Math.max(...validWeights);
    const pad = (max - min) * WEIGHT_PADDING_FACTOR || WEIGHT_PADDING_FALLBACK;

    const chartData = rawChartData as unknown as WeightTrendDataPoint[];

    return {
      chartData,
      baseline,
      minWeight: min,
      maxWeight: max,
      padding: pad,
      hasData: true,
    };
  }, [rawChartData, baseline, hasData]);
}
