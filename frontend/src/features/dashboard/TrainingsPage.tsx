import { useState, useMemo } from "react";
import { useDetailedWorkouts } from "../../hooks/useDetailedWorkouts";
import { useHealthData } from "../../hooks/useHealthData";
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
} from "lucide-react";
import { format, parseISO } from "date-fns";
import type {
  WorkoutExerciseDetail,
  WhoopWorkoutData,
  GarminActivityData,
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
  date: string;
  items: TrainingItem[];
}

function groupAllTrainingsByDate(
  strengthWorkouts: WorkoutExerciseDetail[],
  garminActivities: GarminActivityData[],
  whoopWorkouts: WhoopWorkoutData[],
): DailyTrainings[] {
  const byDate = new Map<string, TrainingItem[]>();

  const strengthByDate = new Map<string, WorkoutExerciseDetail[]>();
  for (const w of strengthWorkouts) {
    const existing = strengthByDate.get(w.date);
    if (existing) {
      existing.push(w);
    } else {
      strengthByDate.set(w.date, [w]);
    }
  }

  for (const [date, exercises] of strengthByDate) {
    const items = byDate.get(date) ?? [];
    items.push({ type: "strength", data: exercises, sortKey: date });
    byDate.set(date, items);
  }

  for (const activity of garminActivities) {
    const items = byDate.get(activity.date) ?? [];
    items.push({
      type: "garmin",
      data: activity,
      sortKey: activity.start_time ?? activity.date,
    });
    byDate.set(activity.date, items);
  }

  for (const workout of whoopWorkouts) {
    const items = byDate.get(workout.date) ?? [];
    items.push({
      type: "whoop",
      data: workout,
      sortKey: workout.start_time ?? workout.date,
    });
    byDate.set(workout.date, items);
  }

  return Array.from(byDate.entries())
    .map(([date, items]) => ({
      date,
      items: items.sort((a, b) => b.sortKey.localeCompare(a.sortKey)),
    }))
    .sort((a, b) => b.date.localeCompare(a.date));
}

function formatWorkoutDate(dateStr: string): string {
  return format(parseISO(dateStr), "EEEE, MMMM d, yyyy");
}

function StrengthWorkoutInline({
  exercises,
}: {
  exercises: WorkoutExerciseDetail[];
}) {
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
              const parts: string[] = [];

              const setLabel =
                set.set_type && set.set_type !== "normal"
                  ? `Set ${String(set.set_index + 1)} (${set.set_type})`
                  : `Set ${String(set.set_index + 1)}`;
              parts.push(setLabel);

              if (set.weight_kg !== null) {
                parts.push(`${String(set.weight_kg)}kg`);
              } else {
                parts.push("bodyweight");
              }

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
  label: string;
  seconds: number;
  color: string;
}

function HRZoneBar({ zones }: { zones: HRZoneEntry[] }) {
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

function WhoopWorkoutInline({ workout }: { workout: WhoopWorkoutData }) {
  const startTime = workout.start_time
    ? format(parseISO(workout.start_time), "h:mm a")
    : null;
  const calories =
    workout.kilojoules !== null ? Math.round(workout.kilojoules / 4.184) : null;
  const distanceKm =
    workout.distance_meters !== null
      ? (workout.distance_meters / 1000).toFixed(2)
      : null;

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

  if (durationStr !== null) {
    details.push(durationStr);
  }
  if (workout.strain !== null) {
    details.push(
      `Strain ${workout.strain.toFixed(1)}/${String(WHOOP_MAX_STRAIN)}`,
    );
  }
  if (calories !== null) {
    details.push(`${String(calories)} kcal`);
  }
  if (workout.avg_heart_rate !== null) {
    details.push(`Avg HR ${String(workout.avg_heart_rate)}`);
  }
  if (distanceKm !== null) {
    details.push(`${distanceKm} km`);
  }
  if (workout.percent_recorded !== null && workout.percent_recorded < 100) {
    details.push(`${workout.percent_recorded.toFixed(0)}% recorded`);
  }

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
      </div>
      <p className="text-sm text-muted-foreground mt-1">
        {details.join(" · ")}
      </p>
      <HRZoneBar zones={buildWhoopZones(workout)} />
    </div>
  );
}

function GarminActivityInline({ activity }: { activity: GarminActivityData }) {
  const startTime = activity.start_time
    ? format(parseISO(activity.start_time), "h:mm a")
    : null;

  const distanceKm =
    activity.distance_meters !== null
      ? (activity.distance_meters / 1000).toFixed(2)
      : null;

  const pace =
    shouldShowPace(activity.avg_speed_mps, activity.distance_meters) &&
    activity.avg_speed_mps !== null
      ? formatPace(activity.avg_speed_mps)
      : null;

  const details: string[] = [];

  if (activity.duration_seconds !== null) {
    details.push(formatDuration(activity.duration_seconds));
  }
  if (distanceKm !== null) {
    details.push(`${distanceKm} km`);
  }
  if (pace !== null) {
    details.push(pace);
  }
  if (activity.avg_heart_rate !== null) {
    details.push(`Avg HR ${String(activity.avg_heart_rate)}`);
  }
  if (activity.calories !== null) {
    details.push(`${String(activity.calories)} kcal`);
  }
  if (
    activity.elevation_gain_meters !== null &&
    activity.elevation_gain_meters > 0
  ) {
    details.push(`↑${String(Math.round(activity.elevation_gain_meters))}m`);
  }

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

function DailyTrainingCard({ day }: { day: DailyTrainings }) {
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

export function TrainingsPage() {
  const [periodDays, setPeriodDays] = useState<PeriodDays>(30);

  const {
    data: workouts,
    isLoading,
    isFetching,
    error,
  } = useDetailedWorkouts(periodDays);
  const { data: healthData, isFetching: healthFetching } =
    useHealthData(periodDays);

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

  if (isLoading) {
    return (
      <div className="space-y-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Trainings</h1>
            <p className="text-muted-foreground mt-1">
              Detailed workout log from Hevy, Garmin, and Whoop
            </p>
          </div>
          <div className="flex items-center gap-3">
            <PeriodSelector period={periodDays} setPeriod={setPeriodDays} />
          </div>
        </div>
        <LoadingState message="Loading workouts..." />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Trainings</h1>
          <p className="text-muted-foreground mt-1">
            Detailed workout log from Hevy, Garmin, and Whoop
          </p>
        </div>
        <div className="flex items-center gap-3">
          {(isFetching || healthFetching) && (
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
          )}
          <PeriodSelector period={periodDays} setPeriod={setPeriodDays} />
        </div>
      </div>

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
              <h3 className="text-lg font-medium mb-2">No workouts found</h3>
              <p className="text-muted-foreground">
                No workout data available for the selected period. Sync your
                Hevy, Garmin, or Whoop account to see your training history.
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function PeriodSelector({
  period,
  setPeriod,
}: {
  period: PeriodDays;
  setPeriod: (p: PeriodDays) => void;
}) {
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
