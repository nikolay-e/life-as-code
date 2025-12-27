import {
  Activity,
  Moon,
  Heart,
  Brain,
  Footprints,
  Scale,
  Target,
  Zap,
  Flame,
  Dumbbell,
} from "lucide-react";
import type { MetricDef, MetricData } from "./types";

function toMetricData<T extends { date: string }>(
  data: T[],
  getValue: (row: T) => number | null,
): MetricData[] {
  return data.map((d) => ({ date: d.date, value: getValue(d) }));
}

function formatSleepMinutes(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  return `${hours}h ${mins}m`;
}

function formatDefault(
  value: number | null,
  decimals: number,
  unit: string,
): string {
  if (value === null) return "—";
  const formatted =
    decimals > 0 ? value.toFixed(decimals) : Math.round(value).toString();
  return unit ? `${formatted} ${unit}` : formatted;
}

function formatWithLocale(value: number | null): string {
  if (value === null) return "—";
  return value.toLocaleString();
}

function formatVolume(value: number | null): string {
  if (value === null) return "—";
  return `${(value / 1000).toFixed(1)}t`;
}

export const METRIC_REGISTRY: MetricDef[] = [
  {
    key: "hrv",
    title: "HRV",
    icon: Activity,
    colorVar: "--hrv",
    iconColorClass: "text-hrv",
    iconBgClass: "bg-hrv-muted",
    metricName: "hrv",
    aggregation: "mean",
    invertZScore: false,
    trendMethod: "ema",
    gradientId: "hrvGradient",
    selectRaw: (d) => toMetricData(d?.hrv ?? [], (r) => r.hrv_avg),
    format: (v) => formatDefault(v, 0, "ms"),
  },
  {
    key: "rhr",
    title: "Resting Heart Rate",
    icon: Heart,
    colorVar: "--heart",
    iconColorClass: "text-heart",
    iconBgClass: "bg-heart-muted",
    metricName: "rhr",
    aggregation: "last",
    invertZScore: true,
    trendMethod: "ema",
    gradientId: "heartGradient",
    selectRaw: (d) => toMetricData(d?.heart_rate ?? [], (r) => r.resting_hr),
    format: (v) => formatDefault(v, 0, "bpm"),
    aliases: ["heartRate"],
  },
  {
    key: "sleep",
    title: "Sleep Duration",
    icon: Moon,
    colorVar: "--sleep",
    iconColorClass: "text-sleep",
    iconBgClass: "bg-sleep-muted",
    metricName: "sleep",
    aggregation: "last",
    invertZScore: false,
    trendMethod: "ema",
    gradientId: "sleepGradient",
    selectRaw: (d) =>
      toMetricData(d?.sleep ?? [], (r) => r.total_sleep_minutes),
    format: (v) => (v === null ? "—" : formatSleepMinutes(v)),
  },
  {
    key: "stress",
    title: "Stress Level",
    icon: Brain,
    colorVar: "--stress",
    iconColorClass: "text-stress",
    iconBgClass: "bg-stress-muted",
    metricName: "stress",
    aggregation: "mean",
    accumulating: "stress",
    invertZScore: true,
    trendMethod: "ema",
    gradientId: "stressGradient",
    selectRaw: (d) => toMetricData(d?.stress ?? [], (r) => r.avg_stress),
    format: (v) => formatDefault(v, 0, ""),
  },
  {
    key: "steps",
    title: "Daily Steps",
    icon: Footprints,
    colorVar: "--steps",
    iconColorClass: "text-steps",
    iconBgClass: "bg-steps-muted",
    metricName: "steps",
    aggregation: "last",
    accumulating: "steps",
    invertZScore: false,
    trendMethod: "sma",
    gradientId: "stepsGradient",
    selectRaw: (d) => toMetricData(d?.steps ?? [], (r) => r.total_steps),
    format: formatWithLocale,
  },
  {
    key: "weight",
    title: "Weight",
    icon: Scale,
    colorVar: "--weight",
    iconColorClass: "text-weight",
    iconBgClass: "bg-weight-muted",
    metricName: "weight",
    aggregation: "last",
    invertZScore: true,
    trendMethod: "ema",
    gradientId: "weightGradient",
    selectRaw: (d) => toMetricData(d?.weight ?? [], (r) => r.weight_kg),
    format: (v) => formatDefault(v, 1, "kg"),
  },
  {
    key: "recovery",
    title: "Recovery",
    icon: Target,
    colorVar: "--whoop",
    iconColorClass: "text-whoop",
    iconBgClass: "bg-whoop-muted",
    metricName: "recovery",
    aggregation: "last",
    invertZScore: false,
    trendMethod: "ema",
    gradientId: "recoveryGradient",
    selectRaw: (d) =>
      toMetricData(d?.whoop_recovery ?? [], (r) => r.recovery_score),
    format: (v) => formatDefault(v, 0, "%"),
    aliases: ["whoopRecovery"],
  },
  {
    key: "strain",
    title: "Workout Strain",
    icon: Zap,
    colorVar: "--whoop-strain",
    iconColorClass: "text-whoop-strain",
    iconBgClass: "bg-whoop-strain-muted",
    metricName: "strain",
    aggregation: "max",
    accumulating: "strain",
    invertZScore: false,
    trendMethod: "ema",
    gradientId: "strainGradient",
    selectRaw: (d) => toMetricData(d?.whoop_workout ?? [], (r) => r.strain),
    format: (v) => formatDefault(v, 1, ""),
    aliases: ["whoopStrain"],
  },
  {
    key: "calories",
    title: "Daily Calories",
    icon: Flame,
    colorVar: "--calories",
    iconColorClass: "text-calories",
    iconBgClass: "bg-calories-muted",
    metricName: "calories",
    aggregation: "last",
    accumulating: "calories",
    invertZScore: false,
    trendMethod: "sma",
    gradientId: "caloriesGradient",
    selectRaw: (d) =>
      toMetricData(
        d?.garmin_training_status ?? [],
        (r) => r.total_kilocalories,
      ),
    format: (v) => (v === null ? "—" : `${v.toLocaleString()} kcal`),
  },
  {
    key: "dailyStrain",
    title: "Daily Strain",
    icon: Zap,
    colorVar: "--whoop-strain",
    iconColorClass: "text-whoop-strain",
    iconBgClass: "bg-whoop-strain-muted",
    metricName: "strain",
    aggregation: "max",
    accumulating: "strain",
    invertZScore: false,
    trendMethod: "ema",
    gradientId: "dailyStrainGradient",
    selectRaw: (d) => toMetricData(d?.whoop_cycle ?? [], (r) => r.strain),
    format: (v) => formatDefault(v, 1, ""),
  },
  {
    key: "volume",
    title: "Workout Volume",
    icon: Dumbbell,
    colorVar: "--workout",
    iconColorClass: "text-workout",
    iconBgClass: "bg-workout-muted",
    metricName: "volume",
    aggregation: "sum",
    invertZScore: false,
    trendMethod: "sma",
    gradientId: "volumeGradient",
    selectRaw: (d) => toMetricData(d?.workouts ?? [], (r) => r.total_volume),
    format: formatVolume,
    aliases: ["workout"],
  },
  {
    key: "sets",
    title: "Workout Sets",
    icon: Dumbbell,
    colorVar: "--workout",
    iconColorClass: "text-workout",
    iconBgClass: "bg-workout-muted",
    metricName: "sets",
    aggregation: "sum",
    invertZScore: false,
    trendMethod: "sma",
    gradientId: "setsGradient",
    selectRaw: (d) => toMetricData(d?.workouts ?? [], (r) => r.total_sets),
    format: (v) => formatDefault(v, 0, ""),
  },
];

