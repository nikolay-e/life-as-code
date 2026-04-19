import type { LucideIcon } from "lucide-react";
import type { HealthData } from "../../types/api";

export interface MetricData {
  date: string;
  value: number | null;
}

export type TrendMethod = "ema" | "sma";

export type AccumulatingMetricType = "steps" | "calories" | "strain" | "stress";

export type MetricAggregation = "last" | "mean" | "max" | "sum";

export type MetricName =
  | "hrv"
  | "rhr"
  | "sleep"
  | "stress"
  | "steps"
  | "strain"
  | "calories"
  | "weight"
  | "recovery"
  | "respiratory_rate"
  | "sleep_deep"
  | "sleep_rem"
  | "sleep_score"
  | "bed_temp"
  | "room_temp"
  | "sleep_latency"
  | "sleep_fitness"
  | "sleep_routine"
  | "sleep_quality_es"
  | "toss_and_turn";

export interface MetricDef {
  key: string;
  aliases?: string[];

  title: string;

  metricName: MetricName;
  aggregation: MetricAggregation;

  accumulating?: AccumulatingMetricType;

  icon: LucideIcon;
  iconColorClass: string;
  iconBgClass: string;
  colorVar: string;
  gradientId: string;

  trendMethod: TrendMethod;
  invertZScore: boolean;

  selectRaw(data: HealthData | null): MetricData[];
  format(value: number | null): string;
}

export interface MetricCardVM {
  key: string;
  title: string;
  value: string;
  subtitle: string;
  icon: LucideIcon;
  colorClass: string;
  bgClass: string;
}

export interface TrendConfig {
  method: TrendMethod;
  shortTermWindow: number;
  longTermWindow: number;
  longerTermWindow: number;
  baselineWindow: number;
  color: string;
  trendColor: string;
  longTermTrendColor: string;
  longerTermTrendColor: string;
  gradientId: string;
  colorVar: string;
}

export type TrendMode = "recent" | "quarter" | "year" | "all";
export type ViewMode = TrendMode | "today" | "custom";

export interface TrendModeConfig {
  label: string;
  rangeDays: number;
  shortTerm: number;
  longTerm: number;
  baseline: number;
  trendWindow: number;
  bandwidthShort: number;
  bandwidthLong: number;
  useShiftedZScore: boolean;
  description: string;
}

export interface SeriesResult {
  raw: MetricData[];
  daily: MetricData[];
  adjusted: MetricData[];
}

export interface DisplayValue {
  value: number | null;
  latestDate: string | null;
  usedFallback: boolean;
}
