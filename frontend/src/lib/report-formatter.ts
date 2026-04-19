import { format, parseISO } from "date-fns";
import type {
  HealthData,
  WorkoutExerciseDetail,
  AdvancedInsights,
  AnalyticsResponse,
  BiologicalAgeMetrics,
  DayMetrics,
  LongevityScore,
  TrainingZoneMetrics,
} from "../types/api";
import {
  formatDuration,
  formatPaceForReport,
  formatVolume,
} from "./formatters";
import { WHOOP_MAX_STRAIN, DEFAULT_ACTIVITY_NAME } from "./constants";

function n(v: number | null, d = 1): string {
  return v === null ? "N/A" : v.toFixed(d);
}

function pct(v: number | null): string {
  return v === null ? "N/A" : `${(v * 100).toFixed(1)}%`;
}

function mins(v: number | null): string {
  if (v === null) return "N/A";
  if (v < 0) return "0m";
  const total = Math.round(v);
  const h = Math.floor(total / 60);
  const m = total % 60;
  return h > 0 ? `${String(h)}h${String(m)}m` : `${String(m)}m`;
}

function fmtSteps(v: number | null): string {
  return v === null ? "" : Math.round(v).toLocaleString();
}

function delta(v: number | null, d = 0, suffix = ""): string {
  if (v === null) return "";
  return `(${v >= 0 ? "+" : ""}${v.toFixed(d)}${suffix})`;
}

function arrow(v: number | null): string {
  if (v === null) return "→";
  if (v > 0.01) return "↑";
  if (v < -0.01) return "↓";
  return "→";
}

function pad(s: string, len: number): string {
  return s.padEnd(len);
}

function isAllNull(...values: (number | string | null | undefined)[]): boolean {
  return values.every((v) => v === null || v === undefined);
}

function getAcwrStatus(acwr: number | null): string {
  if (acwr === null) return "N/A";
  if (acwr < 0.8) return "DETRAIN";
  if (acwr <= 1.3) return "OPTIMAL";
  if (acwr <= 1.5) return "CAUTION";
  return "INJURY";
}

function getImbalanceStatus(imbalance: number | null): string {
  if (imbalance === null) return "N/A";
  if (imbalance < -1) return "RECOVERED";
  if (imbalance < 0) return "BALANCED";
  if (imbalance < 1) return "MILD STRAIN";
  return "STRAINED";
}

function getReadiness(
  acwr: number | null,
  imbalance: number | null,
  illnessRisk: string | null,
): string {
  if (illnessRisk === "high") return "REST - illness risk detected";
  if (illnessRisk === "moderate") return "LIGHT ACTIVITY - monitor symptoms";
  if (acwr === null || imbalance === null) return "INSUFFICIENT DATA";
  if (acwr > 1.5) return "RECOVERY DAY - injury risk";
  if (imbalance < -1 && acwr >= 0.8 && acwr <= 1.3) return "READY FOR TRAINING";
  if (imbalance < -1 && acwr > 1.3) return "LIGHT SESSION - load high";
  if (imbalance < -1 && acwr < 0.8) return "INCREASE LOAD - well recovered";
  if (imbalance >= -1 && imbalance < 0 && acwr < 0.8) {
    return "MODERATE TRAINING - room to increase";
  }
  if (imbalance >= 0.5 || acwr > 1.3) return "RECOVERY DAY recommended";
  return "MODERATE ACTIVITY";
}

function formatToday(analytics: AnalyticsResponse, now: Date): string[] {
  const dod = analytics.day_over_day;
  const parts: string[] = [];

  if (dod.recovery.latest !== null) {
    parts.push(
      `Recovery: ${n(dod.recovery.latest, 0)}%${delta(dod.recovery.delta, 0)}`,
    );
  }
  if (dod.hrv.latest !== null) {
    parts.push(`HRV: ${n(dod.hrv.latest, 0)}ms${delta(dod.hrv.delta, 0)}`);
  }
  if (dod.rhr.latest !== null) {
    parts.push(`RHR: ${n(dod.rhr.latest, 0)}${delta(dod.rhr.delta, 0)}`);
  }
  if (dod.sleep.latest !== null) {
    parts.push(`Sleep: ${mins(dod.sleep.latest)}`);
  }
  if (dod.steps.latest !== null) {
    const incomplete =
      analytics.day_completeness < 1 ? `[${format(now, "HH:mm")}]` : "";
    parts.push(`Steps: ${fmtSteps(dod.steps.latest)}${incomplete}`);
  }
  if (dod.weight.latest !== null) {
    parts.push(
      `Weight: ${dod.weight.latest.toFixed(2)}kg${delta(dod.weight.delta, 2, "kg")}`,
    );
  }

  return [`## Today`, parts.join(" | ")];
}

function formatIllnessAlert(
  illness: AnalyticsResponse["illness_risk"],
): string | null {
  if (!illness.risk_level || illness.risk_level === "low") return null;
  const comp = illness.components;
  const parts = [
    `${String(illness.consecutive_days_elevated)}d elevated`,
    comp.hrv_drop === null ? null : `HRV↓${n(comp.hrv_drop, 2)}`,
    comp.rhr_rise === null ? null : `RHR↑${n(comp.rhr_rise, 2)}`,
  ]
    .filter(Boolean)
    .join(" ");
  return `⚠ Pre-Illness: ${illness.risk_level.toUpperCase()} (${parts})`;
}

