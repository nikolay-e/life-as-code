import { useState, useMemo } from "react";
import { useDetailedWorkouts } from "../../hooks/useDetailedWorkouts";
import { useHealthData } from "../../hooks/useHealthData";
import { Button } from "../../components/ui/button";
import { LoadingState } from "../../components/ui/loading-state";
import { ErrorCard } from "../../components/ui/error-card";
import { Loader2 } from "lucide-react";
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
  type PeriodDays,
} from "../../lib/constants";
import { Masthead } from "../../components/luxury/Masthead";
import { SectionHead, SerifEm } from "../../components/luxury/SectionHead";

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

function isToday(dateStr: string): boolean {
  return dateStr === format(new Date(), "yyyy-MM-dd");
}

function formatLedgerDate(dateStr: string): string {
  const d = parseISO(dateStr);
  return `${format(d, "d MMM").toLowerCase()} · ${format(d, "EEE").toLowerCase()}`;
}

function whoopDurationSec(workout: WhoopWorkoutData): number | null {
  if (!workout.start_time || !workout.end_time) return null;
  const sec = Math.round(
    (new Date(workout.end_time).getTime() -
      new Date(workout.start_time).getTime()) /
      1000,
  );
  return sec > 0 ? sec : null;
}

interface LedgerEntry {
  readonly key: string;
  readonly dateStr: string;
  readonly name: string;
  readonly source: string;
  readonly strain: string | null;
  readonly duration: string | null;
}

function strengthEntry(
  date: string,
  exercises: WorkoutExerciseDetail[],
): LedgerEntry {
  const totalSets = exercises.reduce((sum, ex) => sum + ex.total_sets, 0);
  const totalVolume = exercises.reduce((sum, ex) => sum + ex.total_volume, 0);
  return {
    key: `strength-${date}`,
    dateStr: date,
    name: `Strength · ${String(exercises.length)} lifts · ${String(totalSets)} sets`,
    source: "Hevy",
    strain: formatVolume(totalVolume),
    duration: null,
  };
}

function garminEntry(activity: GarminActivityData): LedgerEntry {
  const distanceKm =
    activity.distance_meters === null
      ? null
      : (activity.distance_meters / 1000).toFixed(2);
  const baseName =
    activity.activity_name ?? activity.activity_type ?? DEFAULT_ACTIVITY_NAME;
  const name =
    distanceKm !== null ? `${baseName} · ${distanceKm} km` : baseName;
  return {
    key: `garmin-${activity.activity_id}`,
    dateStr: activity.date,
    name,
    source: "Garmin",
    strain:
      activity.calories !== null ? `${String(activity.calories)} kcal` : null,
    duration:
      activity.duration_seconds !== null
        ? formatDuration(activity.duration_seconds)
        : null,
  };
}

function whoopEntry(workout: WhoopWorkoutData): LedgerEntry {
  const durSec = whoopDurationSec(workout);
  return {
    key: `whoop-${workout.date}-${workout.start_time ?? "n"}`,
    dateStr: workout.date,
    name: workout.sport_name ?? DEFAULT_ACTIVITY_NAME,
    source: "Whoop",
    strain:
      workout.strain !== null
        ? `${workout.strain.toFixed(1)}/${String(WHOOP_MAX_STRAIN)}`
        : null,
    duration: durSec !== null ? formatDuration(durSec) : null,
  };
}

function toLedgerEntries(days: DailyTrainings[]): LedgerEntry[] {
  const out: LedgerEntry[] = [];
  for (const day of days) {
    for (const item of day.items) {
      if (item.type === "strength") {
        out.push(strengthEntry(day.date, item.data));
      } else if (item.type === "garmin") {
        out.push(garminEntry(item.data));
      } else {
        out.push(whoopEntry(item.data));
      }
    }
  }
  return out;
}

interface SessionCardProps {
  readonly day: DailyTrainings;
}

function strengthSummary(exercises: WorkoutExerciseDetail[]): {
  totalSets: number;
  totalVolume: number;
  avgRpe: number | null;
} {
  const totalSets = exercises.reduce((sum, ex) => sum + ex.total_sets, 0);
  const totalVolume = exercises.reduce((sum, ex) => sum + ex.total_volume, 0);
  const rpes = exercises
    .map((ex) => ex.avg_rpe)
    .filter((r): r is number => r !== null);
  const avgRpe =
    rpes.length > 0 ? rpes.reduce((a, b) => a + b, 0) / rpes.length : null;
  return { totalSets, totalVolume, avgRpe };
}

