import { useState, useMemo } from "react";
import { useDetailedWorkouts } from "../../hooks/useDetailedWorkouts";
import { useHealthData } from "../../hooks/useHealthData";
import { useGarminActivities } from "../../hooks/useGarminActivities";
import { Button } from "../../components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../../components/ui/card";
import { LoadingState } from "../../components/ui/loading-state";
import { ErrorCard } from "../../components/ui/error-card";
import { Dumbbell, Calendar, Flame, Activity } from "lucide-react";
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

interface DailyStrengthWorkout {
  date: string;
  exercises: WorkoutExerciseDetail[];
}

function groupWorkoutsByDate(
  workouts: WorkoutExerciseDetail[],
): DailyStrengthWorkout[] {
  const grouped = new Map<string, WorkoutExerciseDetail[]>();

  for (const workout of workouts) {
    const existing = grouped.get(workout.date);
    if (existing) {
      existing.push(workout);
    } else {
      grouped.set(workout.date, [workout]);
    }
  }

  return Array.from(grouped.entries())
    .map(([date, exercises]) => ({ date, exercises }))
    .sort((a, b) => b.date.localeCompare(a.date));
}

function formatWorkoutDate(dateStr: string): string {
  return format(parseISO(dateStr), "EEEE, MMMM d, yyyy");
}

