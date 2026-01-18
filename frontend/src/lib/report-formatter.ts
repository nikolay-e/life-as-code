import { format, differenceInDays, parseISO } from "date-fns";
import type {
  HealthData,
  WorkoutData,
  WhoopWorkoutData,
  GarminActivityData,
  WorkoutExerciseDetail,
} from "../types/api";
import { formatDuration, formatPaceForReport } from "./formatters";
import { WHOOP_MAX_STRAIN, DEFAULT_ACTIVITY_NAME } from "./constants";
import {
  TREND_MODES,
  MODE_ORDER,
  computeAllMetrics,
  getBaselineOptions,
  computeHealthAnalysis,
  type ComputedMetric,
  type HealthAnalysis,
} from "./metrics";
import {
  calculateRecoveryCapacity,
  calculateIllnessRiskSignal,
  calculateDecorrelationAlert,
  calculateDayOverDayMetrics,
  calculateDayCompleteness,
  calculateLastNDaysMetrics,
  type DayOverDayMetrics,
  type DayMetrics,
} from "./health-metrics";
import { toTimeMs } from "./health";

function formatNum(v: number | null, decimals = 1): string {
  return v !== null ? v.toFixed(decimals) : "N/A";
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
  return v !== null ? Math.round(v).toLocaleString() : "N/A";
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
  yesterdayValue: number | null,
  yesterdayDate: string | null,
  suffix: string = "",
  decimals: number = 1,
): string {
  if (delta === null || yesterdayValue === null || yesterdayDate === null) {
    return "";
  }
  const deltaStr = `${delta >= 0 ? "+" : ""}${delta.toFixed(decimals)}${suffix}`;
  const dateStr = format(parseISO(yesterdayDate), "MMM d");
  return ` (diff: ${deltaStr} vs ${dateStr}: ${yesterdayValue.toFixed(decimals)}${suffix})`;
}

function formatTodayStatus(
  dayOverDay: DayOverDayMetrics,
  dayCompleteness: number,
  now: Date,
): string[] {
  const lines: string[] = [];
  const timeStr = format(now, "HH:mm");
  const dateStr = format(now, "yyyy-MM-dd (EEEE)");
  const isIncomplete = dayCompleteness < 1;

  lines.push(`## Today's Status`);
  lines.push(`Date: ${dateStr}`);
  lines.push(`Report time: ${timeStr}`);
  lines.push(``);

  const { recovery, hrv, rhr, sleep, steps, weight } = dayOverDay;

  if (recovery.today !== null) {
    const deltaStr = formatDeltaWithYesterday(
      recovery.delta,
      recovery.yesterday,
      recovery.yesterdayDate,
      "%",
      0,
    );
    lines.push(`Recovery: ${formatNum(recovery.today, 0)}%${deltaStr}`);
  }

  if (hrv.today !== null) {
    const deltaStr = formatDeltaWithYesterday(
      hrv.delta,
      hrv.yesterday,
      hrv.yesterdayDate,
      "",
      0,
    );
    lines.push(`HRV: ${formatNum(hrv.today, 0)} ms${deltaStr}`);
  }

  if (rhr.today !== null) {
    const deltaStr = formatDeltaWithYesterday(
      rhr.delta,
      rhr.yesterday,
      rhr.yesterdayDate,
      "",
      0,
    );
    lines.push(`RHR: ${formatNum(rhr.today, 0)} bpm${deltaStr}`);
  }

  if (sleep.today !== null) {
    const sleepNightStr = sleep.yesterdayDate
      ? ` (${format(parseISO(sleep.yesterdayDate), "MMM d")}→${format(now, "d")} night)`
      : "";
    lines.push(`Sleep: ${formatMinutes(sleep.today)}${sleepNightStr}`);
  }

  if (steps.today !== null) {
    const incompleteFlag = isIncomplete
      ? ` [incomplete, as of ${timeStr}]`
      : "";
    lines.push(`Steps: ${formatSteps(steps.today)}${incompleteFlag}`);
  }

  if (weight.today !== null) {
    const deltaStr = formatDeltaWithYesterday(
      weight.delta,
      weight.yesterday,
      weight.yesterdayDate,
      " kg",
      2,
    );
    lines.push(`Weight: ${weight.today.toFixed(2)} kg${deltaStr}`);
  }

  return lines;
}

