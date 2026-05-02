import { useState, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useDetailedWorkouts } from "../../hooks/useDetailedWorkouts";
import { useHealthData } from "../../hooks/useHealthData";
import { useRacePredictions } from "../../hooks/useRacePredictions";
import { Button } from "../../components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../../components/ui/card";
import { LoadingState } from "../../components/ui/loading-state";
import { ErrorCard } from "../../components/ui/error-card";
import {
  Dumbbell,
  Calendar,
  Flame,
  Activity,
  Heart,
  Loader2,
  Trophy,
  Timer,
  ArrowUp,
  ArrowDown,
  ClipboardList,
} from "lucide-react";
import { format, parseISO } from "date-fns";
import { ProgramsPanel } from "./programs/ProgramsPage";
import { cn } from "../../lib/utils";
import type {
  WorkoutExerciseDetail,
  WhoopWorkoutData,
  GarminActivityData,
  GarminRacePredictionData,
} from "../../types/api";
import {
  formatDuration,
  formatPace,
  formatVolume,
  shouldShowPace,
} from "../../lib/formatters";
import {
  PERIOD_OPTIONS,
  WHOOP_MAX_STRAIN,
  DEFAULT_ACTIVITY_NAME,
  ACTIVITY_COLORS,
  type PeriodDays,
} from "../../lib/constants";

type TrainingItem =
  | { type: "strength"; data: WorkoutExerciseDetail[]; sortKey: string }
  | { type: "garmin"; data: GarminActivityData; sortKey: string }
  | { type: "whoop"; data: WhoopWorkoutData; sortKey: string };

interface DailyTrainings {
  readonly date: string;
  readonly items: TrainingItem[];
}

function addToDateMap(
  byDate: Map<string, TrainingItem[]>,
  date: string,
  item: TrainingItem,
): void {
  const items = byDate.get(date) ?? [];
  items.push(item);
  byDate.set(date, items);
}

function groupStrengthByDate(
  strengthWorkouts: WorkoutExerciseDetail[],
): Map<string, WorkoutExerciseDetail[]> {
  const strengthByDate = new Map<string, WorkoutExerciseDetail[]>();
  for (const w of strengthWorkouts) {
    const existing = strengthByDate.get(w.date);
    if (existing) {
      existing.push(w);
    } else {
      strengthByDate.set(w.date, [w]);
    }
  }
  return strengthByDate;
}

function groupAllTrainingsByDate(
  strengthWorkouts: WorkoutExerciseDetail[],
  garminActivities: GarminActivityData[],
  whoopWorkouts: WhoopWorkoutData[],
): DailyTrainings[] {
  const byDate = new Map<string, TrainingItem[]>();

  for (const [date, exercises] of groupStrengthByDate(strengthWorkouts)) {
    addToDateMap(byDate, date, {
      type: "strength",
      data: exercises,
      sortKey: date,
    });
  }

  for (const activity of garminActivities) {
    addToDateMap(byDate, activity.date, {
      type: "garmin",
      data: activity,
      sortKey: activity.start_time ?? activity.date,
    });
  }

  for (const workout of whoopWorkouts) {
    addToDateMap(byDate, workout.date, {
      type: "whoop",
      data: workout,
      sortKey: workout.start_time ?? workout.date,
    });
  }

  return Array.from(byDate.entries())
    .map(([date, items]) => ({
      date,
      items: items.toSorted((a, b) => b.sortKey.localeCompare(a.sortKey)),
    }))
    .sort((a, b) => b.date.localeCompare(a.date));
}

function formatWorkoutDate(dateStr: string): string {
  return format(parseISO(dateStr), "EEEE, MMMM d, yyyy");
}

interface StrengthWorkoutInlineProps {
  readonly exercises: WorkoutExerciseDetail[];
}