function formatClinicalAlerts(
  clinical: AnalyticsResponse["clinical_alerts"],
): string | null {
  if (!clinical.any_alert) return null;
  const alerts: string[] = [];
  if (clinical.persistent_tachycardia) {
    alerts.push(`Tachycardia ${String(clinical.tachycardia_days)}d`);
  }
  if (clinical.acute_hrv_drop) {
    alerts.push(`HRV drop ${n(clinical.hrv_drop_percent, 0)}%`);
  }
  if (clinical.progressive_weight_loss) {
    alerts.push(`Weight loss ${n(clinical.weight_loss_percent, 1)}%`);
  }
  if (clinical.severe_overtraining) {
    alerts.push(`Overtraining score=${n(clinical.overtraining_score, 1)}`);
  }
  if (alerts.length === 0) return null;
  return `⚠ Clinical: ${alerts.join(" | ")}`;
}

function formatStatus(analytics: AnalyticsResponse): string[] {
  const acwr = analytics.activity_metrics.acwr;
  const imbalance = analytics.recovery_metrics.hrv_rhr_imbalance;
  const illness = analytics.illness_risk;
  const decor = analytics.decorrelation;
  const clinical = analytics.clinical_alerts;
  const overreaching = analytics.overreaching;

  const recommendation = getReadiness(acwr, imbalance, illness.risk_level);
  const lines: string[] = [
    `## Status`,
    `Readiness: ${recommendation} (ACWR: ${n(acwr)} ${getAcwrStatus(acwr)}, Imbalance: ${n(imbalance)} ${getImbalanceStatus(imbalance)})`,
  ];

  const illnessAlert = formatIllnessAlert(illness);
  if (illnessAlert) {
    lines.push(illnessAlert);
  }

  if (decor.is_decorrelated) {
    lines.push(
      `⚠ HRV-RHR Decorrelation: r=${n(decor.current_correlation, 3)} (baseline: ${n(decor.baseline_correlation, 3)})`,
    );
  }

  const clinicalAlert = formatClinicalAlerts(clinical);
  if (clinicalAlert) {
    lines.push(clinicalAlert);
  }

  if (overreaching.risk_level && overreaching.risk_level !== "low") {
    lines.push(
      `⚠ Overreaching: ${overreaching.risk_level.toUpperCase()} (score=${n(overreaching.score, 1)}, low recovery ${String(overreaching.consecutive_low_recovery_days)}d)`,
    );
  }

  return lines;
}

function formatDayTableRow(day: DayMetrics): string {
  const dateStr = format(parseISO(day.date), "MMM d(EEE)");
  const rec = day.recovery === null ? "" : `${day.recovery.toFixed(0)}%`;
  const hrv = day.hrv === null ? "" : day.hrv.toFixed(0);
  const rhr = day.rhr === null ? "" : day.rhr.toFixed(0);
  const slp = day.sleep === null ? "" : mins(day.sleep);
  const stp = day.steps === null ? "" : fmtSteps(day.steps);
  const str = day.strain === null ? "" : day.strain.toFixed(1);
  const strs = day.stress === null ? "" : day.stress.toFixed(0);
  const cal = day.calories === null ? "" : day.calories.toFixed(0);
  const wt = day.weight === null ? "" : day.weight.toFixed(1);
  return `| ${pad(dateStr, 10)} | ${pad(rec, 4)} | ${pad(hrv, 3)} | ${pad(rhr, 3)} | ${pad(slp, 5)} | ${pad(stp, 6)} | ${pad(str, 4)} | ${pad(strs, 4)} | ${pad(cal, 5)} | ${pad(wt, 4)} |`;
}

function formatLastDays(lastDays: DayMetrics[]): string[] {
  const lines: string[] = [
    `## Last ${String(lastDays.length)} Days`,
    `| Date       | Rec% | HRV | RHR | Sleep | Steps  | Str  | Strs | Burn  | Wt   |`,
    `|------------|------|-----|-----|-------|--------|------|------|-------|------|`,
  ];
  for (const day of lastDays) {
    lines.push(formatDayTableRow(day));
  }
  return lines;
}

function formatBioAge(
  bio: BiologicalAgeMetrics,
  score: LongevityScore,
): string | null {
  if (bio.composite_biological_age === null && score.overall === null) {
    return null;
  }
  if (bio.composite_biological_age !== null) {
    const scoreStr =
      score.overall === null ? "" : ` | Score: ${score.overall.toFixed(0)}/100`;
    return `Bio Age: ${bio.composite_biological_age.toFixed(1)}y (chrono: ${String(bio.chronological_age)}, Δ=${n(bio.age_delta, 1)}y)${scoreStr}`;
  }
  return `Score: ${(score.overall ?? 0).toFixed(0)}/100`;
}