function formatAlerts(
  illnessRisk: ReturnType<typeof calculateIllnessRiskSignal>,
  decorrelationAlert: ReturnType<typeof calculateDecorrelationAlert>,
): string[] {
  const lines: string[] = [];
  lines.push(`## Alerts`);
  lines.push(``);

  const riskStatus =
    illnessRisk.riskLevel === "high"
      ? "[HIGH]"
      : illnessRisk.riskLevel === "moderate"
        ? "[MODERATE]"
        : "[LOW]";
  lines.push(
    `${riskStatus} Pre-Illness Risk: ${(illnessRisk.riskLevel ?? "N/A").toUpperCase()}`,
  );

  const decorStatus = decorrelationAlert.isDecorrelated ? "[ALERT]" : "[OK]";
  lines.push(
    `${decorStatus} HRV-RHR Decorrelation: ${decorrelationAlert.isDecorrelated ? "YES - monitor" : "No"}`,
  );

  if (illnessRisk.consecutiveDaysElevated > 0) {
    lines.push(
      `[WARNING] Consecutive Days Elevated: ${String(illnessRisk.consecutiveDaysElevated)}`,
    );
  }

  return lines;
}

function formatReadiness(
  recoveryMetrics: HealthAnalysis["recoveryMetrics"],
  activityMetrics: HealthAnalysis["activityMetrics"],
  illnessRiskLevel: string | null,
): string[] {
  const lines: string[] = [];
  lines.push(`## Readiness`);
  lines.push(``);

  const imbalance = recoveryMetrics.hrvRhrImbalance;
  const imbalanceStatus =
    imbalance !== null
      ? imbalance < -1
        ? "RECOVERED"
        : imbalance < 0
          ? "BALANCED"
          : imbalance < 1
            ? "MILD STRAIN"
            : "STRAINED"
      : "N/A";
  lines.push(`HRV-RHR Imbalance: ${formatNum(imbalance)} (${imbalanceStatus})`);

  const acwr = activityMetrics.acwr;
  const acwrStatus =
    acwr !== null
      ? acwr < 0.8
        ? "DETRAINING"
        : acwr <= 1.3
          ? "OPTIMAL"
          : acwr <= 1.5
            ? "CAUTION"
            : "INJURY RISK"
      : "N/A";
  lines.push(`ACWR: ${formatNum(acwr)} (${acwrStatus})`);

  const recommendation = getReadinessRecommendation(
    acwr,
    imbalance,
    illnessRiskLevel,
  );
  lines.push(`Recommendation: ${recommendation}`);

  return lines;
}

function formatLastWorkouts(workouts: WorkoutData[], now: Date): string[] {
  const lines: string[] = [];
  lines.push(`## Last Workouts`);
  lines.push(``);

  const { strength } = getLastWorkouts(workouts, now);

  if (strength) {
    const dateStr = format(parseISO(strength.date), "MMM d");
    const daysAgoStr =
      strength.daysAgo === 0 ? "today" : `${String(strength.daysAgo)} days ago`;
    const volumeStr =
      strength.volume !== null
        ? `, ${String(Math.round(strength.volume / 1000))}k kg`
        : "";
    lines.push(`- Strength: ${dateStr} (${daysAgoStr})${volumeStr}`);
  } else {
    lines.push(`- Strength: No data`);
  }

  return lines;
}

