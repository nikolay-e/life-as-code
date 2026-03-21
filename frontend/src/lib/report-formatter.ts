import { format, differenceInDays, parseISO } from "date-fns";
import type {
  HealthData,
  WorkoutData,
  WhoopWorkoutData,
  GarminActivityData,
  WorkoutExerciseDetail,
  AdvancedInsights,
  AnalyticsResponse,
  DayOverDayMetrics,
  IllnessRiskSignal,
  DecorrelationAlert,
  RecoveryMetrics,
  ActivityMetrics,
  RecoveryCapacityMetrics,
  DayMetrics,
} from "../types/api";
import { formatDuration, formatPaceForReport } from "./formatters";
import { WHOOP_MAX_STRAIN, DEFAULT_ACTIVITY_NAME } from "./constants";
import { toTimeMs } from "./health";

function formatNum(v: number | null, decimals = 1): string {
  return v === null ? "N/A" : v.toFixed(decimals);
}

function getRiskStatus(riskLevel: string | null): string {
  if (riskLevel === "high") return "[HIGH]";
  if (riskLevel === "moderate") return "[MODERATE]";
  return "[LOW]";
}

function getImbalanceStatus(imbalance: number | null): string {
  if (imbalance === null) return "N/A";
  if (imbalance < -1) return "RECOVERED";
  if (imbalance < 0) return "BALANCED";
  if (imbalance < 1) return "MILD STRAIN";
  return "STRAINED";
}

function getAcwrStatus(acwr: number | null): string {
  if (acwr === null) return "N/A";
  if (acwr < 0.8) return "DETRAINING";
  if (acwr <= 1.3) return "OPTIMAL";
  if (acwr <= 1.5) return "CAUTION";
  return "INJURY RISK";
}

function formatMinutes(mins: number | null): string {
  if (mins === null) return "N/A";
  if (mins < 0) return "0m";
  const totalMinutes = Math.round(mins);
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  return h > 0 ? `${String(h)}h ${String(m)}m` : `${String(m)}m`;
}

function formatSteps(v: number | null): string {
  return v === null ? "N/A" : Math.round(v).toLocaleString();
}

interface LastWorkout {
  type: "strength" | "cardio";
  daysAgo: number;
  date: string;
  volume: number | null;
  sets: number | null;
}

function getLastWorkouts(
  workouts: WorkoutData[],
  now: Date,
): { strength: LastWorkout | null; lastWorkoutDate: string | null } {
  if (workouts.length === 0) {
    return { strength: null, lastWorkoutDate: null };
  }

  const sorted = [...workouts]
    .filter((w) => w.total_volume !== null || w.total_sets !== null)
    .sort((a, b) => toTimeMs(b.date) - toTimeMs(a.date));

  if (sorted.length === 0) {
    return { strength: null, lastWorkoutDate: null };
  }

  const latest = sorted[0];
  const daysAgo = differenceInDays(now, parseISO(latest.date));

  return {
    strength: {
      type: "strength",
      daysAgo,
      date: latest.date,
      volume: latest.total_volume,
      sets: latest.total_sets,
    },
    lastWorkoutDate: latest.date,
  };
}

function getReadinessRecommendation(
  acwr: number | null,
  hrvRhrImbalance: number | null,
  illnessRiskLevel: string | null,
): string {
  if (illnessRiskLevel === "high") return "REST - illness risk detected";
  if (illnessRiskLevel === "moderate") {
    return "LIGHT ACTIVITY - monitor symptoms";
  }

  if (acwr === null || hrvRhrImbalance === null) return "INSUFFICIENT DATA";

  const isRecovered = hrvRhrImbalance < -1;
  const isBalanced = hrvRhrImbalance >= -1 && hrvRhrImbalance < 0;
  const isStrained = hrvRhrImbalance >= 0.5;
  const isDetraining = acwr < 0.8;
  const isOptimalLoad = acwr >= 0.8 && acwr <= 1.3;
  const isOverreaching = acwr > 1.3;
  const isInjuryRisk = acwr > 1.5;

  if (isInjuryRisk) {
    return "RECOVERY DAY - injury risk from high load";
  }
  if (isRecovered && isOptimalLoad) {
    return "READY FOR TRAINING";
  }
  if (isRecovered && isOverreaching) {
    return "LIGHT SESSION - recovered but load is high";
  }
  if (isRecovered && isDetraining) {
    return "INCREASE LOAD - well recovered, build capacity";
  }
  if (isBalanced && isDetraining) {
    return "MODERATE TRAINING - room to increase";
  }
  if (isStrained || isOverreaching) {
    return "RECOVERY DAY recommended";
  }
  return "MODERATE ACTIVITY";
}

function formatDeltaWithYesterday(
  delta: number | null,
  previousValue: number | null,
  previousDate: string | null,
  suffix: string = "",
  decimals: number = 1,
): string {
  if (delta === null || previousValue === null || previousDate === null) {
    return "";
  }
  const deltaStr = `${delta >= 0 ? "+" : ""}${delta.toFixed(decimals)}${suffix}`;
  const dateStr = format(parseISO(previousDate), "MMM d");
  return ` (diff: ${deltaStr} vs ${dateStr}: ${previousValue.toFixed(decimals)}${suffix})`;
}