export const METRIC_KEYS = METRIC_REGISTRY.map((m) => m.key);

const METRIC_BY_KEY = new Map<string, MetricDef>();
const ALIAS_TO_KEY = new Map<string, string>();

for (const m of METRIC_REGISTRY) {
  METRIC_BY_KEY.set(m.key, m);
  for (const alias of m.aliases ?? []) {
    ALIAS_TO_KEY.set(alias, m.key);
  }
}

export function resolveMetricKey(keyOrAlias: string): string | undefined {
  if (METRIC_BY_KEY.has(keyOrAlias)) {
    return keyOrAlias;
  }
  return ALIAS_TO_KEY.get(keyOrAlias);
}

export function resolveMetric(keyOrAlias: string): MetricDef | undefined {
  const key = resolveMetricKey(keyOrAlias);
  return key ? METRIC_BY_KEY.get(key) : undefined;
}

export function getMetricByKey(key: string): MetricDef | undefined {
  return METRIC_BY_KEY.get(key);
}

export { formatSleepMinutes };

function validateRegistry(): void {
  const errors: string[] = [];
  const keysSeen = new Set<string>();
  const aliasesSeen = new Set<string>();

  for (const m of METRIC_REGISTRY) {
    if (keysSeen.has(m.key)) {
      errors.push(`Duplicate key: ${m.key}`);
    }
    keysSeen.add(m.key);

    if (!m.colorVar.startsWith("--")) {
      errors.push(`Invalid colorVar for ${m.key}: expected "--name" format`);
    }

    if (!m.gradientId) {
      errors.push(`Missing gradientId for ${m.key}`);
    }

    for (const alias of m.aliases ?? []) {
      if (aliasesSeen.has(alias)) {
        errors.push(`Duplicate alias: ${alias}`);
      }
      aliasesSeen.add(alias);
    }
  }

  if (errors.length > 0) {
    const msg = `METRIC_REGISTRY validation failed:\n${errors.join("\n")}`;
    if (import.meta.env.DEV) {
      throw new Error(msg);
    } else {
      console.error(`[METRIC_REGISTRY] ${msg}`);
    }
  }
}

validateRegistry();