function formatAnalysisWindows(now: Date): string[] {
  const lines: string[] = [];
  lines.push(`## Analysis Windows`);
  lines.push(``);

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
  allMetrics: Record<string, Record<string, ComputedMetric>>,
): string[] {
  const lines: string[] = [];
  lines.push(`## Trends Summary`);
  lines.push(``);
  lines.push(`Short-term averages by mode (baseline windows in parentheses):`);
  lines.push(``);
  lines.push(
    `| Metric   | 6W (7d) | 6M (14d) | 2Y (30d) | 5Y (90d) | 7d Trend   |`,
  );
  lines.push(
    `|----------|---------|----------|----------|----------|------------|`,
  );

  const modes = ["recent", "quarter", "year", "all"] as const;

  const formatRow = (
    name: string,
    key: string,
    formatter: (v: number | null) => string,
  ): string => {
    const values = modes.map((m) => {
      const metric = allMetrics[m][key];
      return metric.baseline.shortTermMean;
    });

    const recentMetric = allMetrics.recent[key];
    const trendSlope = recentMetric.baseline.trendSlope;
    const trendStr =
      trendSlope !== null
        ? `${trendSlope >= 0 ? "+" : ""}${trendSlope.toFixed(2)}/d`
        : "N/A";

    const pad = (s: string, len: number) => s.padEnd(len);
    return `| ${pad(name, 8)} | ${pad(formatter(values[0]), 7)} | ${pad(formatter(values[1]), 8)} | ${pad(formatter(values[2]), 8)} | ${pad(formatter(values[3]), 8)} | ${pad(trendStr, 10)} |`;
  };

  lines.push(
    formatRow("HRV", "hrv", (v) => (v !== null ? v.toFixed(1) : "N/A")),
  );
  lines.push(
    formatRow("RHR", "rhr", (v) => (v !== null ? v.toFixed(1) : "N/A")),
  );
  lines.push(
    formatRow("Sleep", "sleep", (v) => (v !== null ? formatMinutes(v) : "N/A")),
  );
  lines.push(formatRow("Steps", "steps", (v) => formatSteps(v)));
  lines.push(
    formatRow("Weight", "weight", (v) => (v !== null ? v.toFixed(1) : "N/A")),
  );
  lines.push(
    formatRow("Recovery", "recovery", (v) =>
      v !== null ? `${v.toFixed(0)}%` : "N/A",
    ),
  );

  return lines;
}

function formatHealthScoreSummary(analysis: HealthAnalysis): string[] {
  const lines: string[] = [];
  const { healthScore } = analysis;

  lines.push(`## Health Score`);
  lines.push(``);
  lines.push(`Overall: ${formatNum(healthScore.overall, 2)}`);
  lines.push(`Recovery Core (70%): ${formatNum(healthScore.recoveryCore, 2)}`);
  lines.push(
    `Behavior Support (30%): ${formatNum(healthScore.behaviorSupport, 2)}`,
  );
  lines.push(``);

  lines.push(`Contributors:`);
  for (const c of healthScore.contributors) {
    const gateStatus = c.isGated ? " [GATED]" : "";
    lines.push(
      `- ${c.name}: z=${formatNum(c.goodnessZScore, 2)} (conf=${(c.confidence * 100).toFixed(0)}%)${gateStatus}`,
    );
  }

  return lines;
}