function formatZoneMinutes(zones: TrainingZoneMetrics): string | null {
  if (zones.zone2_minutes_7d === null && zones.zone5_minutes_7d === null) {
    return null;
  }
  const z2target = zones.zone2_target_met ? " ✓" : " ✗";
  const z2 =
    zones.zone2_minutes_7d === null
      ? ""
      : `Zone2: ${String(Math.round(zones.zone2_minutes_7d))}min/7d${z2target}`;
  const z5target = zones.zone5_target_met ? " ✓" : " ✗";
  const z5 =
    zones.zone5_minutes_7d === null
      ? ""
      : `Zone5: ${String(Math.round(zones.zone5_minutes_7d))}min/7d${z5target}`;
  return [z2, z5].filter(Boolean).join(" | ");
}

function formatLongevity(analytics: AnalyticsResponse): string[] {
  const longevity = analytics.longevity_insights;
  if (!longevity) return [];

  const bio = longevity.biological_age;
  const zones = longevity.training_zones;
  const score = longevity.longevity_score;

  const lines: string[] = [`## Longevity`];

  const bioLine = formatBioAge(bio, score);
  if (bioLine) {
    lines.push(bioLine);
  }

  if (bio.components.length > 0) {
    const comps = bio.components
      .filter((c) => c.estimated_age !== null)
      .map((c) => `${c.name}→${(c.estimated_age ?? 0).toFixed(0)}y`)
      .join(" ");
    if (comps) {
      lines.push(`Components: ${comps}`);
    }
  }

  const zoneLine = formatZoneMinutes(zones);
  if (zoneLine) {
    lines.push(zoneLine);
  }

  const scoreParts = [
    score.cardiorespiratory === null
      ? null
      : `cardio=${score.cardiorespiratory.toFixed(0)}`,
    score.recovery_resilience === null
      ? null
      : `recovery=${score.recovery_resilience.toFixed(0)}`,
    score.sleep_optimization === null
      ? null
      : `sleep=${score.sleep_optimization.toFixed(0)}`,
    score.body_composition === null
      ? null
      : `body=${score.body_composition.toFixed(0)}`,
    score.activity_consistency === null
      ? null
      : `activity=${score.activity_consistency.toFixed(0)}`,
  ].filter(Boolean);
  if (scoreParts.length > 0) {
    lines.push(`Breakdown: ${scoreParts.join(" ")}`);
  }

  return lines;
}

function formatTrendsTable(
  allAnalytics: Partial<Record<string, AnalyticsResponse>>,
): string[] {
  const modes = ["recent", "quarter", "year", "all"] as const;

  const row = (
    name: string,
    key: string,
    fmt: (v: number | null) => string,
  ): string => {
    const vals = modes.map((m) => {
      const b = allAnalytics[m]?.metric_baselines[key];
      return b?.short_term_mean ?? null;
    });

    const recent = allAnalytics.recent?.metric_baselines[key];
    const trendSlope = recent?.trend_slope ?? null;
    const percentile = recent?.percentile ?? null;

    const trendPrefix = trendSlope !== null && trendSlope >= 0 ? "+" : "";
    const trend =
      trendSlope === null
        ? ""
        : `${trendPrefix}${trendSlope.toFixed(2)}/d ${arrow(trendSlope)}`;
    const pctl = percentile === null ? "" : percentile.toFixed(0);

    return `| ${pad(name, 10)} | ${pad(fmt(vals[0]), 6)} | ${pad(fmt(vals[1]), 6)} | ${pad(fmt(vals[2]), 6)} | ${pad(fmt(vals[3]), 6)} | ${pad(trend, 12)} | ${pad(pctl, 4)} |`;
  };

  return [
    `## Trends`,
    `| Metric     | 6W     | 6M     | 2Y     | 5Y     | Trend        | %ile |`,
    `|------------|--------|--------|--------|--------|--------------|------|`,
    row("HRV (ms)", "hrv", (v) => (v === null ? "" : v.toFixed(1))),
    row("RHR (bpm)", "rhr", (v) => (v === null ? "" : v.toFixed(1))),
    row("Sleep", "sleep", (v) => (v === null ? "" : mins(v))),
    row("Steps", "steps", (v) => (v === null ? "" : fmtSteps(v))),
    row("Weight(kg)", "weight", (v) => (v === null ? "" : v.toFixed(1))),
    row("Recovery%", "recovery", (v) => (v === null ? "" : v.toFixed(0))),
  ];
}

function formatAnomalies(analytics: AnalyticsResponse): string[] {
  const a = analytics.anomalies;
  if (!a.has_recent_anomaly || a.anomalies.length === 0) return [];

  const lines: string[] = [`## Anomalies`];
  for (const anomaly of a.anomalies.slice(0, 5)) {
    const dateStr = format(parseISO(anomaly.date), "MMM d");
    lines.push(
      `${dateStr}: ${anomaly.metric} ${anomaly.value.toFixed(1)} z=${anomaly.z_score.toFixed(1)} ${anomaly.severity.toUpperCase()}`,
    );
  }
  return lines;
}

function formatWeightDelta(periodChange: number | null): string {
  if (periodChange === null) return "";
  const sign = periodChange >= 0 ? "+" : "";
  return `${sign}${periodChange.toFixed(2)}`;
}

