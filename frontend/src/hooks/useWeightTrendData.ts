import { useMemo } from "react";
import { parseISO, startOfDay } from "date-fns";
import {
  calculateBiologicalWeightSmoothing,
  calculateBaseline,
  loessSmooth,
} from "../lib/statistics";
import type { WeightData } from "../types/api";

function dateToTimestamp(dateStr: string): number {
  return startOfDay(parseISO(dateStr)).getTime();
}

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

export interface WeightBaselineData {
  baseline: number;
  median: number;
  deviation: number;
}

interface WeightTrendResult {
  chartData: WeightTrendDataPoint[];
  baseline: WeightBaselineData | null;
  minWeight: number;
  maxWeight: number;
  padding: number;
  hasData: boolean;
}

export function useWeightTrendData(
  data: WeightData[],
  options: WeightTrendOptions = {},
): WeightTrendResult {
  const {
    bandwidthShort = 0.17,
    bandwidthLong = 0.33,
    showBaseline = false,
    baselineWindow = 14,
  } = options;

  return useMemo(() => {
    if (data.length === 0) {
      return {
        chartData: [],
        baseline: null,
        minWeight: 0,
        maxWeight: 100,
        padding: 5,
        hasData: false,
      };
    }

    const normalizedData = data.map((d) => ({
      date: d.date,
      weight_kg: d.weight_kg,
    }));

    const smoothedData = calculateBiologicalWeightSmoothing(
      normalizedData,
      "weight_kg",
    );

    const validWeights = smoothedData
      .filter(
        (d): d is typeof d & { rawWeight: number } => d.rawWeight !== null,
      )
      .map((d) => d.rawWeight);

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
    const pad = (max - min) * 0.15 || 2;

    const baseline = showBaseline
      ? calculateBaseline(normalizedData, baselineWindow, "weight_kg")
      : null;

    const dataForLoess = smoothedData as unknown as ({
      date: string;
    } & Record<string, unknown>)[];
    const loessShort = loessSmooth(dataForLoess, "rawWeight", bandwidthShort);
    const loessLong = loessSmooth(dataForLoess, "rawWeight", bandwidthLong);

    const chartData: WeightTrendDataPoint[] = smoothedData.map((d, i) => ({
      date: d.date,
      timestamp: dateToTimestamp(d.date),
      rawWeight: d.rawWeight,
      smoothedWeight: d.smoothedWeight,
      trendShort: loessShort[i]?.loess ?? null,
      trendLong: loessLong[i]?.loess ?? null,
    }));

    return {
      chartData,
      baseline,
      minWeight: min,
      maxWeight: max,
      padding: pad,
      hasData: true,
    };
  }, [data, bandwidthShort, bandwidthLong, showBaseline, baselineWindow]);
}