function StrengthWorkoutInline({ exercises }: StrengthWorkoutInlineProps) {
  const totalVolume = exercises.reduce((sum, ex) => sum + ex.total_volume, 0);
  const totalSets = exercises.reduce((sum, ex) => sum + ex.total_sets, 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Dumbbell className={`h-5 w-5 ${ACTIVITY_COLORS.strength}`} />
        <span className="font-semibold">Strength Training (Hevy)</span>
        <span className="text-sm text-muted-foreground">
          {String(exercises.length)} exercises · {String(totalSets)} sets ·{" "}
          {formatVolume(totalVolume)}
        </span>
      </div>

      {exercises.map((exercise) => (
        <div
          key={`${exercise.date}-${exercise.exercise}`}
          className={`border-l-2 ${ACTIVITY_COLORS.strengthBorder} pl-4`}
        >
          <p className="font-semibold text-base">{exercise.exercise}</p>
          <p className="text-xs text-muted-foreground mb-2">
            {String(exercise.total_sets)} sets ·{" "}
            {formatVolume(exercise.total_volume)} volume
            {exercise.avg_rpe !== null &&
              ` · avg RPE ${exercise.avg_rpe.toFixed(1)}`}
          </p>

          <div className="space-y-1 text-sm">
            {exercise.sets.map((set) => {
              const setLabel =
                set.set_type && set.set_type !== "normal"
                  ? `Set ${String(set.set_index + 1)} (${set.set_type})`
                  : `Set ${String(set.set_index + 1)}`;

              const weightStr =
                set.weight_kg === null
                  ? "bodyweight"
                  : `${String(set.weight_kg)}kg`;

              const parts: string[] = [setLabel, weightStr];

              if (set.reps !== null) {
                parts.push(`× ${String(set.reps)} reps`);
              }

              if (set.rpe !== null) {
                parts.push(`@ RPE ${String(set.rpe)}`);
              }

              return (
                <p
                  key={`${exercise.exercise}-set-${String(set.set_index)}`}
                  className="text-muted-foreground"
                >
                  {parts.join(" ")}
                </p>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

const WHOOP_ZONE_COLORS = [
  "bg-gray-400",
  "bg-blue-400",
  "bg-green-400",
  "bg-yellow-400",
  "bg-orange-400",
  "bg-red-500",
] as const;

const GARMIN_ZONE_COLORS = [
  "bg-blue-400",
  "bg-green-400",
  "bg-yellow-400",
  "bg-orange-400",
  "bg-red-500",
] as const;

interface HRZoneEntry {
  readonly label: string;
  readonly seconds: number;
  readonly color: string;
}

interface HRZoneBarProps {
  readonly zones: HRZoneEntry[];
}

function HRZoneBar({ zones }: HRZoneBarProps) {
  const nonZero = zones.filter((z) => z.seconds > 0);
  if (nonZero.length === 0) return null;

  const totalSeconds = nonZero.reduce((sum, z) => sum + z.seconds, 0);
  if (totalSeconds === 0) return null;

  return (
    <div className="mt-2 space-y-1">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Heart className="h-3 w-3" />
        <span>HR Zones</span>
      </div>
      <div className="flex h-3 rounded-full overflow-hidden">
        {nonZero.map((z) => {
          const pct = (z.seconds / totalSeconds) * 100;
          if (pct < 0.5) return null;
          return (
            <div
              key={z.label}
              className={`${z.color} transition-all`}
              style={{ width: `${String(pct)}%` }}
              title={`${z.label}: ${String(Math.round(z.seconds / 60))}m (${pct.toFixed(0)}%)`}
            />
          );
        })}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
        {nonZero.map((z) => (
          <span key={z.label} className="flex items-center gap-1">
            <span className={`inline-block w-2 h-2 rounded-full ${z.color}`} />
            {z.label}: {String(Math.round(z.seconds / 60))}m
          </span>
        ))}
      </div>
    </div>
  );
}

function buildWhoopZones(workout: WhoopWorkoutData): HRZoneEntry[] {
  const millis = [
    workout.zone_zero_millis,
    workout.zone_one_millis,
    workout.zone_two_millis,
    workout.zone_three_millis,
    workout.zone_four_millis,
    workout.zone_five_millis,
  ];
  return millis.map((m, i) => ({
    label: `Zone ${String(i)}`,
    seconds: (m ?? 0) / 1000,
    color: WHOOP_ZONE_COLORS[i],
  }));
}

function buildGarminZones(activity: GarminActivityData): HRZoneEntry[] {
  const secs = [
    activity.hr_zone_one_seconds,
    activity.hr_zone_two_seconds,
    activity.hr_zone_three_seconds,
    activity.hr_zone_four_seconds,
    activity.hr_zone_five_seconds,
  ];
  return secs.map((s, i) => ({
    label: `Zone ${String(i + 1)}`,
    seconds: s ?? 0,
    color: GARMIN_ZONE_COLORS[i],
  }));
}

interface WhoopWorkoutInlineProps {
  readonly workout: WhoopWorkoutData;
}

function buildWhoopDetails(workout: WhoopWorkoutData): string[] {
  const calories =
    workout.kilojoules === null ? null : Math.round(workout.kilojoules / 4.184);
  const distanceKm =
    workout.distance_meters === null
      ? null
      : (workout.distance_meters / 1000).toFixed(2);

  let durationStr: string | null = null;
  if (workout.start_time && workout.end_time) {
    const durationSec = Math.round(
      (new Date(workout.end_time).getTime() -
        new Date(workout.start_time).getTime()) /
        1000,
    );
    if (durationSec > 0) {
      durationStr = formatDuration(durationSec);
    }
  }

  const details: string[] = [];
  if (durationStr !== null) details.push(durationStr);
  if (workout.strain !== null) {
    details.push(
      `Strain ${workout.strain.toFixed(1)}/${String(WHOOP_MAX_STRAIN)}`,
    );
  }
  if (calories !== null) details.push(`${String(calories)} kcal`);
  if (workout.avg_heart_rate !== null) {
    details.push(`Avg HR ${String(workout.avg_heart_rate)}`);
  }
  if (distanceKm !== null) details.push(`${distanceKm} km`);
  if (
    workout.altitude_change_meters !== null &&
    workout.altitude_change_meters !== 0
  ) {
    details.push(
      `Net altitude: ${String(Math.round(workout.altitude_change_meters))} m`,
    );
  }
  if (workout.percent_recorded !== null && workout.percent_recorded < 100) {
    details.push(`${workout.percent_recorded.toFixed(0)}% recorded`);
  }
  return details;
}

function WhoopWorkoutInline({ workout }: WhoopWorkoutInlineProps) {
  const startTime = workout.start_time
    ? format(parseISO(workout.start_time), "h:mm a")
    : null;
  const endTime = workout.end_time
    ? format(parseISO(workout.end_time), "h:mm a")
    : null;
  const details = buildWhoopDetails(workout);

  return (
    <div className={`border-l-2 ${ACTIVITY_COLORS.cardioBorder} pl-4`}>
      <div className="flex items-center gap-2">
        <Flame className={`h-4 w-4 ${ACTIVITY_COLORS.cardio}`} />
        <span className="font-semibold">
          {workout.sport_name ?? DEFAULT_ACTIVITY_NAME}
        </span>
        <span className="text-xs text-muted-foreground">Whoop</span>
        {startTime && (
          <span className="text-xs text-muted-foreground">at {startTime}</span>
        )}
        {endTime && (
          <span className="text-xs text-muted-foreground">
            ended at {endTime}
          </span>
        )}
      </div>
      <p className="text-sm text-muted-foreground mt-1">
        {details.join(" · ")}
      </p>
      <HRZoneBar zones={buildWhoopZones(workout)} />
    </div>
  );
}

interface GarminActivityInlineProps {
  readonly activity: GarminActivityData;
}

function buildGarminPower(activity: GarminActivityData): string | null {
  if (activity.avg_power_watts === null && activity.max_power_watts === null) {
    return null;
  }
  const parts: string[] = [];
  if (activity.avg_power_watts !== null) {
    parts.push(`Avg Pwr ${String(Math.round(activity.avg_power_watts))} W`);
  }
  if (activity.max_power_watts !== null) {
    parts.push(`Max ${String(Math.round(activity.max_power_watts))} W`);
  }
  return parts.join(", ");
}

function buildGarminTrainingEffect(
  activity: GarminActivityData,
): string | null {
  const aerobic = activity.training_effect_aerobic;
  const anaerobic = activity.training_effect_anaerobic;
  if (aerobic !== null && anaerobic !== null) {
    return `Aerobic TE: ${aerobic.toFixed(1)} | Anaerobic TE: ${anaerobic.toFixed(1)}`;
  }
  if (aerobic !== null) return `Aerobic TE: ${aerobic.toFixed(1)}`;
  if (anaerobic !== null) return `Anaerobic TE: ${anaerobic.toFixed(1)}`;
  return null;
}

function pickGarminPace(activity: GarminActivityData): string | null {
  if (
    !shouldShowPace(activity.avg_speed_mps, activity.distance_meters) ||
    activity.avg_speed_mps === null
  ) {
    return null;
  }
  return formatPace(activity.avg_speed_mps);
}

function pickGarminMaxPace(activity: GarminActivityData): string | null {
  const isRunning =
    activity.activity_type?.toLowerCase().includes("run") ?? false;
  if (
    !isRunning ||
    !shouldShowPace(activity.max_speed_mps, activity.distance_meters) ||
    activity.max_speed_mps === null
  ) {
    return null;
  }
  return formatPace(activity.max_speed_mps);
}

function pickElevationGain(activity: GarminActivityData): string | null {
  if (
    activity.elevation_gain_meters === null ||
    activity.elevation_gain_meters <= 0
  ) {
    return null;
  }
  return `↑${String(Math.round(activity.elevation_gain_meters))}m`;
}

function pickElevationLoss(activity: GarminActivityData): string | null {
  if (
    activity.elevation_loss_meters === null ||
    activity.elevation_loss_meters <= 0
  ) {
    return null;
  }
  return `↓${String(Math.round(activity.elevation_loss_meters))}m`;
}

function buildGarminDetails(activity: GarminActivityData): string[] {
  const distanceKm =
    activity.distance_meters === null
      ? null
      : (activity.distance_meters / 1000).toFixed(2);

  const details: string[] = [];
  if (activity.duration_seconds !== null) {
    details.push(formatDuration(activity.duration_seconds));
  }
  if (distanceKm !== null) details.push(`${distanceKm} km`);
  const pace = pickGarminPace(activity);
  if (pace !== null) details.push(pace);
  const maxPace = pickGarminMaxPace(activity);
  if (maxPace !== null) details.push(`Max Pace: ${maxPace}`);
  if (activity.avg_heart_rate !== null) {
    details.push(`Avg HR ${String(activity.avg_heart_rate)}`);
  }
  if (activity.calories !== null) {
    details.push(`${String(activity.calories)} kcal`);
  }
  const elevGain = pickElevationGain(activity);
  if (elevGain !== null) details.push(elevGain);
  const elevLoss = pickElevationLoss(activity);
  if (elevLoss !== null) details.push(elevLoss);
  const power = buildGarminPower(activity);
  if (power !== null) details.push(power);
  const te = buildGarminTrainingEffect(activity);
  if (te !== null) details.push(te);
  if (activity.vo2_max_value !== null) {
    details.push(`VO2max from activity: ${activity.vo2_max_value.toFixed(1)}`);
  }
  return details;
}

function GarminActivityInline({ activity }: GarminActivityInlineProps) {
  const startTime = activity.start_time
    ? format(parseISO(activity.start_time), "h:mm a")
    : null;
  const details = buildGarminDetails(activity);

  return (
    <div className={`border-l-2 ${ACTIVITY_COLORS.activityBorder} pl-4`}>
      <div className="flex items-center gap-2">
        <Activity className={`h-4 w-4 ${ACTIVITY_COLORS.activity}`} />
        <span className="font-semibold">
          {activity.activity_name ??
            activity.activity_type ??
            DEFAULT_ACTIVITY_NAME}
        </span>
        <span className="text-xs text-muted-foreground">Garmin</span>
        {startTime && (
          <span className="text-xs text-muted-foreground">at {startTime}</span>
        )}
      </div>
      <p className="text-sm text-muted-foreground mt-1">
        {details.join(" · ")}
      </p>
      <HRZoneBar zones={buildGarminZones(activity)} />
    </div>
  );
}

function formatRaceTime(seconds: number): string {
  const totalSec = Math.round(seconds);
  const hours = Math.floor(totalSec / 3600);
  const minutes = Math.floor((totalSec % 3600) / 60);
  const secs = totalSec % 60;
  if (hours > 0) {
    return `${String(hours)}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${String(minutes)}:${String(secs).padStart(2, "0")}`;
}

function classifyVo2Max(value: number): string {
  if (value > 55) return "Excellent";
  if (value >= 45) return "Good";
  if (value >= 35) return "Fair";
  return "Poor";
}

type RaceDistanceKey =
  | "prediction_5k_seconds"
  | "prediction_10k_seconds"
  | "prediction_half_marathon_seconds"
  | "prediction_marathon_seconds";

interface RaceDistance {
  readonly key: RaceDistanceKey;
  readonly label: string;
}

const RACE_DISTANCES: readonly RaceDistance[] = [
  { key: "prediction_5k_seconds", label: "5K" },
  { key: "prediction_10k_seconds", label: "10K" },
  { key: "prediction_half_marathon_seconds", label: "Half Marathon" },
  { key: "prediction_marathon_seconds", label: "Marathon" },
] as const;

function findLatestNonNullRecord(
  records: GarminRacePredictionData[],
  field: keyof GarminRacePredictionData,
): GarminRacePredictionData | null {
  const sorted = [...records].sort((a, b) => b.date.localeCompare(a.date));
  return sorted.find((r) => r[field] !== null) ?? null;
}

function findRecordNearDate(
  records: GarminRacePredictionData[],
  field: keyof GarminRacePredictionData,
  targetIso: string,
): GarminRacePredictionData | null {
  const candidates = records.filter(
    (r) => r[field] !== null && r.date <= targetIso,
  );
  if (candidates.length === 0) return null;
  return candidates.reduce<GarminRacePredictionData>(
    (best, cur) => (cur.date > best.date ? cur : best),
    candidates[0],
  );
}

interface RaceCardProps {
  readonly label: string;
  readonly latestSeconds: number;
  readonly priorSeconds: number | null;
}

function deltaToneClass(improved: boolean, worsened: boolean): string {
  if (improved) return "text-green-600";
  if (worsened) return "text-red-600";
  return "text-muted-foreground";
}

function deltaArrowIcon(improved: boolean, worsened: boolean) {
  if (improved) return <ArrowDown className="h-3 w-3" />;
  if (worsened) return <ArrowUp className="h-3 w-3" />;
  return null;
}

function deltaText(deltaSec: number, improved: boolean): string {
  if (deltaSec === 0) return "no change";
  const sign = improved ? "-" : "+";
  return `${sign}${formatRaceTime(Math.abs(deltaSec))} vs 30d ago`;
}

function RaceCard({ label, latestSeconds, priorSeconds }: RaceCardProps) {
  const deltaSec = priorSeconds === null ? null : latestSeconds - priorSeconds;
  const improved = deltaSec !== null && deltaSec < 0;
  const worsened = deltaSec !== null && deltaSec > 0;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2 text-muted-foreground">
          <Timer className="h-4 w-4" />
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">
          {formatRaceTime(latestSeconds)}
        </div>
        {deltaSec !== null && (
          <div
            className={`mt-1 flex items-center gap-1 text-xs ${deltaToneClass(improved, worsened)}`}
          >
            {deltaArrowIcon(improved, worsened)}
            <span>{deltaText(deltaSec, improved)}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

interface Vo2MaxCardProps {
  readonly value: number;
}

function Vo2MaxCard({ value }: Vo2MaxCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2 text-muted-foreground">
          <Activity className="h-4 w-4" />
          VO2max
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value.toFixed(1)}</div>
        <div className="text-xs text-muted-foreground mt-1">
          ml/kg/min · {classifyVo2Max(value)}
        </div>
      </CardContent>
    </Card>
  );
}

interface RacePredictionsSectionProps {
  readonly predictions: GarminRacePredictionData[];
}

function RacePredictionsSection({ predictions }: RacePredictionsSectionProps) {
  const cards = useMemo(() => {
    const result: { label: string; latest: number; prior: number | null }[] =
      [];
    for (const dist of RACE_DISTANCES) {
      const latest = findLatestNonNullRecord(predictions, dist.key);
      if (latest === null) continue;
      const value = latest[dist.key];
      if (value === null) continue;
      const latestDate = new Date(latest.date);
      latestDate.setDate(latestDate.getDate() - 30);
      const targetIso = latestDate.toISOString().slice(0, 10);
      const prior = findRecordNearDate(predictions, dist.key, targetIso);
      const priorValue = prior?.[dist.key] ?? null;
      result.push({ label: dist.label, latest: value, prior: priorValue });
    }
    return result;
  }, [predictions]);

  const latestVo2 = useMemo(
    () => findLatestNonNullRecord(predictions, "vo2_max_value"),
    [predictions],
  );

  const vo2Value = latestVo2?.vo2_max_value ?? null;

  if (cards.length === 0 && vo2Value === null) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <Trophy className="h-5 w-5 text-yellow-500" />
          Race Predictions
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {cards.map((c) => (
            <RaceCard
              key={c.label}
              label={c.label}
              latestSeconds={c.latest}
              priorSeconds={c.prior}
            />
          ))}
          {vo2Value !== null && <Vo2MaxCard value={vo2Value} />}
        </div>
      </CardContent>
    </Card>
  );
}

interface DailyTrainingCardProps {
  readonly day: DailyTrainings;
}

function DailyTrainingCard({ day }: DailyTrainingCardProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <Calendar className="h-5 w-5 text-muted-foreground" />
          {formatWorkoutDate(day.date)}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {day.items.map((item, idx) => {
          if (item.type === "strength") {
            return (
              <StrengthWorkoutInline
                key={`strength-${day.date}`}
                exercises={item.data}
              />
            );
          }
          if (item.type === "garmin") {
            return (
              <GarminActivityInline
                key={`garmin-${item.data.activity_id}`}
                activity={item.data}
              />
            );
          }
          return (
            <WhoopWorkoutInline
              key={`whoop-${item.data.date}-${item.data.start_time ?? String(idx)}`}
              workout={item.data}
            />
          );
        })}
      </CardContent>
    </Card>
  );
}

type TrainingsTab = "log" | "program";

function isTrainingsTab(v: string | null): v is TrainingsTab {
  return v === "log" || v === "program";
}

export function TrainingsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const tab: TrainingsTab = isTrainingsTab(tabParam) ? tabParam : "log";

  const setTab = (next: TrainingsTab) => {
    setSearchParams(
      (prev) => {
        const updated = new URLSearchParams(prev);
        if (next === "log") {
          updated.delete("tab");
        } else {
          updated.set("tab", next);
        }
        return updated;
      },
      { replace: true },
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Trainings</h1>
        <p className="text-muted-foreground mt-1">
          {tab === "log"
            ? "Detailed workout log from Hevy, Garmin, and Whoop"
            : "Plan that drives your strength logs — references the Hevy exercise library"}
        </p>
      </div>

      <div
        role="tablist"
        aria-label="Trainings sections"
        className="inline-flex items-center gap-1 p-1 bg-muted/50 rounded-lg"
      >
        <TabButton
          label="Workouts"
          icon={Dumbbell}
          active={tab === "log"}
          onClick={() => {
            setTab("log");
          }}
        />
        <TabButton
          label="Program"
          icon={ClipboardList}
          active={tab === "program"}
          onClick={() => {
            setTab("program");
          }}
        />
      </div>

      {tab === "log" ? <WorkoutLogTab /> : <ProgramsPanel />}
    </div>
  );
}

interface TabButtonProps {
  readonly label: string;
  readonly icon: React.ComponentType<{ className?: string }>;
  readonly active: boolean;
  readonly onClick: () => void;
}

function TabButton({ label, icon: Icon, active, onClick }: TabButtonProps) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
        active
          ? "bg-background text-foreground shadow-sm"
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      <Icon className="h-4 w-4" />
      {label}
    </button>
  );
}

function WorkoutLogTab() {
  const [periodDays, setPeriodDays] = useState<PeriodDays>(30);

  const {
    data: workouts,
    isLoading,
    isFetching,
    error,
  } = useDetailedWorkouts(periodDays);
  const { data: healthData, isFetching: healthFetching } =
    useHealthData(periodDays);
  const { data: racePredictions } = useRacePredictions(365);

  const dailyTrainings = useMemo(() => {
    return groupAllTrainingsByDate(
      workouts ?? [],
      healthData?.garmin_activity ?? [],
      healthData?.whoop_workout ?? [],
    );
  }, [workouts, healthData?.garmin_activity, healthData?.whoop_workout]);

  if (error) {
    return (
      <ErrorCard message={`Failed to load workout data: ${error.message}`} />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-end gap-3">
        {(isFetching || healthFetching) && (
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
        )}
        <PeriodSelector period={periodDays} setPeriod={setPeriodDays} />
      </div>

      {isLoading ? (
        <LoadingState message="Loading workouts..." />
      ) : (
        <>
          {racePredictions && racePredictions.length > 0 && (
            <RacePredictionsSection predictions={racePredictions} />
          )}

          {dailyTrainings.length > 0 ? (
            <div className="space-y-4">
              {dailyTrainings.map((day) => (
                <DailyTrainingCard key={day.date} day={day} />
              ))}
            </div>
          ) : (
            <Card>
              <CardContent className="pt-6">
                <div className="text-center py-8">
                  <Dumbbell className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <h2 className="text-lg font-medium mb-2">
                    No workouts found
                  </h2>
                  <p className="text-muted-foreground">
                    No workout data available for the selected period. Sync your
                    Hevy, Garmin, or Whoop account to see your training history.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

interface PeriodSelectorProps {
  readonly period: PeriodDays;
  readonly setPeriod: (p: PeriodDays) => void;
}

function PeriodSelector({ period, setPeriod }: PeriodSelectorProps) {
  return (
    <div className="flex items-center gap-2 p-1 bg-muted/50 rounded-lg">
      <Calendar className="h-4 w-4 text-muted-foreground ml-2" />
      {PERIOD_OPTIONS.map((opt) => (
        <Button
          key={opt.days}
          variant={period === opt.days ? "default" : "ghost"}
          size="sm"
          onClick={() => {
            setPeriod(opt.days);
          }}
        >
          {opt.label}
        </Button>
      ))}
    </div>
  );
}