function formatTimeframeTable(
  allAnalytics: Partial<Record<string, AnalyticsResponse>>,
): string[] {
  const modes = ["recent", "quarter", "year", "all"] as const;
  const labels = ["6W", "6M", "2Y", "5Y"];

  const val = (
    mode: (typeof modes)[number],
    getter: (a: AnalyticsResponse) => string,
  ): string => {
    const data = allAnalytics[mode];
    return data ? getter(data) : "";
  };

  const row = (
    name: string,
    getter: (a: AnalyticsResponse) => string,
  ): string => {
    const vals = modes.map((m) => val(m, getter));
    return `| ${pad(name, 15)} | ${pad(vals[0], 6)} | ${pad(vals[1], 6)} | ${pad(vals[2], 6)} | ${pad(vals[3], 6)} |`;
  };

  return [
    `## Timeframes`,
    `| Metric          | ${labels.map((l) => pad(l, 6)).join(" | ")} |`,
    `|-----------------|--------|--------|--------|--------|`,
    row("Recovery CV", (a) =>
      a.recovery_metrics.recovery_cv === null
        ? ""
        : pct(a.recovery_metrics.recovery_cv),
    ),
    row("Stress Load", (a) => n(a.recovery_metrics.stress_load_short, 0)),
    row("Sleep Debt", (a) => mins(a.sleep_metrics.sleep_debt_short)),
    row("Sleep Surplus", (a) => mins(a.sleep_metrics.sleep_surplus_short)),
    row("Sleep CV", (a) => `${(a.sleep_metrics.sleep_cv * 100).toFixed(1)}%`),
    row("Acute Load", (a) => n(a.activity_metrics.acute_load, 1)),
    row("ACWR", (a) => n(a.activity_metrics.acwr)),
    row("Weight EMA(kg)", (a) =>
      a.weight_metrics.ema_short === null
        ? ""
        : a.weight_metrics.ema_short.toFixed(1),
    ),
    row("Weight Δ(kg)", (a) =>
      formatWeightDelta(a.weight_metrics.period_change),
    ),
  ];
}

function formatHealthScore(analytics: AnalyticsResponse): string[] {
  const hs = analytics.health_score;
  if (hs.overall === null) return [];

  const lines = [
    `## Health Score: ${n(hs.overall, 2)}`,
    `Recovery Core (60%): ${n(hs.recovery_core, 2)} | Training (20%): ${n(hs.training_load, 2)} | Behavior (20%): ${n(hs.behavior_support, 2)}`,
  ];

  const scored = hs.contributors.filter((c) => c.goodness_z_score !== null);
  if (scored.length > 0) {
    const sorted = [...scored].sort(
      (a, b) => (b.goodness_z_score ?? 0) - (a.goodness_z_score ?? 0),
    );
    const top = sorted[0];
    const worst = sorted.at(-1)!;
    const topStr = `Top: ${top.name} z=${n(top.goodness_z_score, 1)} ${(top.confidence * 100).toFixed(0)}%`;
    const gatedSuffix = worst.is_gated ? " [GATED]" : "";
    const worstStr = `Worst: ${worst.name} z=${n(worst.goodness_z_score, 1)} ${(worst.confidence * 100).toFixed(0)}%${gatedSuffix}`;
    lines.push(`${topStr} | ${worstStr}`);
  }

  return lines;
}

function formatEnergyBalance(analytics: AnalyticsResponse): string[] {
  const eb = analytics.energy_balance;
  const cal = analytics.calories_metrics;

  if (
    eb.balance_signal === null &&
    cal.avg_7 === null &&
    eb.weight_delta === null
  ) {
    return [];
  }

  const parts: string[] = [];
  if (cal.avg_7 !== null) {
    parts.push(`cal avg ${cal.avg_7.toFixed(0)}`);
  }
  if (cal.trend) {
    parts.push(`trend ${cal.trend}`);
  }
  if (eb.weight_delta !== null) {
    const sign = eb.weight_delta >= 0 ? "+" : "";
    parts.push(`weight ${sign}${eb.weight_delta.toFixed(2)}kg/7d`);
  }
  if (eb.balance_signal) {
    parts.push(eb.balance_signal.replaceAll("_", " "));
  }

  return [`## Energy`, `Energy: ${parts.join(", ")}`];
}

interface DayAggregatedWorkout {
  date: string;
  activities: string[];
  totalStrain: number;
  peakHr: number | null;
  totalVolume: number;
  totalSets: number;
  duration: string;
  distance: string;
  notes: string[];
}

function createEmptyDayWorkout(date: string): DayAggregatedWorkout {
  return {
    date,
    activities: [],
    totalStrain: 0,
    peakHr: null,
    totalVolume: 0,
    totalSets: 0,
    duration: "",
    distance: "",
    notes: [],
  };
}

const ACTIVITY_ALIASES: Record<string, string> = {
  "assault-bike": "Indoor Cycling",
  "assault bike": "Indoor Cycling",
  cycling: "Indoor Cycling",
  "functional fitness": "Strength",
  weightlifting: "Strength",
};