function formatTodayStatus(
  dayOverDay: DayOverDayMetrics,
  dayCompleteness: number,
  now: Date,
): string[] {
  const timeStr = format(now, "HH:mm");
  const dateStr = format(now, "yyyy-MM-dd (EEEE)");
  const isIncomplete = dayCompleteness < 1;

  const lines: string[] = [
    `## Today's Status`,
    `Date: ${dateStr}`,
    `Report time: ${timeStr}`,
    ``,
  ];

  const { recovery, hrv, rhr, sleep, steps, weight } = dayOverDay;

  if (recovery.latest !== null) {
    const deltaStr = formatDeltaWithYesterday(
      recovery.delta,
      recovery.previous,
      recovery.previous_date,
      "%",
      0,
    );
    lines.push(`Recovery: ${formatNum(recovery.latest, 0)}%${deltaStr}`);
  }

  if (hrv.latest !== null) {
    const deltaStr = formatDeltaWithYesterday(
      hrv.delta,
      hrv.previous,
      hrv.previous_date,
      "",
      0,
    );
    lines.push(`HRV: ${formatNum(hrv.latest, 0)} ms${deltaStr}`);
  }

  if (rhr.latest !== null) {
    const deltaStr = formatDeltaWithYesterday(
      rhr.delta,
      rhr.previous,
      rhr.previous_date,
      "",
      0,
    );
    lines.push(`RHR: ${formatNum(rhr.latest, 0)} bpm${deltaStr}`);
  }

  if (sleep.latest !== null) {
    const sleepNightStr = sleep.previous_date
      ? ` (${format(parseISO(sleep.previous_date), "MMM d")}→${format(now, "d")} night)`
      : "";
    lines.push(`Sleep: ${formatMinutes(sleep.latest)}${sleepNightStr}`);
  }

  if (steps.latest !== null) {
    const incompleteFlag = isIncomplete
      ? ` [incomplete, as of ${timeStr}]`
      : "";
    lines.push(`Steps: ${formatSteps(steps.latest)}${incompleteFlag}`);
  }

  if (weight.latest !== null) {
    const deltaStr = formatDeltaWithYesterday(
      weight.delta,
      weight.previous,
      weight.previous_date,
      " kg",
      2,
    );
    lines.push(`Weight: ${weight.latest.toFixed(2)} kg${deltaStr}`);
  }

  return lines;
}

function formatAlerts(
  illnessRisk: IllnessRiskSignal,
  decorrelationAlert: DecorrelationAlert,
): string[] {
  const riskStatus = getRiskStatus(illnessRisk.risk_level);
  const riskLevel = (illnessRisk.risk_level ?? "N/A").toUpperCase();
  const decorStatus = decorrelationAlert.is_decorrelated ? "[ALERT]" : "[OK]";
  const decorText = decorrelationAlert.is_decorrelated ? "YES - monitor" : "No";

  const lines: string[] = [
    `## Alerts`,
    ``,
    `${riskStatus} Pre-Illness Risk: ${riskLevel}`,
    `${decorStatus} HRV-RHR Decorrelation: ${decorText}`,
  ];

  if (illnessRisk.consecutive_days_elevated > 0) {
    lines.push(
      `[WARNING] Consecutive Days Elevated: ${String(illnessRisk.consecutive_days_elevated)}`,
    );
  }

  return lines;
}

function formatReadiness(
  recoveryMetrics: RecoveryMetrics,
  activityMetrics: ActivityMetrics,
  illnessRiskLevel: string | null,
): string[] {
  const imbalance = recoveryMetrics.hrv_rhr_imbalance;
  const imbalanceStatus = getImbalanceStatus(imbalance);
  const acwr = activityMetrics.acwr;
  const acwrStatus = getAcwrStatus(acwr);
  const recommendation = getReadinessRecommendation(
    acwr,
    imbalance,
    illnessRiskLevel,
  );

  return [
    `## Readiness`,
    ``,
    `HRV-RHR Imbalance: ${formatNum(imbalance)} (${imbalanceStatus})`,
    `ACWR: ${formatNum(acwr)} (${acwrStatus})`,
    `Recommendation: ${recommendation}`,
  ];
}

function formatLastWorkouts(workouts: WorkoutData[], now: Date): string[] {
  const lines: string[] = [`## Last Workouts`, ``];

  const { strength } = getLastWorkouts(workouts, now);

  if (strength) {
    const dateStr = format(parseISO(strength.date), "MMM d");
    const daysAgoStr =
      strength.daysAgo === 0 ? "today" : `${String(strength.daysAgo)} days ago`;
    const volumeStr =
      strength.volume === null
        ? ""
        : `, ${String(Math.round(strength.volume / 1000))}k kg`;
    lines.push(`- Strength: ${dateStr} (${daysAgoStr})${volumeStr}`);
  } else {
    lines.push(`- Strength: No data`);
  }

  return lines;
}

function formatAnalysisWindows(now: Date): string[] {
  const lines: string[] = [`## Analysis Windows`, ``];

  const windows = [
    { label: "7d", days: 7 },
    { label: "14d", days: 14 },
    { label: "30d", days: 30 },
    { label: "42d", days: 42 },
    { label: "90d", days: 90 },
  ];

  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);

  for (const w of windows) {
    const startDate = new Date(now);
    startDate.setDate(startDate.getDate() - w.days);
    lines.push(
      `- ${w.label}: ${format(startDate, "MMM d")}–${format(yesterday, "MMM d")}`,
    );
  }

  return lines;
}

