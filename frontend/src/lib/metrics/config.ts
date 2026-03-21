import type {
  TrendMode,
  TrendModeConfig,
  MetricDef,
  TrendConfig,
} from "./types";
import { METRIC_REGISTRY, resolveMetric } from "./registry";
import { LOESS_BANDWIDTH_SHORT, LOESS_BANDWIDTH_LONG } from "../constants";

export const TREND_MODES: Record<TrendMode, TrendModeConfig> = {
  recent: {
    label: "6W",
    rangeDays: 42,
    shortTerm: 7,
    longTerm: 14,
    baseline: 42,
    trendWindow: 7,
    bandwidthShort: LOESS_BANDWIDTH_SHORT,
    bandwidthLong: LOESS_BANDWIDTH_LONG,
    useShiftedZScore: false,
    description: "Daily",
  },
  quarter: {
    label: "6M",
    rangeDays: 180,
    shortTerm: 14,
    longTerm: 30,
    baseline: 90,
    trendWindow: 14,
    bandwidthShort: 0.08,
    bandwidthLong: 0.17,
    useShiftedZScore: true,
    description: "Training",
  },
  year: {
    label: "2Y",
    rangeDays: 730,
    shortTerm: 30,
    longTerm: 90,
    baseline: 180,
    trendWindow: 30,
    bandwidthShort: 0.04,
    bandwidthLong: 0.12,
    useShiftedZScore: true,
    description: "Seasonal",
  },
  all: {
    label: "5Y",
    rangeDays: 1825,
    shortTerm: 90,
    longTerm: 180,
    baseline: 365,
    trendWindow: 60,
    bandwidthShort: 0.05,
    bandwidthLong: 0.1,
    useShiftedZScore: true,
    description: "Lifetime",
  },
};

export const MODE_ORDER: TrendMode[] = ["recent", "quarter", "year", "all"];

export const MAX_BASELINE_DAYS = Math.max(
  ...MODE_ORDER.map((m) => TREND_MODES[m].baseline),
);

function normalizeCssVar(v: string): string {
  const trimmed = v.trim();
  if (trimmed.startsWith("--")) {
    return trimmed.split(/[\s,]/)[0];
  }
  if (trimmed.startsWith("var(")) {
    const inner = trimmed.slice(4).replace(/\)$/, "").trim();
    const varName = inner.split(/[\s,]/)[0];
    if (varName.startsWith("--")) return varName;
  }
  throw new Error(`Invalid CSS variable format: "${v}" (expected "--name")`);
}

export function getTrendConfig(def: MetricDef): TrendConfig {
  const normalizedVar = normalizeCssVar(def.colorVar);
  return {
    method: def.trendMethod,
    shortTermWindow: 7,
    longTermWindow: 30,
    longerTermWindow: 90,
    baselineWindow: 14,
    color: `hsl(var(${normalizedVar}))`,
    trendColor: `hsl(var(${normalizedVar}) / 0.6)`,
    longTermTrendColor: `hsl(var(${normalizedVar}) / 0.4)`,
    longerTermTrendColor: `hsl(var(${normalizedVar}) / 0.25)`,
    gradientId: def.gradientId,
    colorVar: normalizedVar,
  };
}

export function getTrendConfigByKey(
  keyOrAlias: string,
): TrendConfig | undefined {
  const def = resolveMetric(keyOrAlias);
  return def ? getTrendConfig(def) : undefined;
}

const trendConfigCache = new Map<string, TrendConfig>();
for (const m of METRIC_REGISTRY) {
  const config = getTrendConfig(m);
  trendConfigCache.set(m.key, config);
  for (const alias of m.aliases ?? []) {
    trendConfigCache.set(alias, config);
  }
}

export const TREND_CONFIGS: Readonly<Record<string, TrendConfig>> =
  Object.freeze(Object.fromEntries(trendConfigCache));