function normalizeActivityName(name: string): string {
  const lower = name.toLowerCase().trim();
  if (ACTIVITY_ALIASES[lower]) return ACTIVITY_ALIASES[lower];
  return name.trim().charAt(0).toUpperCase() + name.trim().slice(1);
}

function addUniqueActivity(day: DayAggregatedWorkout, name: string): void {
  const normalized = normalizeActivityName(name);
  const exists = day.activities.some(
    (a) => a.toLowerCase() === normalized.toLowerCase(),
  );
  if (!exists) {
    day.activities.push(normalized);
  }
}

function updatePeakHr(day: DayAggregatedWorkout, hr: number): void {
  day.peakHr = day.peakHr === null ? hr : Math.max(day.peakHr, hr);
}

function aggregateDetailedWorkouts(
  detailedWorkouts: WorkoutExerciseDetail[],
  byDate: Map<string, DayAggregatedWorkout>,
  thirtyDaysAgo: Date,
  now: Date,
): void {
  for (const w of detailedWorkouts) {
    const wDate = parseISO(w.date);
    if (wDate < thirtyDaysAgo || wDate > now) continue;
    let day = byDate.get(w.date);
    if (!day) {
      day = createEmptyDayWorkout(w.date);
      byDate.set(w.date, day);
    }
    addUniqueActivity(day, "Strength");
    day.totalVolume += w.total_volume;
    day.totalSets += w.total_sets;
  }
}

function aggregateFallbackWorkouts(
  workouts: HealthData["workouts"],
  byDate: Map<string, DayAggregatedWorkout>,
  thirtyDaysAgo: Date,
  now: Date,
): void {
  for (const w of workouts) {
    const wDate = parseISO(w.date);
    if (wDate < thirtyDaysAgo || wDate > now) continue;
    if (w.total_volume === null && w.total_sets === null) continue;
    let day = byDate.get(w.date);
    if (!day) {
      day = createEmptyDayWorkout(w.date);
      byDate.set(w.date, day);
    }
    addUniqueActivity(day, "Strength");
    day.totalVolume += w.total_volume ?? 0;
    day.totalSets += w.total_sets ?? 0;
  }
}

function applyGarminDayMetrics(
  day: DayAggregatedWorkout,
  a: HealthData["garmin_activity"][number],
): void {
  if (a.duration_seconds !== null) {
    day.duration = formatDuration(a.duration_seconds);
  }
  if (a.distance_meters !== null && a.distance_meters > 0) {
    day.distance = `${(a.distance_meters / 1000).toFixed(1)}km`;
  }
  if (a.avg_heart_rate !== null) {
    updatePeakHr(day, a.avg_heart_rate);
  }
  if (
    a.avg_speed_mps !== null &&
    a.avg_speed_mps > 0 &&
    a.distance_meters !== null &&
    a.distance_meters > 100
  ) {
    day.notes.push(formatPaceForReport(a.avg_speed_mps));
  }
  if (a.training_effect_aerobic !== null) {
    day.notes.push(`TE=${a.training_effect_aerobic.toFixed(1)}`);
  }
}

function aggregateGarminActivities(
  activities: HealthData["garmin_activity"],
  byDate: Map<string, DayAggregatedWorkout>,
  thirtyDaysAgo: Date,
  now: Date,
): void {
  for (const a of activities) {
    const aDate = parseISO(a.date);
    if (aDate < thirtyDaysAgo || aDate > now) continue;
    if (a.distance_meters !== null && a.distance_meters < 1000) continue;
    let day = byDate.get(a.date);
    if (!day) {
      day = createEmptyDayWorkout(a.date);
      byDate.set(a.date, day);
    }
    const name = a.activity_name ?? a.activity_type ?? DEFAULT_ACTIVITY_NAME;
    addUniqueActivity(day, name);
    applyGarminDayMetrics(day, a);
  }
}

const DEDUP_WINDOW_MS = 10 * 60 * 1000;

function deduplicateWhoopWorkouts(
  workouts: HealthData["whoop_workout"],
): HealthData["whoop_workout"] {
  const kept: HealthData["whoop_workout"][number][] = [];
  for (const w of workouts) {
    const name = normalizeActivityName(w.sport_name ?? DEFAULT_ACTIVITY_NAME);
    const wStart = w.start_time ? parseISO(w.start_time).getTime() : 0;
    const duplicate = kept.find((k) => {
      const kName = normalizeActivityName(
        k.sport_name ?? DEFAULT_ACTIVITY_NAME,
      );
      if (kName.toLowerCase() !== name.toLowerCase()) return false;
      if (!k.start_time || !w.start_time) return k.date === w.date;
      return (
        Math.abs(parseISO(k.start_time).getTime() - wStart) <= DEDUP_WINDOW_MS
      );
    });
    if (duplicate) {
      if ((w.strain ?? 0) > (duplicate.strain ?? 0)) {
        kept.splice(kept.indexOf(duplicate), 1, w);
      }
    } else {
      kept.push(w);
    }
  }
  return kept;
}