function formatTrendsSummaryTable(
  allAnalytics: Partial<Record<string, AnalyticsResponse>>,
): string[] {
  const modes = ["recent", "quarter", "year", "all"] as const;

  const formatRow = (
    name: string,
    key: string,
    formatter: (v: number | null) => string,
  ): string => {
    const values = modes.map((m) => {
      const baseline = allAnalytics[m]?.metric_baselines[key];
      return baseline?.short_term_mean ?? null;
    });

    const trendSlope =
      allAnalytics.recent?.metric_baselines[key]?.trend_slope ?? null;
    let trendStr = "N/A";
    if (trendSlope !== null) {
      const sign = trendSlope >= 0 ? "+" : "";
      trendStr = `${sign}${trendSlope.toFixed(2)}/d`;
    }

    const pad = (s: string, len: number) => s.padEnd(len);
    return `| ${pad(name, 8)} | ${pad(formatter(values[0]), 7)} | ${pad(formatter(values[1]), 8)} | ${pad(formatter(values[2]), 8)} | ${pad(formatter(values[3]), 8)} | ${pad(trendStr, 10)} |`;
  };

  return [
    `## Trends Summary`,
    ``,
    `Short-term averages by mode (baseline windows in parentheses):`,
    ``,
    `| Metric   | 6W (7d) | 6M (14d) | 2Y (30d) | 5Y (90d) | 7d Trend   |`,
    `|----------|---------|----------|----------|----------|------------|`,
    formatRow("HRV", "hrv", (v) => (v === null ? "N/A" : v.toFixed(1))),
    formatRow("RHR", "rhr", (v) => (v === null ? "N/A" : v.toFixed(1))),
    formatRow("Sleep", "sleep", (v) => (v === null ? "N/A" : formatMinutes(v))),
    formatRow("Steps", "steps", (v) => formatSteps(v)),
    formatRow("Weight", "weight", (v) => (v === null ? "N/A" : v.toFixed(1))),
    formatRow("Recovery", "recovery", (v) =>
      v === null ? "N/A" : `${v.toFixed(0)}%`,
    ),
  ];
}

function formatHealthScoreSummary(analytics: AnalyticsResponse): string[] {
  const hs = analytics.health_score;

  const lines: string[] = [
    `## Health Score`,
    ``,
    `Overall: ${formatNum(hs.overall, 2)}`,
    `Recovery Core (60%): ${formatNum(hs.recovery_core, 2)}`,
    `Training Load (20%): ${formatNum(hs.training_load, 2)}`,
    `Behavior Support (20%): ${formatNum(hs.behavior_support, 2)}`,
    ``,
    `Contributors:`,
  ];

  for (const c of hs.contributors) {
    const gateStatus = c.is_gated ? " [GATED]" : "";
    lines.push(
      `- ${c.name}: z=${formatNum(c.goodness_z_score, 2)} (conf=${(c.confidence * 100).toFixed(0)}%)${gateStatus}`,
    );
  }

  return lines;
}

function formatClinicalMetrics(
  recoveryCapacity: RecoveryCapacityMetrics,
  illnessRisk: IllnessRiskSignal,
  decorrelationAlert: DecorrelationAlert,
): string[] {
  const avgRecDays =
    recoveryCapacity.avg_recovery_days === null
      ? "N/A"
      : recoveryCapacity.avg_recovery_days.toFixed(1);
  const recEfficiency =
    recoveryCapacity.recovery_efficiency === null
      ? "N/A"
      : recoveryCapacity.recovery_efficiency.toFixed(2);

  const components = illnessRisk.components;
  const combinedDev =
    illnessRisk.combined_deviation === null
      ? "N/A"
      : illnessRisk.combined_deviation.toFixed(2);
  const hrvDrop =
    components.hrv_drop === null ? "N/A" : components.hrv_drop.toFixed(2);
  const rhrRise =
    components.rhr_rise === null ? "N/A" : components.rhr_rise.toFixed(2);
  const sleepDrop =
    components.sleep_drop === null ? "N/A" : components.sleep_drop.toFixed(2);

  const currentCorr =
    decorrelationAlert.current_correlation === null
      ? "N/A"
      : decorrelationAlert.current_correlation.toFixed(3);
  const baselineCorr =
    decorrelationAlert.baseline_correlation === null
      ? "N/A"
      : decorrelationAlert.baseline_correlation.toFixed(3);
  const corrDelta =
    decorrelationAlert.correlation_delta === null
      ? "N/A"
      : decorrelationAlert.correlation_delta.toFixed(3);

  return [
    `## Clinical Metrics (Detailed)`,
    ``,
    `### Recovery Capacity`,
    `- Avg Recovery Days: ${avgRecDays}`,
    `- Recovery Efficiency: ${recEfficiency}`,
    `- High Strain Events: ${String(recoveryCapacity.high_strain_events)}`,
    `- Recovered Events: ${String(recoveryCapacity.recovered_events)}`,
    ``,
    `### Pre-Illness Components`,
    `- Combined Deviation: ${combinedDev}`,
    `- HRV Drop: ${hrvDrop}`,
    `- RHR Rise: ${rhrRise}`,
    `- Sleep Drop: ${sleepDrop}`,
    ``,
    `### HRV-RHR Correlation`,
    `- Current (14d): ${currentCorr}`,
    `- Baseline (60d): ${baselineCorr}`,
    `- Delta: ${corrDelta}`,
  ];
}