function formatClinicalMetrics(
  recoveryCapacity: ReturnType<typeof calculateRecoveryCapacity>,
  illnessRisk: ReturnType<typeof calculateIllnessRiskSignal>,
  decorrelationAlert: ReturnType<typeof calculateDecorrelationAlert>,
): string[] {
  const lines: string[] = [];
  lines.push(`## Clinical Metrics (Detailed)`);
  lines.push(``);

  lines.push(`### Recovery Capacity`);
  lines.push(
    `- Avg Recovery Days: ${recoveryCapacity.avgRecoveryDays !== null ? recoveryCapacity.avgRecoveryDays.toFixed(1) : "N/A"}`,
  );
  lines.push(
    `- Recovery Efficiency: ${recoveryCapacity.recoveryEfficiency !== null ? recoveryCapacity.recoveryEfficiency.toFixed(2) : "N/A"}`,
  );
  lines.push(
    `- High Strain Events: ${String(recoveryCapacity.highStrainEvents)}`,
  );
  lines.push(`- Recovered Events: ${String(recoveryCapacity.recoveredEvents)}`);
  lines.push(``);

  lines.push(`### Pre-Illness Components`);
  lines.push(
    `- Combined Deviation: ${illnessRisk.combinedDeviation !== null ? illnessRisk.combinedDeviation.toFixed(2) : "N/A"}`,
  );
  lines.push(
    `- HRV Drop: ${illnessRisk.components.hrvDrop !== null ? illnessRisk.components.hrvDrop.toFixed(2) : "N/A"}`,
  );
  lines.push(
    `- RHR Rise: ${illnessRisk.components.rhrRise !== null ? illnessRisk.components.rhrRise.toFixed(2) : "N/A"}`,
  );
  lines.push(
    `- Sleep Drop: ${illnessRisk.components.sleepDrop !== null ? illnessRisk.components.sleepDrop.toFixed(2) : "N/A"}`,
  );
  lines.push(``);

  lines.push(`### HRV-RHR Correlation`);
  lines.push(
    `- Current (14d): ${decorrelationAlert.currentCorrelation !== null ? decorrelationAlert.currentCorrelation.toFixed(3) : "N/A"}`,
  );
  lines.push(
    `- Baseline (60d): ${decorrelationAlert.baselineCorrelation !== null ? decorrelationAlert.baselineCorrelation.toFixed(3) : "N/A"}`,
  );
  lines.push(
    `- Delta: ${decorrelationAlert.correlationDelta !== null ? decorrelationAlert.correlationDelta.toFixed(3) : "N/A"}`,
  );

  return lines;
}

function formatGarminActivities(
  activities: GarminActivityData[],
  now: Date,
): string[] {
  const lines: string[] = [];
  lines.push(`## Garmin Activities (Last 30 Days)`);
  lines.push(``);

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

    lines.push(`### ${dateStr}${timeStr ? ` at ${timeStr}` : ""}: ${name}`);

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
      details.push(
        `Aerobic TE: ${activity.training_effect_aerobic.toFixed(1)}`,
      );
    }

    if (activity.training_effect_anaerobic !== null) {
      details.push(
        `Anaerobic TE: ${activity.training_effect_anaerobic.toFixed(1)}`,
      );
    }

    if (activity.vo2_max_value !== null) {
      details.push(`VO2 Max: ${activity.vo2_max_value.toFixed(1)}`);
    }

    for (const detail of details) {
      lines.push(`- ${detail}`);
    }
    lines.push(``);
  }

  return lines;
}

function formatWhoopWorkouts(
  workouts: WhoopWorkoutData[],
  now: Date,
): string[] {
  const lines: string[] = [];
  lines.push(`## Whoop Workouts (Last 30 Days)`);
  lines.push(``);

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
      details.push(
        `Distance: ${(workout.distance_meters / 1000).toFixed(2)} km`,
      );
    }

    if (
      workout.altitude_gain_meters !== null &&
      workout.altitude_gain_meters > 0
    ) {
      details.push(
        `Elevation Gain: ${String(Math.round(workout.altitude_gain_meters))} m`,
      );
    }

    for (const detail of details) {
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

function formatStrengthWorkoutsWithExercises(
  detailedWorkouts: WorkoutExerciseDetail[] | null,
  now: Date,
): string[] {
  const lines: string[] = [];
  lines.push(`## Strength Training (Hevy) - Last 30 Days`);
  lines.push(``);

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
    const dateStr = format(parseISO(day.date), "MMM d (EEE)");
    const volumeStr =
      day.totalVolume >= 1000
        ? `${(day.totalVolume / 1000).toFixed(1)}t`
        : `${String(Math.round(day.totalVolume))}kg`;

    lines.push(
      `### ${dateStr} - ${String(day.exercises.length)} exercises, ${String(day.totalSets)} sets, ${volumeStr} total`,
    );
    lines.push(``);

    for (const exercise of day.exercises) {
      const exerciseVolumeStr =
        exercise.total_volume >= 1000
          ? `${(exercise.total_volume / 1000).toFixed(1)}t`
          : `${String(Math.round(exercise.total_volume))}kg`;
      const rpeStr =
        exercise.avg_rpe !== null
          ? `, avg RPE ${exercise.avg_rpe.toFixed(1)}`
          : "";

      lines.push(
        `**${exercise.exercise}** (${String(exercise.total_sets)} sets, ${exerciseVolumeStr}${rpeStr})`,
      );

      for (const set of exercise.sets) {
        lines.push(`  - ${formatSetInfo(set)}`);
      }
      lines.push(``);
    }
  }

  return lines;
}