function StrengthSessionCard({
  exercises,
}: {
  readonly exercises: WorkoutExerciseDetail[];
}) {
  const { totalSets, totalVolume, avgRpe } = strengthSummary(exercises);
  return (
    <article className="border border-foreground p-7 lg:p-9 bg-background">
      <header className="flex items-baseline justify-between border-b border-border pb-4 mb-6">
        <span className="type-mono-eyebrow text-foreground/80">
          strength session
        </span>
        <span className="type-mono-label text-muted-foreground">Hevy</span>
      </header>

      <div className="grid grid-cols-3 gap-6 mb-7">
        <SessionStat label="working sets" value={String(totalSets)} />
        <SessionStat label="tonnage" value={formatVolume(totalVolume)} />
        <SessionStat
          label="avg rpe"
          value={avgRpe !== null ? avgRpe.toFixed(1) : "—"}
        />
      </div>

      <ul className="divide-y divide-border">
        {exercises.map((exercise, idx) => {
          const setSummary = exercise.sets[0];
          const weight =
            setSummary.weight_kg !== null
              ? `${String(setSummary.weight_kg)} kg`
              : "bodyweight";
          const reps =
            setSummary.reps !== null ? ` × ${String(setSummary.reps)}` : "";
          const load = `${String(exercise.total_sets)} ×${reps} · ${weight}`;
          return (
            <li
              key={`${exercise.date}-${exercise.exercise}`}
              className="grid grid-cols-[auto_1fr_auto] gap-4 items-baseline py-3.5"
            >
              <span className="type-mono-label text-muted-foreground w-7">
                {String(idx + 1).padStart(2, "0")}
              </span>
              <span
                className="font-serif italic text-[17px] text-foreground"
                style={{
                  fontVariationSettings: '"opsz" 144, "SOFT" 100',
                  fontWeight: 400,
                }}
              >
                {exercise.exercise}
              </span>
              <span
                className="font-mono text-[12px] text-foreground tracking-wide text-right"
                style={{ fontFeatureSettings: '"lnum","tnum"' }}
              >
                {load}
              </span>
            </li>
          );
        })}
      </ul>
    </article>
  );
}

function CardioSessionCard({
  item,
}: {
  readonly item:
    | { type: "garmin"; data: GarminActivityData }
    | { type: "whoop"; data: WhoopWorkoutData };
}) {
  let name: string;
  let source: string;
  let durationSec: number | null;
  let strain: string | null;
  let calories: number | null;
  let avgHr: number | null;
  let distanceKm: string | null;
  let pace: string | null;

  if (item.type === "garmin") {
    const a = item.data;
    name = a.activity_name ?? a.activity_type ?? DEFAULT_ACTIVITY_NAME;
    source = "Garmin";
    durationSec = a.duration_seconds;
    strain = null;
    calories = a.calories;
    avgHr = a.avg_heart_rate;
    distanceKm =
      a.distance_meters !== null ? (a.distance_meters / 1000).toFixed(2) : null;
    pace =
      shouldShowPace(a.avg_speed_mps, a.distance_meters) &&
      a.avg_speed_mps !== null
        ? formatPace(a.avg_speed_mps)
        : null;
  } else {
    const w = item.data;
    name = w.sport_name ?? DEFAULT_ACTIVITY_NAME;
    source = "Whoop";
    durationSec = whoopDurationSec(w);
    strain =
      w.strain !== null
        ? `${w.strain.toFixed(1)}/${String(WHOOP_MAX_STRAIN)}`
        : null;
    calories = w.kilojoules === null ? null : Math.round(w.kilojoules / 4.184);
    avgHr = w.avg_heart_rate;
    distanceKm =
      w.distance_meters !== null ? (w.distance_meters / 1000).toFixed(2) : null;
    pace = null;
  }

  return (
    <article className="border border-foreground p-7 lg:p-9 bg-background">
      <header className="flex items-baseline justify-between border-b border-border pb-4 mb-6">
        <span className="type-mono-eyebrow text-foreground/80">
          conditioning
        </span>
        <span className="type-mono-label text-muted-foreground">{source}</span>
      </header>

      <h3
        className="font-serif italic text-[clamp(22px,2.4vw,30px)] leading-tight text-foreground mb-6"
        style={{
          fontVariationSettings: '"opsz" 144, "SOFT" 100',
          fontWeight: 400,
        }}
      >
        {name}
      </h3>

      <ul className="grid grid-cols-2 gap-x-6 gap-y-4">
        {durationSec !== null && (
          <SessionStat label="duration" value={formatDuration(durationSec)} />
        )}
        {strain !== null && (
          <SessionStat
            label={`strain · ${String(WHOOP_MAX_STRAIN)}`}
            value={strain.split("/")[0]}
          />
        )}
        {distanceKm !== null && (
          <SessionStat label="distance" value={`${distanceKm} km`} />
        )}
        {pace !== null && <SessionStat label="pace" value={pace} />}
        {avgHr !== null && (
          <SessionStat label="avg hr" value={`${String(avgHr)} bpm`} />
        )}
        {calories !== null && (
          <SessionStat label="calories" value={`${String(calories)} kcal`} />
        )}
      </ul>
    </article>
  );
}