function aggregateWhoopWorkouts(
  whoopWorkouts: HealthData["whoop_workout"],
  byDate: Map<string, DayAggregatedWorkout>,
  thirtyDaysAgo: Date,
  now: Date,
): void {
  const deduped = deduplicateWhoopWorkouts(whoopWorkouts);
  for (const w of deduped) {
    const wDate = parseISO(w.date);
    if (wDate < thirtyDaysAgo || wDate > now) continue;
    let day = byDate.get(w.date);
    if (!day) {
      day = createEmptyDayWorkout(w.date);
      byDate.set(w.date, day);
    }
    const name = w.sport_name ?? DEFAULT_ACTIVITY_NAME;
    addUniqueActivity(day, name);
    if (w.strain !== null) {
      day.totalStrain += w.strain;
    }
    if (w.avg_heart_rate !== null) {
      updatePeakHr(day, w.avg_heart_rate);
    }
  }
}

function buildDayAggregatedLog(
  data: HealthData,
  detailedWorkouts: WorkoutExerciseDetail[] | null,
  now: Date,
): DayAggregatedWorkout[] {
  const thirtyDaysAgo = new Date(now);
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

  const byDate = new Map<string, DayAggregatedWorkout>();

  if (detailedWorkouts && detailedWorkouts.length > 0) {
    aggregateDetailedWorkouts(detailedWorkouts, byDate, thirtyDaysAgo, now);
  } else {
    aggregateFallbackWorkouts(data.workouts, byDate, thirtyDaysAgo, now);
  }

  aggregateGarminActivities(data.garmin_activity, byDate, thirtyDaysAgo, now);
  aggregateWhoopWorkouts(data.whoop_workout, byDate, thirtyDaysAgo, now);

  return Array.from(byDate.values()).sort((a, b) =>
    b.date.localeCompare(a.date),
  );
}

function formatUnifiedTrainingLog(
  data: HealthData,
  detailedWorkouts: WorkoutExerciseDetail[] | null,
  now: Date,
): string[] {
  const days = buildDayAggregatedLog(data, detailedWorkouts, now);

  if (days.length === 0) {
    return [`## Training Log (30d)`, `No workouts recorded.`];
  }

  const lines: string[] = [
    `## Training Log (30d)`,
    `| Date   | Activities          | Load                   | HR  | Notes     |`,
    `|--------|---------------------|------------------------|-----|-----------|`,
  ];

  for (const day of days) {
    const dateStr = format(parseISO(day.date), "MMM d");
    const acts = day.activities.join("+").slice(0, 19);

    const loadParts: string[] = [];
    if (day.totalStrain > 0) {
      loadParts.push(
        `${day.totalStrain.toFixed(1)}/${String(WHOOP_MAX_STRAIN)}str`,
      );
    }
    if (day.totalVolume > 0) {
      loadParts.push(
        `${formatVolume(day.totalVolume)}/${String(day.totalSets)}s`,
      );
    }
    if (day.distance) {
      loadParts.push(day.distance);
    }
    if (day.duration && loadParts.length === 0) {
      loadParts.push(day.duration);
    }
    const load = loadParts.join(" ").slice(0, 22);
    const hr = day.peakHr === null ? "" : String(day.peakHr);
    const notes = day.notes.join(" ").slice(0, 9);

    lines.push(
      `| ${pad(dateStr, 6)} | ${pad(acts, 19)} | ${pad(load, 22)} | ${pad(hr, 3)} | ${pad(notes, 9)} |`,
    );
  }

  return lines;
}

function formatClinical(analytics: AnalyticsResponse): string[] {
  const rc = analytics.recovery_capacity;
  const decor = analytics.decorrelation;
  const lines: string[] = [];

  const hasRecoveryData = !isAllNull(
    rc.avg_recovery_days,
    rc.recovery_efficiency,
  );
  const hasCorrelationData = !isAllNull(
    decor.current_correlation,
    decor.baseline_correlation,
  );

  if (!hasRecoveryData && !hasCorrelationData) return [];

  lines.push(`## Clinical`);

  if (hasRecoveryData) {
    lines.push(
      `Recovery: avg ${n(rc.avg_recovery_days, 1)}d, efficiency ${n(rc.recovery_efficiency, 2)}, ${String(rc.recovered_events)}/${String(rc.high_strain_events)} high-strain recovered`,
    );
  }

  if (hasCorrelationData) {
    lines.push(
      `HRV-RHR r: current=${n(decor.current_correlation, 3)} baseline=${n(decor.baseline_correlation, 3)} Δ=${n(decor.correlation_delta, 3)}`,
    );
  }

  return lines;
}

function formatHrvAdvanced(hrv: AdvancedInsights["hrv_advanced"]): string {
  return `HRV: ln(RMSSD)=${n(hrv.ln_rmssd_current, 2)} (7d: ${n(hrv.ln_rmssd_mean_7d, 2)}±${n(hrv.ln_rmssd_sd_7d, 3)}) divergence=${n(hrv.divergence_rate, 3)}`;
}