function formatStrengthWorkoutsDetailed(
  workouts: WorkoutData[],
  now: Date,
): string[] {
  const lines: string[] = [];
  lines.push(`## Strength Training (Hevy) (Last 30 Days)`);
  lines.push(``);

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
      workout.total_volume !== null ? Math.round(workout.total_volume) : 0;
    const sets = workout.total_sets ?? 0;

    lines.push(
      `### ${dateStr}: ${String(sets)} sets, ${String(volumeKg)} kg total volume`,
    );
    lines.push(``);
  }

  return lines;
}

function formatAnalysisDetails(
  modeConfig: { label: string; shortTerm: number; baseline: number },
  analysis: HealthAnalysis,
): string[] {
  const lines: string[] = [];
  const { recoveryMetrics, sleepMetrics, activityMetrics, weightMetrics } =
    analysis;

  lines.push(`### ${modeConfig.label} Analysis Details`);
  lines.push(``);

  lines.push(`**Recovery:**`);
  lines.push(
    `- Recovery CV: ${(recoveryMetrics.recoveryCV * 100).toFixed(1)}%`,
  );
  lines.push(
    `- Stress Load (${String(modeConfig.shortTerm)}d): ${formatNum(recoveryMetrics.stressLoadShort, 0)}`,
  );
  lines.push(
    `- Stress Load (${String(modeConfig.baseline)}d): ${formatNum(recoveryMetrics.stressLoadLong, 0)}`,
  );
  lines.push(``);

  lines.push(`**Sleep:**`);
  lines.push(`- Target: ${formatMinutes(sleepMetrics.targetSleep)}/night`);
  lines.push(
    `- Debt (${String(modeConfig.shortTerm)}d): ${formatMinutes(sleepMetrics.sleepDebtShort)}`,
  );
  lines.push(
    `- Surplus (${String(modeConfig.shortTerm)}d): ${formatMinutes(sleepMetrics.sleepSurplusShort)}`,
  );
  lines.push(`- CV: ${(sleepMetrics.sleepCV * 100).toFixed(1)}%`);
  lines.push(``);

  lines.push(`**Activity:**`);
  lines.push(`- Acute Load: ${formatNum(activityMetrics.acuteLoad, 1)}`);
  lines.push(`- Chronic Load: ${formatNum(activityMetrics.chronicLoad, 1)}`);
  lines.push(`- ACWR: ${formatNum(activityMetrics.acwr)}`);
  lines.push(`- Steps CV: ${(activityMetrics.stepsCV * 100).toFixed(1)}%`);
  lines.push(``);

  lines.push(`**Weight:**`);
  lines.push(
    `- EMA (${String(modeConfig.shortTerm)}d): ${weightMetrics.emaShort !== null ? `${weightMetrics.emaShort.toFixed(1)} kg` : "N/A"}`,
  );
  lines.push(
    `- EMA (${String(modeConfig.baseline)}d): ${weightMetrics.emaLong !== null ? `${weightMetrics.emaLong.toFixed(1)} kg` : "N/A"}`,
  );
  lines.push(
    `- Period Change: ${weightMetrics.periodChange !== null ? `${weightMetrics.periodChange >= 0 ? "+" : ""}${weightMetrics.periodChange.toFixed(2)} kg` : "N/A"}`,
  );
  lines.push(`- Volatility: ±${weightMetrics.volatilityShort.toFixed(2)} kg`);

  return lines;
}