function formatDayTableRow(day: DayMetrics): string {
  const pad = (s: string, len: number) => s.padEnd(len);
  const dateStr = format(parseISO(day.date), "MMM d (EEE)");
  const rec = day.recovery === null ? "—" : `${day.recovery.toFixed(0)}%`;
  const hrv = day.hrv === null ? "—" : day.hrv.toFixed(0);
  const rhr = day.rhr === null ? "—" : day.rhr.toFixed(0);
  const sleep = day.sleep === null ? "—" : formatMinutes(day.sleep);
  const steps = day.steps === null ? "—" : formatSteps(day.steps);
  const strain = day.strain === null ? "—" : day.strain.toFixed(1);
  const stress = day.stress === null ? "—" : day.stress.toFixed(0);
  const cal = day.calories === null ? "—" : day.calories.toFixed(0);
  const weight = day.weight === null ? "—" : day.weight.toFixed(1);
  return `| ${pad(dateStr, 10)} | ${pad(rec, 4)} | ${pad(hrv, 3)} | ${pad(rhr, 3)} | ${pad(sleep, 7)} | ${pad(steps, 6)} | ${pad(strain, 6)} | ${pad(stress, 6)} | ${pad(cal, 5)} | ${pad(weight, 6)} |`;
}

function formatLastDaysTable(lastDays: DayMetrics[]): string[] {
  const lines: string[] = [
    `## Last ${String(lastDays.length)} Days Detail`,
    ``,
    `| Date       | Rec% | HRV | RHR | Sleep   | Steps  | Strain | Stress | Cal   | Weight |`,
    `|------------|------|-----|-----|---------|--------|--------|--------|-------|--------|`,
  ];
  for (const day of lastDays) {
    lines.push(formatDayTableRow(day));
  }
  return lines;
}

function formatAnalysisDetails(analytics: AnalyticsResponse): string[] {
  const cfg = analytics.mode_config;
  const { recovery_metrics, sleep_metrics, activity_metrics, weight_metrics } =
    analytics;

  const emaShort =
    weight_metrics.ema_short === null
      ? "N/A"
      : `${weight_metrics.ema_short.toFixed(1)} kg`;
  const emaLong =
    weight_metrics.ema_long === null
      ? "N/A"
      : `${weight_metrics.ema_long.toFixed(1)} kg`;
  let periodChange = "N/A";
  if (weight_metrics.period_change !== null) {
    const sign = weight_metrics.period_change >= 0 ? "+" : "";
    periodChange = `${sign}${weight_metrics.period_change.toFixed(2)} kg`;
  }

  return [
    `### ${analytics.mode} Analysis Details`,
    ``,
    `**Recovery:**`,
    `- Recovery CV: ${recovery_metrics.recovery_cv === null ? "N/A" : (recovery_metrics.recovery_cv * 100).toFixed(1)}%`,
    `- Stress Load (${String(cfg.short_term)}d): ${formatNum(recovery_metrics.stress_load_short, 0)}`,
    `- Stress Load (${String(cfg.baseline)}d): ${formatNum(recovery_metrics.stress_load_long, 0)}`,
    ``,
    `**Sleep:**`,
    `- Target: ${formatMinutes(sleep_metrics.target_sleep)}/night`,
    `- Debt (${String(cfg.short_term)}d): ${formatMinutes(sleep_metrics.sleep_debt_short)}`,
    `- Surplus (${String(cfg.short_term)}d): ${formatMinutes(sleep_metrics.sleep_surplus_short)}`,
    `- CV: ${(sleep_metrics.sleep_cv * 100).toFixed(1)}%`,
    ``,
    `**Activity:**`,
    `- Acute Load: ${formatNum(activity_metrics.acute_load, 1)}`,
    `- Chronic Load: ${formatNum(activity_metrics.chronic_load, 1)}`,
    `- ACWR: ${formatNum(activity_metrics.acwr)}`,
    `- Steps CV: ${(activity_metrics.steps_cv * 100).toFixed(1)}%`,
    ``,
    `**Weight:**`,
    `- EMA (${String(cfg.short_term)}d): ${emaShort}`,
    `- EMA (${String(cfg.baseline)}d): ${emaLong}`,
    `- Period Change: ${periodChange}`,
    `- Volatility: ±${weight_metrics.volatility_short.toFixed(2)} kg`,
  ];
}

function collectGarminActivityDetails(activity: GarminActivityData): string[] {
  const details: string[] = [];

  if (activity.duration_seconds !== null) {
    details.push(`Duration: ${formatDuration(activity.duration_seconds)}`);
  }
  if (activity.distance_meters !== null && activity.distance_meters > 0) {
    details.push(
      `Distance: ${(activity.distance_meters / 1000).toFixed(2)} km`,
    );
  }
  if (
    activity.avg_speed_mps !== null &&
    activity.avg_speed_mps > 0 &&
    activity.distance_meters !== null &&
    activity.distance_meters > 100
  ) {
    details.push(`Pace: ${formatPaceForReport(activity.avg_speed_mps)}`);
  }
  if (activity.avg_heart_rate !== null) {
    details.push(`Avg HR: ${String(activity.avg_heart_rate)} bpm`);
  }
  if (activity.max_heart_rate !== null) {
    details.push(`Max HR: ${String(activity.max_heart_rate)} bpm`);
  }
  if (activity.calories !== null) {
    details.push(`Calories: ${String(activity.calories)} kcal`);
  }
  if (
    activity.elevation_gain_meters !== null &&
    activity.elevation_gain_meters > 0
  ) {
    details.push(
      `Elevation Gain: ${String(Math.round(activity.elevation_gain_meters))} m`,
    );
  }
  if (activity.avg_power_watts !== null) {
    details.push(
      `Avg Power: ${String(Math.round(activity.avg_power_watts))} W`,
    );
  }
  if (activity.training_effect_aerobic !== null) {
    details.push(`Aerobic TE: ${activity.training_effect_aerobic.toFixed(1)}`);
  }
  if (activity.training_effect_anaerobic !== null) {
    details.push(
      `Anaerobic TE: ${activity.training_effect_anaerobic.toFixed(1)}`,
    );
  }
  if (activity.vo2_max_value !== null) {
    details.push(`VO2 Max: ${activity.vo2_max_value.toFixed(1)}`);
  }

  return details;
}