function formatSleepQuality(
  sleep: AdvancedInsights["sleep_quality"],
): string | null {
  const sleepParts = [
    sleep.deep_sleep_pct === null
      ? null
      : `deep=${sleep.deep_sleep_pct.toFixed(0)}%`,
    sleep.rem_sleep_pct === null
      ? null
      : `rem=${sleep.rem_sleep_pct.toFixed(0)}%`,
    sleep.efficiency === null ? null : `eff=${sleep.efficiency.toFixed(0)}%`,
    sleep.fragmentation_index === null
      ? null
      : `frag=${sleep.fragmentation_index.toFixed(1)}`,
    sleep.consistency_score === null
      ? null
      : `consistency=${sleep.consistency_score.toFixed(0)}%`,
  ].filter(Boolean);
  if (sleepParts.length === 0) return null;
  return `Sleep: ${sleepParts.join(" ")}`;
}

function formatVo2MaxWithTrend(fitness: AdvancedInsights["fitness"]): string {
  if (fitness.vo2_max_current === null) return "";
  if (fitness.vo2_max_trend === null) {
    return `VO2=${fitness.vo2_max_current.toFixed(1)}`;
  }
  const sign = fitness.vo2_max_trend >= 0 ? "+" : "";
  return `VO2=${fitness.vo2_max_current.toFixed(1)}(${sign}${fitness.vo2_max_trend.toFixed(2)}/wk)`;
}

function formatFitnessMetrics(
  fitness: AdvancedInsights["fitness"],
): string | null {
  const fitParts = [
    formatVo2MaxWithTrend(fitness) || null,
    fitness.ctl === null ? null : `CTL=${fitness.ctl.toFixed(0)}`,
    fitness.atl === null ? null : `ATL=${fitness.atl.toFixed(0)}`,
    fitness.tsb === null ? null : `TSB=${fitness.tsb.toFixed(0)}`,
    fitness.monotony === null
      ? null
      : `monotony=${fitness.monotony.toFixed(1)}`,
  ].filter(Boolean);
  if (fitParts.length === 0) return null;
  return `Fitness: ${fitParts.join(" ")}`;
}

function formatAllostaticAndRecovery(
  allostatic: AdvancedInsights["allostatic_load"],
  recovery: AdvancedInsights["recovery_enhanced"],
): string {
  const alloScore = n(allostatic.composite_score, 2);
  const alloNorm =
    allostatic.composite_score !== null && allostatic.composite_score > 10
      ? " [HIGH, norm:<10]"
      : "";
  const recDebt = recovery.recovery_debt;
  const recDebtNorm =
    recDebt !== null && recDebt > 100 ? " [HIGH, norm:<100]" : "";
  const halfLife = recovery.recovery_half_life_days;
  const halfLifeStr = halfLife === null ? "N/A" : `${halfLife.toFixed(1)}d`;

  return `Allostatic: ${alloScore}${alloNorm} (trend:${n(allostatic.trend, 3)}) | Recovery: debt=${n(recDebt, 1)}${recDebtNorm} mismatch=${n(recovery.strain_recovery_mismatch_7d, 2)} half-life=${halfLifeStr}`;
}

function formatAdvanced(insights: AdvancedInsights): string[] {
  const lines: string[] = [`## Advanced`];

  lines.push(formatHrvAdvanced(insights.hrv_advanced));

  const sleepLine = formatSleepQuality(insights.sleep_quality);
  if (sleepLine) {
    lines.push(sleepLine);
  }

  const fitnessLine = formatFitnessMetrics(insights.fitness);
  if (fitnessLine) {
    lines.push(fitnessLine);
  }

  lines.push(
    formatAllostaticAndRecovery(
      insights.allostatic_load,
      insights.recovery_enhanced,
    ),
  );

  return lines;
}

function ensureSectionHeader(lines: string[]): void {
  if (lines.length === 0) {
    lines.push(`## Cross-Domain`);
  }
}

function formatHrvResidual(
  residual: AdvancedInsights["cross_domain"]["hrv_residual"],
  lines: string[],
): void {
  const hasResidual = !isAllNull(
    residual.predicted,
    residual.actual,
    residual.residual,
  );
  if (!hasResidual) return;

  ensureSectionHeader(lines);
  lines.push(
    `HRV Residual: pred=${n(residual.predicted)} actual=${n(residual.actual)} residual=${n(residual.residual)} z=${n(residual.residual_z, 2)} R²=${n(residual.r_squared, 3)}`,
  );
}

function formatWeightHrvCoupling(
  crossDomain: AdvancedInsights["cross_domain"],
  lines: string[],
): void {
  if (
    crossDomain.weight_hrv_coupling === null ||
    crossDomain.weight_hrv_p_value === null ||
    crossDomain.weight_hrv_p_value >= 0.05
  ) {
    return;
  }
  ensureSectionHeader(lines);
  lines.push(
    `Weight-HRV: r=${crossDomain.weight_hrv_coupling.toFixed(3)} (p=${crossDomain.weight_hrv_p_value.toFixed(3)})`,
  );
}