function formatLastDaysTable(lastDays: DayMetrics[]): string[] {
  const lines: string[] = [];
  lines.push(`## Last ${String(lastDays.length)} Days Detail`);
  lines.push(``);
  lines.push(
    `| Date       | Rec% | HRV | RHR | Sleep   | Steps  | Strain | Stress | Cal   | Weight |`,
  );
  lines.push(
    `|------------|------|-----|-----|---------|--------|--------|--------|-------|--------|`,
  );

  for (const day of lastDays) {
    const dateStr = format(parseISO(day.date), "MMM d (EEE)");
    const rec = day.recovery !== null ? `${day.recovery.toFixed(0)}%` : "—";
    const hrv = day.hrv !== null ? day.hrv.toFixed(0) : "—";
    const rhr = day.rhr !== null ? day.rhr.toFixed(0) : "—";
    const sleep = day.sleep !== null ? formatMinutes(day.sleep) : "—";
    const steps = day.steps !== null ? formatSteps(day.steps) : "—";
    const strain = day.strain !== null ? day.strain.toFixed(1) : "—";
    const stress = day.stress !== null ? day.stress.toFixed(0) : "—";
    const cal = day.calories !== null ? day.calories.toFixed(0) : "—";
    const weight = day.weight !== null ? day.weight.toFixed(1) : "—";

    const pad = (s: string, len: number) => s.padEnd(len);
    lines.push(
      `| ${pad(dateStr, 10)} | ${pad(rec, 4)} | ${pad(hrv, 3)} | ${pad(rhr, 3)} | ${pad(sleep, 7)} | ${pad(steps, 6)} | ${pad(strain, 6)} | ${pad(stress, 6)} | ${pad(cal, 5)} | ${pad(weight, 6)} |`,
    );
  }

  return lines;
}