function formatGarminActivities(
  activities: GarminActivityData[],
  now: Date,
): string[] {
  const lines: string[] = [`## Garmin Activities (Last 30 Days)`, ``];

  const thirtyDaysAgo = new Date(now);
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

  const filtered = activities.filter((a) => {
    const actDate = parseISO(a.date);
    return actDate >= thirtyDaysAgo && actDate <= now;
  });

  if (filtered.length === 0) {
    lines.push(`No Garmin activities recorded in the last 30 days.`);
    return lines;
  }

  const sorted = [...filtered].sort((a, b) =>
    (b.start_time ?? b.date).localeCompare(a.start_time ?? a.date),
  );

  for (const activity of sorted) {
    const dateStr = format(parseISO(activity.date), "MMM d (EEE)");
    const timeStr = activity.start_time
      ? format(parseISO(activity.start_time), "HH:mm")
      : "";
    const name =
      activity.activity_name ?? activity.activity_type ?? DEFAULT_ACTIVITY_NAME;

    const timePart = timeStr ? ` at ${timeStr}` : "";
    lines.push(`### ${dateStr}${timePart}: ${name}`);

    for (const detail of collectGarminActivityDetails(activity)) {
      lines.push(`- ${detail}`);
    }
    lines.push(``);
  }

  return lines;
}

function collectWhoopWorkoutDetails(workout: WhoopWorkoutData): string[] {
  const details: string[] = [];

  if (workout.strain !== null) {
    details.push(
      `Strain: ${workout.strain.toFixed(1)} / ${String(WHOOP_MAX_STRAIN)}`,
    );
  }
  if (workout.kilojoules !== null) {
    const calories = Math.round(workout.kilojoules / 4.184);
    details.push(
      `Energy: ${String(calories)} kcal (${workout.kilojoules.toFixed(0)} kJ)`,
    );
  }
  if (workout.avg_heart_rate !== null) {
    details.push(`Avg HR: ${String(workout.avg_heart_rate)} bpm`);
  }
  if (workout.max_heart_rate !== null) {
    details.push(`Max HR: ${String(workout.max_heart_rate)} bpm`);
  }
  if (workout.distance_meters !== null && workout.distance_meters > 0) {
    details.push(`Distance: ${(workout.distance_meters / 1000).toFixed(2)} km`);
  }
  if (
    workout.altitude_gain_meters !== null &&
    workout.altitude_gain_meters > 0
  ) {
    details.push(
      `Elevation Gain: ${String(Math.round(workout.altitude_gain_meters))} m`,
    );
  }

  return details;
}

function formatWhoopWorkouts(
  workouts: WhoopWorkoutData[],
  now: Date,
): string[] {
  const lines: string[] = [`## Whoop Workouts (Last 30 Days)`, ``];

  const thirtyDaysAgo = new Date(now);
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

  const filtered = workouts.filter((w) => {
    const wDate = parseISO(w.date);
    return wDate >= thirtyDaysAgo && wDate <= now;
  });

  if (filtered.length === 0) {
    lines.push(`No Whoop workouts recorded in the last 30 days.`);
    return lines;
  }

  const sorted = [...filtered].sort((a, b) =>
    (b.start_time ?? b.date).localeCompare(a.start_time ?? a.date),
  );

  for (const workout of sorted) {
    const dateStr = format(parseISO(workout.date), "MMM d (EEE)");
    const timeStr = workout.start_time
      ? format(parseISO(workout.start_time), "HH:mm")
      : "N/A";
    const name = workout.sport_name ?? DEFAULT_ACTIVITY_NAME;

    lines.push(`### ${dateStr} at ${timeStr}: ${name}`);

    for (const detail of collectWhoopWorkoutDetails(workout)) {
      lines.push(`- ${detail}`);
    }
    lines.push(``);
  }

  return lines;
}

interface DailyStrengthWorkout {
  date: string;
  exercises: WorkoutExerciseDetail[];
  totalVolume: number;
  totalSets: number;
}

function groupWorkoutsByDate(
  workouts: WorkoutExerciseDetail[],
): DailyStrengthWorkout[] {
  const byDate = new Map<string, WorkoutExerciseDetail[]>();

  for (const w of workouts) {
    const existing = byDate.get(w.date);
    if (existing) {
      existing.push(w);
    } else {
      byDate.set(w.date, [w]);
    }
  }

  return Array.from(byDate.entries())
    .map(([date, exercises]) => ({
      date,
      exercises,
      totalVolume: exercises.reduce((sum, e) => sum + e.total_volume, 0),
      totalSets: exercises.reduce((sum, e) => sum + e.total_sets, 0),
    }))
    .sort((a, b) => b.date.localeCompare(a.date));
}