function SessionCard({ day }: SessionCardProps) {
  const primary = day.items[0];
  if (primary.type === "strength") {
    return <StrengthSessionCard exercises={primary.data} />;
  }
  return <CardioSessionCard item={primary} />;
}

function SessionStat({
  label,
  value,
}: {
  readonly label: string;
  readonly value: string;
}) {
  return (
    <li className="flex flex-col gap-1.5">
      <span className="type-mono-label text-muted-foreground">{label}</span>
      <span
        className="font-serif text-[26px] leading-none tracking-[-0.02em] text-foreground"
        style={{
          fontVariationSettings: '"opsz" 144, "SOFT" 60',
          fontWeight: 350,
          fontFeatureSettings: '"lnum","tnum"',
        }}
      >
        {value}
      </span>
    </li>
  );
}

interface TodayHeroProps {
  readonly day: DailyTrainings;
}

function TodayHero({ day }: TodayHeroProps) {
  const primary = day.items[0];
  let verdictLead: string;
  let verdictEm: string;
  let brief: string;

  if (primary.type === "strength") {
    const { totalSets, totalVolume } = strengthSummary(primary.data);
    verdictLead = "Lifted.";
    verdictEm = "Heavy work logged.";
    brief = `${String(primary.data.length)} lifts across ${String(
      totalSets,
    )} working sets — total tonnage ${formatVolume(totalVolume)}. Posterior chain and compounds tracked, ready for the next block.`;
  } else if (primary.type === "garmin") {
    const a = primary.data;
    const baseName =
      a.activity_name ?? a.activity_type ?? DEFAULT_ACTIVITY_NAME;
    verdictLead = `${baseName}.`;
    verdictEm = "Aerobic deposit.";
    const dur =
      a.duration_seconds !== null ? formatDuration(a.duration_seconds) : "—";
    const km =
      a.distance_meters !== null
        ? `${(a.distance_meters / 1000).toFixed(1)} km`
        : "";
    brief = `Today's session ran ${dur}${km ? ` · ${km}` : ""}. Heart-rate zones logged via Garmin and folded into the day's load total.`;
  } else {
    const w = primary.data;
    const sport = w.sport_name ?? DEFAULT_ACTIVITY_NAME;
    verdictLead = `${sport}.`;
    verdictEm = "Strain banked.";
    brief = `Whoop captured ${
      w.strain !== null
        ? `strain ${w.strain.toFixed(1)}/${String(WHOOP_MAX_STRAIN)}`
        : "the session"
    }. Recovery debit accounted for in tomorrow's window.`;
  }

  const sessionCount = String(day.items.length);
  const sessionLabel = day.items.length === 1 ? "session" : "sessions";

  return (
    <section className="grid grid-cols-1 lg:grid-cols-[1.05fr_0.95fr] gap-10 lg:gap-16 items-start py-14 lg:py-20 border-b border-border">
      <div>
        <span className="type-mono-eyebrow text-muted-foreground block mb-5">
          Today's prescription
        </span>
        <h1
          className="font-serif leading-[0.88] tracking-[-0.045em] text-[clamp(44px,8.2vw,104px)]"
          style={{
            fontVariationSettings: '"opsz" 144, "SOFT" 100',
            fontWeight: 350,
          }}
        >
          {verdictLead} <SerifEm>{verdictEm}</SerifEm>
        </h1>
        <p
          className="mt-7 font-serif text-[clamp(16px,1.45vw,19px)] leading-[1.55] text-muted-foreground max-w-[48ch]"
          style={{
            fontVariationSettings: '"opsz" 14, "SOFT" 30',
            fontWeight: 380,
          }}
        >
          {brief}
        </p>
        <div className="mt-7 flex items-center gap-2.5">
          <span className="type-mono-label text-muted-foreground">logged</span>
          <span
            className="font-serif italic text-[17px]"
            style={{
              fontVariationSettings: '"opsz" 144, "SOFT" 100',
              fontWeight: 400,
            }}
          >
            {sessionCount} {sessionLabel} ·{" "}
            {format(parseISO(day.date), "EEEE d LLLL")}
          </span>
        </div>
      </div>

      <SessionCard day={day} />
    </section>
  );
}

interface LedgerProps {
  readonly entries: LedgerEntry[];
}