function formatWeekdayWeekend(
  ww: AdvancedInsights["cross_domain"]["weekday_weekend"],
  lines: string[],
): void {
  const wwKeys = Object.keys(ww);
  if (wwKeys.length === 0) return;

  const meaningful = wwKeys.filter((k) => {
    const s = ww[k];
    return s.delta !== null && Math.abs(s.delta) >= 1;
  });
  if (meaningful.length === 0) return;

  ensureSectionHeader(lines);
  lines.push(`Weekday/Weekend:`);
  for (const k of meaningful) {
    const s = ww[k];
    const deltaSign = s.delta !== null && s.delta >= 0 ? "+" : "";
    const d = s.delta === null ? "" : `${deltaSign}${s.delta.toFixed(1)}`;
    const wdStr = s.weekday_mean === null ? "" : s.weekday_mean.toFixed(1);
    const weStr = s.weekend_mean === null ? "" : s.weekend_mean.toFixed(1);
    lines.push(`  ${k}: wd=${wdStr} we=${weStr} Δ=${d}`);
  }
}

function formatCrossDomain(insights: AdvancedInsights): string[] {
  const { cross_domain } = insights;
  const lines: string[] = [];

  formatHrvResidual(cross_domain.hrv_residual, lines);
  formatWeightHrvCoupling(cross_domain, lines);
  formatWeekdayWeekend(cross_domain.weekday_weekend, lines);

  return lines;
}

function formatLagCorrelations(insights: AdvancedInsights): string[] {
  const { lag_correlations } = insights;
  const significant = lag_correlations.pairs.filter(
    (p) => p.correlation !== null && p.p_value !== null && p.p_value < 0.1,
  );

  if (significant.length === 0) return [];

  const lines: string[] = [
    `## Lag Correlations`,
    `| A → B | Lag | r | p |`,
    `|-------|-----|---|---|`,
  ];

  for (const pair of significant) {
    lines.push(
      `| ${pair.metric_a}→${pair.metric_b} | ${String(pair.lag_days)}d | ${(pair.correlation ?? 0).toFixed(3)} | ${(pair.p_value ?? 0).toFixed(3)} |`,
    );
  }

  return lines;
}

function formatSignificantCorrelations(analytics: AnalyticsResponse): string[] {
  const c = analytics.correlations;
  if (!c.is_significant) return [];

  const lines: string[] = [];
  if (
    c.hrv_rhr_correlation !== null &&
    c.hrv_rhr_p_value !== null &&
    c.hrv_rhr_p_value < 0.05
  ) {
    lines.push(
      `HRV-RHR: r=${c.hrv_rhr_correlation.toFixed(3)} p=${c.hrv_rhr_p_value.toFixed(3)}`,
    );
  }
  if (
    c.sleep_hrv_lag_correlation !== null &&
    c.sleep_hrv_p_value !== null &&
    c.sleep_hrv_p_value < 0.05
  ) {
    lines.push(
      `Sleep→HRV: r=${c.sleep_hrv_lag_correlation.toFixed(3)} p=${c.sleep_hrv_p_value.toFixed(3)}`,
    );
  }
  if (
    c.strain_recovery_correlation !== null &&
    c.strain_recovery_p_value !== null &&
    c.strain_recovery_p_value < 0.05
  ) {
    lines.push(
      `Strain→Recovery: r=${c.strain_recovery_correlation.toFixed(3)} p=${c.strain_recovery_p_value.toFixed(3)}`,
    );
  }

  if (lines.length === 0) return [];
  return [`## Correlations`, ...lines];
}

export function formatCombinedReport(
  data: HealthData | null,
  detailedWorkouts?: WorkoutExerciseDetail[] | null,
  allAnalytics?: Partial<Record<string, AnalyticsResponse>> | null,
): string {
  if (!data) return "";

  const now = new Date();
  const recent = allAnalytics?.recent ?? null;
  const dateStr = format(now, "yyyy-MM-dd (EEE)");
  const timeStr = format(now, "HH:mm");

  const sections: string[][] = [
    [
      `# Daily Health Brief | ${dateStr} ${timeStr}`,
      `Note: All calorie/energy values are energy EXPENDITURE (burned), NOT food intake.`,
    ],
  ];

  if (recent) {
    sections.push(
      formatToday(recent, now),
      formatStatus(recent),
      formatLastDays(recent.recent_days),
    );
  }

  if (recent?.longevity_insights) {
    sections.push(formatLongevity(recent));
  }

  if (allAnalytics) {
    sections.push(formatTrendsTable(allAnalytics));
  }

  if (recent) {
    sections.push(formatAnomalies(recent));
  }

  if (allAnalytics) {
    sections.push(formatTimeframeTable(allAnalytics));
  }

  if (recent) {
    sections.push(formatHealthScore(recent), formatEnergyBalance(recent));
  }

  sections.push(formatUnifiedTrainingLog(data, detailedWorkouts ?? null, now));

  if (recent) {
    sections.push(formatClinical(recent));
  }

  if (recent?.advanced_insights) {
    sections.push(
      formatAdvanced(recent.advanced_insights),
      formatCrossDomain(recent.advanced_insights),
      formatLagCorrelations(recent.advanced_insights),
    );
  }

  if (recent) {
    sections.push(formatSignificantCorrelations(recent));
  }

  sections.push([
    `---`,
    `Z: <-2 very low … >+2 very high | ACWR: <0.8 detrain 0.8-1.3 optimal 1.3-1.5 caution >1.5 injury`,
  ]);

  return sections
    .filter((s) => s.length > 0)
    .map((s) => s.join("\n"))
    .join("\n\n");
}