function formatSetInfo(set: {
  set_index: number;
  weight_kg: number | null;
  reps: number | null;
  rpe: number | null;
  set_type: string | null;
}): string {
  const parts: string[] = [];

  const setNum = set.set_index + 1;
  const typeLabel =
    set.set_type && set.set_type !== "normal" ? ` (${set.set_type})` : "";
  parts.push(`Set ${String(setNum)}${typeLabel}:`);

  if (set.weight_kg !== null && set.weight_kg > 0) {
    parts.push(`${set.weight_kg.toFixed(1)}kg`);
  } else {
    parts.push("bodyweight");
  }

  if (set.reps !== null) {
    parts.push(`x ${String(set.reps)} reps`);
  }

  if (set.rpe !== null) {
    parts.push(`@ RPE ${set.rpe.toFixed(1)}`);
  }

  return parts.join(" ");
}

function formatVolumeStr(volume: number): string {
  return volume >= 1000
    ? `${(volume / 1000).toFixed(1)}t`
    : `${String(Math.round(volume))}kg`;
}

function formatDayStrengthSection(day: DailyStrengthWorkout): string[] {
  const lines: string[] = [];
  const dateStr = format(parseISO(day.date), "MMM d (EEE)");
  const volumeStr = formatVolumeStr(day.totalVolume);
  lines.push(
    `### ${dateStr} - ${String(day.exercises.length)} exercises, ${String(day.totalSets)} sets, ${volumeStr} total`,
    ``,
  );

  for (const exercise of day.exercises) {
    const exerciseVolumeStr = formatVolumeStr(exercise.total_volume);
    const rpeStr =
      exercise.avg_rpe === null
        ? ""
        : `, avg RPE ${exercise.avg_rpe.toFixed(1)}`;
    lines.push(
      `**${exercise.exercise}** (${String(exercise.total_sets)} sets, ${exerciseVolumeStr}${rpeStr})`,
    );
    for (const set of exercise.sets) {
      lines.push(`  - ${formatSetInfo(set)}`);
    }
    lines.push(``);
  }

  return lines;
}

function formatStrengthWorkoutsWithExercises(
  detailedWorkouts: WorkoutExerciseDetail[] | null,
  now: Date,
): string[] {
  const lines: string[] = [`## Strength Training (Hevy) - Last 30 Days`, ``];

  if (!detailedWorkouts || detailedWorkouts.length === 0) {
    lines.push(`No strength workouts recorded in the last 30 days.`);
    return lines;
  }

  const thirtyDaysAgo = new Date(now);
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

  const filtered = detailedWorkouts.filter((w) => {
    const wDate = parseISO(w.date);
    return wDate >= thirtyDaysAgo && wDate <= now;
  });

  if (filtered.length === 0) {
    lines.push(`No strength workouts recorded in the last 30 days.`);
    return lines;
  }

  const grouped = groupWorkoutsByDate(filtered);

  for (const day of grouped) {
    lines.push(...formatDayStrengthSection(day));
  }

  return lines;
}

function formatStrengthWorkoutsDetailed(
  workouts: WorkoutData[],
  now: Date,
): string[] {
  const lines: string[] = [`## Strength Training (Hevy) (Last 30 Days)`, ``];

  const thirtyDaysAgo = new Date(now);
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

  const filtered = workouts.filter((w) => {
    const wDate = parseISO(w.date);
    return wDate >= thirtyDaysAgo && wDate <= now;
  });

  if (filtered.length === 0) {
    lines.push(`No strength workouts recorded in the last 30 days.`);
    return lines;
  }

  const sorted = [...filtered].sort((a, b) => b.date.localeCompare(a.date));

  for (const workout of sorted) {
    const dateStr = format(parseISO(workout.date), "MMM d (EEE)");
    const volumeKg =
      workout.total_volume === null ? 0 : Math.round(workout.total_volume);
    const sets = workout.total_sets ?? 0;

    lines.push(
      `### ${dateStr}: ${String(sets)} sets, ${String(volumeKg)} kg total volume`,
      ``,
    );
  }

  return lines;
}

function formatHrvAdvancedSection(insights: AdvancedInsights): string[] {
  const { hrv_advanced, sleep_quality } = insights;

  const deepSleepPct =
    sleep_quality.deep_sleep_pct === null
      ? "N/A"
      : `${sleep_quality.deep_sleep_pct.toFixed(1)}%`;
  const remSleepPct =
    sleep_quality.rem_sleep_pct === null
      ? "N/A"
      : `${sleep_quality.rem_sleep_pct.toFixed(1)}%`;
  const sleepEfficiency =
    sleep_quality.efficiency === null
      ? "N/A"
      : `${sleep_quality.efficiency.toFixed(1)}%`;
  const consistencyScore =
    sleep_quality.consistency_score === null
      ? "N/A"
      : `${sleep_quality.consistency_score.toFixed(1)}%`;
  const sleepHrvP =
    sleep_quality.sleep_hrv_p_value === null
      ? ""
      : ` (p=${sleep_quality.sleep_hrv_p_value.toFixed(3)})`;
  const sleepHrvResponsiveness = `${formatNum(sleep_quality.sleep_hrv_responsiveness, 3)}${sleepHrvP}`;

  return [
    `# Advanced Health Insights`,
    ``,
    `## HRV Advanced`,
    ``,
    `- ln(RMSSD) Current: ${formatNum(hrv_advanced.ln_rmssd_current, 2)}`,
    `- ln(RMSSD) 7d Mean: ${formatNum(hrv_advanced.ln_rmssd_mean_7d, 2)}`,
    `- ln(RMSSD) 7d SD: ${formatNum(hrv_advanced.ln_rmssd_sd_7d, 3)}`,
    `- HRV-RHR Rolling r (14d): ${formatNum(hrv_advanced.hrv_rhr_rolling_r_14d, 3)}`,
    `- HRV-RHR Rolling r (60d): ${formatNum(hrv_advanced.hrv_rhr_rolling_r_60d, 3)}`,
    `- Divergence Rate: ${formatNum(hrv_advanced.divergence_rate, 3)}`,
    ``,
    `## Sleep Quality`,
    ``,
    `- Deep Sleep: ${deepSleepPct}`,
    `- REM Sleep: ${remSleepPct}`,
    `- Efficiency: ${sleepEfficiency}`,
    `- Fragmentation Index: ${formatNum(sleep_quality.fragmentation_index, 2)}`,
    `- Sleep→HRV Responsiveness: ${sleepHrvResponsiveness}`,
    `- Consistency Score: ${consistencyScore}`,
  ];
}