function StrengthWorkoutBlock({ workout }: { workout: DailyStrengthWorkout }) {
  const totalVolume = workout.exercises.reduce(
    (sum, ex) => sum + ex.total_volume,
    0,
  );
  const totalSets = workout.exercises.reduce(
    (sum, ex) => sum + ex.total_sets,
    0,
  );

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <Dumbbell className={`h-5 w-5 ${ACTIVITY_COLORS.strength}`} />
          <CardTitle className="text-lg">
            {formatWorkoutDate(workout.date)}
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          {String(workout.exercises.length)} exercises · {String(totalSets)}{" "}
          sets · {formatVolume(totalVolume)} total volume
        </p>

        {workout.exercises.map((exercise) => (
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

                // Set number and type
                const setLabel =
                  set.set_type && set.set_type !== "normal"
                    ? `Set ${String(set.set_index + 1)} (${set.set_type})`
                    : `Set ${String(set.set_index + 1)}`;
                parts.push(setLabel);

                // Weight
                if (set.weight_kg !== null) {
                  parts.push(`${String(set.weight_kg)}kg`);
                } else {
                  parts.push("bodyweight");
                }

                // Reps
                if (set.reps !== null) {
                  parts.push(`× ${String(set.reps)} reps`);
                }

                // RPE - always show if available
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
      </CardContent>
    </Card>
  );
}

function WhoopWorkoutBlock({ workout }: { workout: WhoopWorkoutData }) {
  const startTime = workout.start_time
    ? format(parseISO(workout.start_time), "h:mm a")
    : null;
  const calories =
    workout.kilojoules !== null ? Math.round(workout.kilojoules / 4.184) : null;
  const distanceKm =
    workout.distance_meters !== null
      ? (workout.distance_meters / 1000).toFixed(2)
      : null;

  const lines: string[] = [];

  lines.push(`Activity: ${workout.sport_name ?? DEFAULT_ACTIVITY_NAME}`);
  if (startTime !== null) {
    lines.push(`Time: ${startTime}`);
  }

  if (workout.strain !== null) {
    lines.push(
      `Strain: ${workout.strain.toFixed(1)} / ${String(WHOOP_MAX_STRAIN)}`,
    );
  }

  if (calories !== null) {
    lines.push(`Energy: ${String(calories)} kcal`);
  }

  if (workout.kilojoules !== null) {
    lines.push(`Kilojoules: ${workout.kilojoules.toFixed(1)} kJ`);
  }

  if (workout.avg_heart_rate !== null) {
    lines.push(`Average Heart Rate: ${String(workout.avg_heart_rate)} bpm`);
  }

  if (workout.max_heart_rate !== null) {
    lines.push(`Max Heart Rate: ${String(workout.max_heart_rate)} bpm`);
  }

  if (distanceKm !== null) {
    lines.push(`Distance: ${distanceKm} km`);
  }

  if (
    workout.altitude_gain_meters !== null &&
    workout.altitude_gain_meters > 0
  ) {
    lines.push(
      `Elevation Gain: ${String(Math.round(workout.altitude_gain_meters))} m`,
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <Flame className={`h-5 w-5 ${ACTIVITY_COLORS.cardio}`} />
          <CardTitle className="text-lg">
            {formatWorkoutDate(workout.date)}
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-1 text-sm">
          {lines.map((line, i) => (
            <p key={`line-${String(i)}`} className="text-muted-foreground">
              {line}
            </p>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function GarminActivityBlock({ activity }: { activity: GarminActivityData }) {
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

  const lines: string[] = [];

  lines.push(
    `Activity: ${activity.activity_name ?? activity.activity_type ?? DEFAULT_ACTIVITY_NAME}`,
  );

  if (startTime) {
    lines.push(`Time: ${startTime}`);
  }

  if (activity.duration_seconds !== null) {
    lines.push(`Duration: ${formatDuration(activity.duration_seconds)}`);
  }

  if (distanceKm !== null) {
    lines.push(`Distance: ${distanceKm} km`);
  }

  if (pace !== null) {
    lines.push(`Pace: ${pace}`);
  }

  if (activity.avg_heart_rate !== null) {
    lines.push(`Average Heart Rate: ${String(activity.avg_heart_rate)} bpm`);
  }

  if (activity.max_heart_rate !== null) {
    lines.push(`Max Heart Rate: ${String(activity.max_heart_rate)} bpm`);
  }

  if (activity.calories !== null) {
    lines.push(`Calories: ${String(activity.calories)} kcal`);
  }

  if (
    activity.elevation_gain_meters !== null &&
    activity.elevation_gain_meters > 0
  ) {
    lines.push(
      `Elevation Gain: ${String(Math.round(activity.elevation_gain_meters))} m`,
    );
  }

  if (
    activity.elevation_loss_meters !== null &&
    activity.elevation_loss_meters > 0
  ) {
    lines.push(
      `Elevation Loss: ${String(Math.round(activity.elevation_loss_meters))} m`,
    );
  }

  if (activity.avg_power_watts !== null) {
    lines.push(
      `Average Power: ${String(Math.round(activity.avg_power_watts))} W`,
    );
  }

  if (activity.max_power_watts !== null) {
    lines.push(`Max Power: ${String(Math.round(activity.max_power_watts))} W`);
  }

  if (activity.training_effect_aerobic !== null) {
    lines.push(
      `Aerobic Training Effect: ${activity.training_effect_aerobic.toFixed(1)}`,
    );
  }

  if (activity.training_effect_anaerobic !== null) {
    lines.push(
      `Anaerobic Training Effect: ${activity.training_effect_anaerobic.toFixed(1)}`,
    );
  }

  if (activity.vo2_max_value !== null) {
    lines.push(`VO2 Max: ${activity.vo2_max_value.toFixed(1)}`);
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <Activity className={`h-5 w-5 ${ACTIVITY_COLORS.activity}`} />
          <CardTitle className="text-lg">
            {formatWorkoutDate(activity.date)}
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-1 text-sm">
          {lines.map((line, i) => (
            <p key={`line-${String(i)}`} className="text-muted-foreground">
              {line}
            </p>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export function TrainingsPage() {
  const [periodDays, setPeriodDays] = useState<PeriodDays>(30);

  const { data: workouts, isLoading, error } = useDetailedWorkouts(periodDays);
  const { data: healthData } = useHealthData(periodDays);
  const { data: garminActivities } = useGarminActivities(periodDays);

  const dailyStrengthWorkouts = useMemo(() => {
    if (!workouts) return [];
    return groupWorkoutsByDate(workouts);
  }, [workouts]);

  const whoopWorkoutRaw = healthData?.whoop_workout;
  const whoopWorkouts = useMemo(() => {
    if (!whoopWorkoutRaw) return [];
    return [...whoopWorkoutRaw].sort((a, b) =>
      (b.start_time ?? b.date).localeCompare(a.start_time ?? a.date),
    );
  }, [whoopWorkoutRaw]);

  const sortedGarminActivities = useMemo(() => {
    if (!garminActivities) return [];
    return [...garminActivities].sort((a, b) =>
      (b.start_time ?? b.date).localeCompare(a.start_time ?? a.date),
    );
  }, [garminActivities]);

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
          <PeriodSelector period={periodDays} setPeriod={setPeriodDays} />
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
        <PeriodSelector period={periodDays} setPeriod={setPeriodDays} />
      </div>

      {dailyStrengthWorkouts.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <Dumbbell className="h-5 w-5" />
            Strength Training (Hevy)
          </h2>
          <div className="space-y-4">
            {dailyStrengthWorkouts.map((workout) => (
              <StrengthWorkoutBlock key={workout.date} workout={workout} />
            ))}
          </div>
        </section>
      )}

      {sortedGarminActivities.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Activities (Garmin)
          </h2>
          <div className="space-y-4">
            {sortedGarminActivities.map((activity) => (
              <GarminActivityBlock
                key={activity.activity_id}
                activity={activity}
              />
            ))}
          </div>
        </section>
      )}

      {whoopWorkouts.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <Flame className="h-5 w-5" />
            Cardio & Activity (Whoop)
          </h2>
          <div className="space-y-4">
            {whoopWorkouts.map((workout, i) => (
              <WhoopWorkoutBlock
                key={`${workout.date}-${workout.start_time ?? "unknown"}-${String(i)}`}
                workout={workout}
              />
            ))}
          </div>
        </section>
      )}

      {dailyStrengthWorkouts.length === 0 &&
        sortedGarminActivities.length === 0 &&
        whoopWorkouts.length === 0 && (
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