function Ledger({ entries }: LedgerProps) {
  return (
    <div className="border-t border-border">
      {entries.map((entry) => (
        <div
          key={entry.key}
          className="grid grid-cols-[120px_1fr_auto_auto] gap-4 sm:gap-6 items-baseline py-5 border-b border-border"
        >
          <span
            className="font-mono text-[12px] text-muted-foreground tracking-wide uppercase"
            style={{ fontFeatureSettings: '"lnum","tnum"' }}
          >
            {formatLedgerDate(entry.dateStr)}
          </span>
          <span
            className="font-serif italic text-[17px] text-foreground"
            style={{
              fontVariationSettings: '"opsz" 144, "SOFT" 100',
              fontWeight: 400,
            }}
          >
            {entry.name}
            <span className="ml-3 type-mono-label text-muted-foreground not-italic">
              {entry.source}
            </span>
          </span>
          <span
            className="font-serif text-[26px] leading-none tracking-[-0.02em] text-foreground text-right min-w-[90px]"
            style={{
              fontVariationSettings: '"opsz" 144, "SOFT" 60',
              fontWeight: 350,
              fontFeatureSettings: '"lnum","tnum"',
            }}
          >
            {entry.strain ?? "—"}
          </span>
          <span
            className="font-mono text-[12px] text-foreground tracking-wide text-right min-w-[64px]"
            style={{ fontFeatureSettings: '"lnum","tnum"' }}
          >
            {entry.duration ?? "—"}
          </span>
        </div>
      ))}
    </div>
  );
}

function EmptyLedger() {
  return (
    <div className="border-t border-b border-border py-20 text-center">
      <p
        className="font-serif italic text-[clamp(22px,2.4vw,30px)] text-muted-foreground"
        style={{
          fontVariationSettings: '"opsz" 144, "SOFT" 100',
          fontWeight: 400,
        }}
      >
        No sessions on the books.
      </p>
      <p className="type-mono-label text-muted-foreground mt-4">
        sync hevy · garmin · whoop in settings to populate the ledger
      </p>
    </div>
  );
}

interface PeriodSelectorProps {
  readonly period: PeriodDays;
  readonly setPeriod: (p: PeriodDays) => void;
}

function PeriodSelector({ period, setPeriod }: PeriodSelectorProps) {
  return (
    <div className="flex flex-wrap gap-0">
      {PERIOD_OPTIONS.map((opt, idx) => (
        <Button
          key={opt.days}
          variant={period === opt.days ? "default" : "outline"}
          size="sm"
          onClick={() => {
            setPeriod(opt.days);
          }}
          className={idx === 0 ? "" : "-ml-px"}
        >
          {opt.label}
        </Button>
      ))}
    </div>
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

  const todayDate = new Date();
  const dateLine = format(todayDate, "d LLLL yyyy");
  const weekday = format(todayDate, "EEEE");

  if (isLoading) {
    return (
      <div className="space-y-0">
        <Masthead
          leftLine={`№ ${format(todayDate, "DDD")} · ${weekday}`}
          title={
            <>
              The <SerifEm>training ledger</SerifEm>
            </>
          }
          rightLine={dateLine}
        />
        <div className="py-20">
          <LoadingState message="Loading workouts..." />
        </div>
      </div>
    );
  }

  const todayDay = dailyTrainings.find((d) => isToday(d.date));
  const ledgerDays = todayDay
    ? dailyTrainings.filter((d) => d.date !== todayDay.date)
    : dailyTrainings;
  const ledgerEntries = toLedgerEntries(ledgerDays);

  return (
    <div className="space-y-0">
      <Masthead
        leftLine="Section III · Movement"
        title={
          <>
            The <SerifEm>training ledger</SerifEm>
          </>
        }
        rightLine={
          <>
            {dateLine}
            <br />
            sources · hevy · garmin · whoop
          </>
        }
      />

      {todayDay && <TodayHero day={todayDay} />}

      <section className="pt-12">
        <SectionHead
          title={
            <>
              Recent <SerifEm>work</SerifEm>
            </>
          }
          meta={
            <>
              {ledgerEntries.length} sessions · {periodDays}-day window
              <br />
              via hevy + garmin + whoop
            </>
          }
        />

        <div className="flex items-center justify-between gap-4 pb-5">
          <span className="type-mono-eyebrow text-muted-foreground">
            window
          </span>
          <div className="flex items-center gap-3">
            {(isFetching || healthFetching) && (
              <Loader2 className="h-3 w-3 animate-spin text-brass" />
            )}
            <PeriodSelector period={periodDays} setPeriod={setPeriodDays} />
          </div>
        </div>

        {ledgerEntries.length > 0 ? (
          <Ledger entries={ledgerEntries} />
        ) : (
          <EmptyLedger />
        )}
      </section>
    </div>
  );
}