function formatFitnessSection(insights: AdvancedInsights): string[] {
  const { fitness, allostatic_load, recovery_enhanced } = insights;

  const lines: string[] = [``, `## Cardio Fitness & Training Load`, ``];

  if (fitness.vo2_max_current !== null) {
    let vo2Trend = "";
    if (fitness.vo2_max_trend !== null) {
      const sign = fitness.vo2_max_trend >= 0 ? "+" : "";
      vo2Trend = ` (trend: ${sign}${fitness.vo2_max_trend.toFixed(2)}/wk)`;
    }
    lines.push(`- VO2 Max: ${fitness.vo2_max_current.toFixed(1)}${vo2Trend}`);
  }

  const daysSinceLastWorkout =
    fitness.days_since_last_workout === null
      ? "N/A"
      : String(fitness.days_since_last_workout);

  lines.push(
    `- Days Since Last Workout: ${daysSinceLastWorkout}`,
    `- Training Frequency: ${String(fitness.training_frequency_7d)}/7d, ${String(fitness.training_frequency_30d)}/30d`,
    `- CTL (Chronic Load): ${formatNum(fitness.ctl)}`,
    `- ATL (Acute Load): ${formatNum(fitness.atl)}`,
    `- TSB (Form): ${formatNum(fitness.tsb)}`,
    `- Monotony: ${formatNum(fitness.monotony, 2)}`,
    `- Strain Index: ${formatNum(fitness.strain_index)}`,
    `- Detraining Score: ${formatNum(fitness.detraining_score, 2)}`,
    ``,
    `## Allostatic Load`,
    ``,
    `- Composite Score: ${formatNum(allostatic_load.composite_score, 2)}`,
    `- Trend: ${formatNum(allostatic_load.trend, 3)}`,
  );

  if (Object.keys(allostatic_load.breach_rates).length > 0) {
    lines.push(`- Breach Rates:`);
    for (const [metric, rate] of Object.entries(allostatic_load.breach_rates)) {
      lines.push(`  - ${metric}: ${(rate * 100).toFixed(0)}%`);
    }
  }

  const recoveryHalfLife =
    recovery_enhanced.recovery_half_life_days === null
      ? "N/A"
      : `${recovery_enhanced.recovery_half_life_days.toFixed(1)} days`;

  lines.push(
    ``,
    `## Recovery Enhanced`,
    ``,
    `- Recovery Debt: ${formatNum(recovery_enhanced.recovery_debt, 2)}`,
    `- Strain-Recovery Mismatch (7d): ${formatNum(recovery_enhanced.strain_recovery_mismatch_7d, 2)}`,
    `- Recovery Half-Life: ${recoveryHalfLife}`,
    ``,
  );

  return lines;
}

function _formatWeekdayWeekendRow(
  metric: string,
  split: {
    weekday_mean: number | null;
    weekend_mean: number | null;
    delta: number | null;
  },
): string {
  const wdStr =
    split.weekday_mean === null ? "—" : split.weekday_mean.toFixed(1);
  const weStr =
    split.weekend_mean === null ? "—" : split.weekend_mean.toFixed(1);
  let dStr = "—";
  if (split.delta !== null) {
    const sign = split.delta >= 0 ? "+" : "";
    dStr = `${sign}${split.delta.toFixed(1)}`;
  }
  return `| ${metric} | ${wdStr} | ${weStr} | ${dStr} |`;
}

function _formatWeightHrvSection(cross_domain: {
  weight_hrv_coupling: number | null;
  weight_hrv_p_value: number | null;
}): string[] {
  if (cross_domain.weight_hrv_coupling === null) return [];
  const p = cross_domain.weight_hrv_p_value;
  const weightHrvP = p === null ? "" : ` (p=${p.toFixed(3)})`;
  return [
    `## Cross-Domain`,
    ``,
    `- Weight-HRV Coupling: ${cross_domain.weight_hrv_coupling.toFixed(3)}${weightHrvP}`,
    ``,
  ];
}

function formatCrossDomainSection(insights: AdvancedInsights): string[] {
  const { cross_domain } = insights;
  const lines: string[] = [];

  const residual = cross_domain.hrv_residual;
  lines.push(
    `## HRV Residual Model`,
    ``,
    `- Predicted HRV: ${formatNum(residual.predicted)}`,
    `- Actual HRV: ${formatNum(residual.actual)}`,
    `- Residual: ${formatNum(residual.residual)}`,
    `- Residual Z-Score: ${formatNum(residual.residual_z, 2)}`,
    `- Model R²: ${formatNum(residual.r_squared, 3)}`,
  );

  if (residual.model_features.length > 0) {
    lines.push(`- Features: ${residual.model_features.join(", ")}`);
  }
  lines.push(``, ..._formatWeightHrvSection(cross_domain));

  const weekdayWeekend = cross_domain.weekday_weekend;
  if (Object.keys(weekdayWeekend).length > 0) {
    lines.push(
      `## Weekday vs Weekend`,
      ``,
      `| Metric | Weekday | Weekend | Delta |`,
      `|--------|---------|---------|-------|`,
    );
    for (const [metric, split] of Object.entries(weekdayWeekend)) {
      lines.push(_formatWeekdayWeekendRow(metric, split));
    }
    lines.push(``);
  }

  return lines;
}