export function formatCombinedReport(
  data: HealthData | null,
  detailedWorkouts?: WorkoutExerciseDetail[] | null,
): string {
  if (!data) return "";

  const now = new Date();
  const sections: string[] = [];

  sections.push(`# Daily Health Brief`);
  sections.push(`Generated: ${format(now, "yyyy-MM-dd HH:mm")}`);
  sections.push(``);

  const hrvData = data.hrv.map((d) => ({ date: d.date, value: d.hrv_avg }));
  const rhrData = data.heart_rate.map((d) => ({
    date: d.date,
    value: d.resting_hr,
  }));
  const sleepData = data.sleep.map((d) => ({
    date: d.date,
    value: d.total_sleep_minutes,
  }));
  const recoveryData = data.whoop_recovery.map((d) => ({
    date: d.date,
    value: d.recovery_score,
  }));
  const stepsData = data.steps.map((d) => ({
    date: d.date,
    value: d.total_steps,
  }));
  const weightData = data.weight.map((d) => ({
    date: d.date,
    value: d.weight_kg,
  }));
  const strainData = data.whoop_cycle.map((d) => ({
    date: d.date,
    value: d.strain,
  }));
  const stressData = data.stress.map((d) => ({
    date: d.date,
    value: d.avg_stress,
  }));
  const caloriesData = data.whoop_cycle.map((d) => ({
    date: d.date,
    value: d.kilojoules !== null ? d.kilojoules * 0.239006 : null,
  }));

  const dayOverDay = calculateDayOverDayMetrics(
    hrvData,
    rhrData,
    sleepData,
    recoveryData,
    stepsData,
    weightData,
    strainData,
  );

  const dayCompleteness = calculateDayCompleteness(now);
  sections.push(...formatTodayStatus(dayOverDay, dayCompleteness, now));
  sections.push(``);

  const lastDays = calculateLastNDaysMetrics(
    hrvData,
    rhrData,
    sleepData,
    recoveryData,
    stepsData,
    weightData,
    strainData,
    stressData,
    caloriesData,
    3,
  );
  sections.push(...formatLastDaysTable(lastDays));
  sections.push(``);

  const recentCfg = TREND_MODES.recent;
  const recentOpts = getBaselineOptions("recent", recentCfg);
  const recentMetrics = computeAllMetrics(
    data,
    recentCfg.baseline,
    recentCfg.shortTerm,
    recentCfg.trendWindow,
    recentOpts,
  );

  const illnessRisk = calculateIllnessRiskSignal(
    recentMetrics.hrv.raw,
    recentMetrics.rhr.raw,
    recentMetrics.sleep.raw,
    recentCfg.baseline,
    3,
  );

  const decorrelationAlert = calculateDecorrelationAlert(
    recentMetrics.hrv.raw,
    recentMetrics.rhr.raw,
    14,
    recentCfg.baseline,
  );

  sections.push(...formatAlerts(illnessRisk, decorrelationAlert));
  sections.push(``);

  const recentAnalysis = computeHealthAnalysis(
    data,
    recentMetrics,
    recentCfg,
    recentOpts,
  );

  sections.push(
    ...formatReadiness(
      recentAnalysis.recoveryMetrics,
      recentAnalysis.activityMetrics,
      illnessRisk.riskLevel,
    ),
  );
  sections.push(``);

  sections.push(...formatLastWorkouts(data.workouts, now));
  sections.push(``);

  sections.push(`---`);
  sections.push(`# Detailed Training Log`);
  sections.push(``);

  if (detailedWorkouts && detailedWorkouts.length > 0) {
    sections.push(
      ...formatStrengthWorkoutsWithExercises(detailedWorkouts, now),
    );
  } else {
    sections.push(...formatStrengthWorkoutsDetailed(data.workouts, now));
  }
  sections.push(``);

  sections.push(...formatGarminActivities(data.garmin_activity, now));
  sections.push(``);

  sections.push(...formatWhoopWorkouts(data.whoop_workout, now));
  sections.push(``);

  sections.push(`---`);
  sections.push(``);

  sections.push(...formatAnalysisWindows(now));
  sections.push(``);

  sections.push(`---`);
  sections.push(``);

  const allMetrics: Record<string, Record<string, ComputedMetric>> = {};
  const allAnalyses: Record<string, HealthAnalysis> = {};

  for (const m of MODE_ORDER) {
    const cfg = TREND_MODES[m];
    const opts = getBaselineOptions(m, cfg);
    const metrics = computeAllMetrics(
      data,
      cfg.baseline,
      cfg.shortTerm,
      cfg.trendWindow,
      opts,
    );
    const analysis = computeHealthAnalysis(data, metrics, cfg, opts);
    allMetrics[m] = metrics;
    allAnalyses[m] = analysis;
  }

  sections.push(...formatTrendsSummaryTable(allMetrics));
  sections.push(``);

  sections.push(...formatHealthScoreSummary(allAnalyses.recent));
  sections.push(``);

  sections.push(`---`);
  sections.push(``);

  const recoveryCapacity = calculateRecoveryCapacity(
    recentMetrics.hrv.raw,
    recentMetrics.strain.raw,
    recentCfg.baseline,
  );

  sections.push(
    ...formatClinicalMetrics(recoveryCapacity, illnessRisk, decorrelationAlert),
  );
  sections.push(``);

  sections.push(`---`);
  sections.push(`# Detailed Analysis by Timeframe`);
  sections.push(``);

  for (const m of MODE_ORDER) {
    const cfg = TREND_MODES[m];
    sections.push(...formatAnalysisDetails(cfg, allAnalyses[m]));
    sections.push(``);
  }

  sections.push(`---`);
  sections.push(
    `Z-Score: <-2 very low, -1 to -2 low, -1 to +1 normal, +1 to +2 high, >+2 very high`,
  );
  sections.push(
    `ACWR: <0.8 detraining, 0.8-1.3 optimal, 1.3-1.5 caution, >1.5 injury risk`,
  );

  return sections.join("\n");
}
