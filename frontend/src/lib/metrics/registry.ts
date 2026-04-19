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
  Wind,
  Thermometer,
  Star,
  Clock,
  RotateCcw,
  Award,
  Sparkles,
  Hash,
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
  return `${String(hours)}h ${String(mins)}m`;
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
  return Math.round(value).toLocaleString();
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
    title: "Calories Burned",
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
    format: (v) =>
      v === null ? "—" : `${Math.round(v).toLocaleString()} kcal`,
  },
  {
    key: "respiratory_rate",
    title: "Respiratory Rate",
    icon: Wind,
    colorVar: "--sleep",
    iconColorClass: "text-sleep",
    iconBgClass: "bg-sleep-muted",
    metricName: "respiratory_rate",
    aggregation: "mean",
    invertZScore: false,
    trendMethod: "ema",
    gradientId: "respiratoryRateGradient",
    selectRaw: (d) =>
      toMetricData(d?.eight_sleep_sessions ?? [], (r) => r.respiratory_rate),
    format: (v) => formatDefault(v, 1, "br/min"),
  },
  {
    key: "sleep_deep",
    title: "Deep Sleep",
    icon: Moon,
    colorVar: "--sleep",
    iconColorClass: "text-sleep",
    iconBgClass: "bg-sleep-muted",
    metricName: "sleep_deep",
    aggregation: "last",
    invertZScore: false,
    trendMethod: "ema",
    gradientId: "sleepDeepGradient",
    selectRaw: (d) => toMetricData(d?.sleep ?? [], (r) => r.deep_minutes),
    format: (v) => (v === null ? "—" : formatSleepMinutes(v)),
  },
  {
    key: "sleep_rem",
    title: "REM Sleep",
    icon: Brain,
    colorVar: "--sleep",
    iconColorClass: "text-sleep",
    iconBgClass: "bg-sleep-muted",
    metricName: "sleep_rem",
    aggregation: "last",
    invertZScore: false,
    trendMethod: "ema",
    gradientId: "sleepRemGradient",
    selectRaw: (d) => toMetricData(d?.sleep ?? [], (r) => r.rem_minutes),
    format: (v) => (v === null ? "—" : formatSleepMinutes(v)),
  },
  {
    key: "sleep_score",
    title: "Sleep Score",
    icon: Star,
    colorVar: "--sleep",
    iconColorClass: "text-sleep",
    iconBgClass: "bg-sleep-muted",
    metricName: "sleep_score",
    aggregation: "last",
    invertZScore: false,
    trendMethod: "ema",
    gradientId: "sleepScoreGradient",
    selectRaw: (d) =>
      toMetricData(d?.eight_sleep_sessions ?? [], (r) => r.score),
    format: (v) => formatDefault(v, 0, "/100"),
  },
  {
    key: "bed_temp",
    title: "Bed Temperature",
    icon: Thermometer,
    colorVar: "--heart",
    iconColorClass: "text-heart",
    iconBgClass: "bg-heart-muted",
    metricName: "bed_temp",
    aggregation: "last",
    invertZScore: false,
    trendMethod: "ema",
    gradientId: "bedTempGradient",
    selectRaw: (d) =>
      toMetricData(d?.eight_sleep_sessions ?? [], (r) => r.bed_temp_celsius),
    format: (v) => formatDefault(v, 1, "°C"),
  },
  {
    key: "room_temp",
    title: "Room Temperature",
    icon: Thermometer,
    colorVar: "--stress",
    iconColorClass: "text-stress",
    iconBgClass: "bg-stress-muted",
    metricName: "room_temp",
    aggregation: "last",
    invertZScore: false,
    trendMethod: "ema",
    gradientId: "roomTempGradient",
    selectRaw: (d) =>
      toMetricData(d?.eight_sleep_sessions ?? [], (r) => r.room_temp_celsius),
    format: (v) => formatDefault(v, 1, "°C"),
  },
  {
    key: "sleep_latency",
    title: "Sleep Latency",
    icon: Clock,
    colorVar: "--sleep",
    iconColorClass: "text-sleep",
    iconBgClass: "bg-sleep-muted",
    metricName: "sleep_latency",
    aggregation: "last",
    invertZScore: true,
    trendMethod: "ema",
    gradientId: "sleepLatencyGradient",
    selectRaw: (d) =>
      toMetricData(d?.eight_sleep_sessions ?? [], (r) =>
        r.latency_asleep_seconds === null
          ? null
          : Math.round(r.latency_asleep_seconds / 60),
      ),
    format: (v) => formatDefault(v, 0, "min"),
  },
  {
    key: "sleep_fitness",
    title: "Sleep Fitness",
    icon: Award,
    colorVar: "--sleep",
    iconColorClass: "text-sleep",
    iconBgClass: "bg-sleep-muted",
    metricName: "sleep_fitness",
    aggregation: "last",
    invertZScore: false,
    trendMethod: "ema",
    gradientId: "sleepFitnessGradient",
    selectRaw: (d) =>
      toMetricData(d?.eight_sleep_sessions ?? [], (r) => r.sleep_fitness_score),
    format: (v) => formatDefault(v, 0, "/100"),
  },
  {
    key: "sleep_routine",
    title: "Sleep Routine",
    icon: RotateCcw,
    colorVar: "--sleep",
    iconColorClass: "text-sleep",
    iconBgClass: "bg-sleep-muted",
    metricName: "sleep_routine",
    aggregation: "last",
    invertZScore: false,
    trendMethod: "ema",
    gradientId: "sleepRoutineGradient",
    selectRaw: (d) =>
      toMetricData(d?.eight_sleep_sessions ?? [], (r) => r.sleep_routine_score),
    format: (v) => formatDefault(v, 0, "/100"),
  },
  {
    key: "sleep_quality_es",
    title: "Sleep Quality",
    icon: Sparkles,
    colorVar: "--sleep",
    iconColorClass: "text-sleep",
    iconBgClass: "bg-sleep-muted",
    metricName: "sleep_quality_es",
    aggregation: "last",
    invertZScore: false,
    trendMethod: "ema",
    gradientId: "sleepQualityEsGradient",
    selectRaw: (d) =>
      toMetricData(d?.eight_sleep_sessions ?? [], (r) => r.sleep_quality_score),
    format: (v) => formatDefault(v, 0, "/100"),
  },
  {
    key: "toss_and_turn",
    title: "Toss & Turn",
    icon: Hash,
    colorVar: "--stress",
    iconColorClass: "text-stress",
    iconBgClass: "bg-stress-muted",
    metricName: "toss_and_turn",
    aggregation: "last",
    invertZScore: true,
    trendMethod: "ema",
    gradientId: "tossAndTurnGradient",
    selectRaw: (d) => toMetricData(d?.eight_sleep_sessions ?? [], (r) => r.tnt),
    format: (v) => formatDefault(v, 0, ""),
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

function validateMetricEntry(
  m: MetricDef,
  keysSeen: Set<string>,
  aliasesSeen: Set<string>,
): string[] {
  const errors: string[] = [];

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

  return errors;
}

function reportValidationErrors(errors: string[]): void {
  const msg = `METRIC_REGISTRY validation failed:\n${errors.join("\n")}`;
  if (import.meta.env.DEV) {
    throw new Error(msg);
  } else {
    console.error(`[METRIC_REGISTRY] ${msg}`);
  }
}

function validateRegistry(): void {
  const keysSeen = new Set<string>();
  const aliasesSeen = new Set<string>();
  const errors: string[] = [];

  for (const m of METRIC_REGISTRY) {
    errors.push(...validateMetricEntry(m, keysSeen, aliasesSeen));
  }

  if (errors.length > 0) {
    reportValidationErrors(errors);
  }
}

validateRegistry();