function formatLagCorrelationsSection(insights: AdvancedInsights): string[] {
  const { lag_correlations } = insights;
  if (lag_correlations.pairs.length === 0) return [];

  const lines: string[] = [`## Lag Correlations`, ``];

  if (lag_correlations.strongest_positive) {
    const sp = lag_correlations.strongest_positive;
    lines.push(
      `- Strongest Positive: ${sp.metric_a} → ${sp.metric_b} (lag ${String(sp.lag_days)}d, r=${formatNum(sp.correlation, 3)}, n=${String(sp.sample_size)})`,
    );
  }
  if (lag_correlations.strongest_negative) {
    const sn = lag_correlations.strongest_negative;
    lines.push(
      `- Strongest Negative: ${sn.metric_a} → ${sn.metric_b} (lag ${String(sn.lag_days)}d, r=${formatNum(sn.correlation, 3)}, n=${String(sn.sample_size)})`,
    );
  }
  lines.push(
    ``,
    `| Metric A | Metric B | Lag | r | p | n |`,
    `|----------|----------|-----|---|---|---|`,
  );

  for (const pair of lag_correlations.pairs) {
    if (pair.correlation === null) continue;
    const pStr = pair.p_value === null ? "—" : pair.p_value.toFixed(3);
    lines.push(
      `| ${pair.metric_a} | ${pair.metric_b} | ${String(pair.lag_days)}d | ${pair.correlation.toFixed(3)} | ${pStr} | ${String(pair.sample_size)} |`,
    );
  }
  lines.push(``);

  return lines;
}

function formatAdvancedInsights(insights: AdvancedInsights): string[] {
  return [
    ...formatHrvAdvancedSection(insights),
    ...formatFitnessSection(insights),
    ...formatCrossDomainSection(insights),
    ...formatLagCorrelationsSection(insights),
  ];
}

export function formatCombinedReport(
  data: HealthData | null,
  detailedWorkouts?: WorkoutExerciseDetail[] | null,
  allAnalytics?: Partial<Record<string, AnalyticsResponse>> | null,
): string {
  if (!data) return "";

  const now = new Date();
  const recentAnalytics = allAnalytics?.recent ?? null;

  const sections: string[] = [
    `# Daily Health Brief`,
    `Generated: ${format(now, "yyyy-MM-dd HH:mm")}`,
    ``,
  ];

  if (recentAnalytics) {
    sections.push(
      ...formatTodayStatus(
        recentAnalytics.day_over_day,
        recentAnalytics.day_completeness,
        now,
      ),
      ``,
      ...formatLastDaysTable(recentAnalytics.recent_days),
      ``,
      ...formatAlerts(
        recentAnalytics.illness_risk,
        recentAnalytics.decorrelation,
      ),
      ``,
      ...formatReadiness(
        recentAnalytics.recovery_metrics,
        recentAnalytics.activity_metrics,
        recentAnalytics.illness_risk.risk_level,
      ),
      ``,
    );
  }

  sections.push(
    ...formatLastWorkouts(data.workouts, now),
    ``,
    `---`,
    `# Detailed Training Log`,
    ``,
  );

  if (detailedWorkouts && detailedWorkouts.length > 0) {
    sections.push(
      ...formatStrengthWorkoutsWithExercises(detailedWorkouts, now),
    );
  } else {
    sections.push(...formatStrengthWorkoutsDetailed(data.workouts, now));
  }
  sections.push(
    ``,
    ...formatGarminActivities(data.garmin_activity, now),
    ``,
    ...formatWhoopWorkouts(data.whoop_workout, now),
    ``,
    `---`,
    ``,
    ...formatAnalysisWindows(now),
    ``,
  );

  if (allAnalytics) {
    sections.push(`---`, ``, ...formatTrendsSummaryTable(allAnalytics), ``);

    if (recentAnalytics) {
      sections.push(
        ...formatHealthScoreSummary(recentAnalytics),
        ``,
        `---`,
        ``,
        ...formatClinicalMetrics(
          recentAnalytics.recovery_capacity,
          recentAnalytics.illness_risk,
          recentAnalytics.decorrelation,
        ),
        ``,
      );
    }

    sections.push(`---`, `# Detailed Analysis by Timeframe`, ``);

    for (const m of ["recent", "quarter", "year", "all"] as const) {
      const modeData = allAnalytics[m];
      if (modeData) {
        sections.push(...formatAnalysisDetails(modeData), ``);
      }
    }
  }

  if (recentAnalytics?.advanced_insights) {
    sections.push(
      `---`,
      ``,
      ...formatAdvancedInsights(recentAnalytics.advanced_insights),
    );
  }

  sections.push(
    `---`,
    `Z-Score: <-2 very low, -1 to -2 low, -1 to +1 normal, +1 to +2 high, >+2 very high`,
    `ACWR: <0.8 detraining, 0.8-1.3 optimal, 1.3-1.5 caution, >1.5 injury risk`,
  );

  return sections.join("\n");
}
