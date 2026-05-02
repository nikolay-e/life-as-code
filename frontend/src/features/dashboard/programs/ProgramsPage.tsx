import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "../../../lib/api";
import { programKeys } from "../../../lib/query-keys";
import {
  Plus,
  Pencil,
  Archive,
  Play,
  Trash2,
  CalendarRange,
  Dumbbell,
  Layers,
  Target,
  ChevronDown,
  ChevronRight,
  Clock,
  Gauge,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import { Button } from "../../../components/ui/button";
import { LoadingState } from "../../../components/ui/loading-state";
import { ErrorCard } from "../../../components/ui/error-card";
import {
  useActivateWorkoutProgram,
  useActiveWorkoutProgram,
  useArchiveWorkoutProgram,
  useDeleteWorkoutProgram,
  useWorkoutProgram,
  useWorkoutPrograms,
} from "../../../hooks/useWorkoutPrograms";
import { ProgramEditor } from "./ProgramEditor";
import type {
  ProgramExerciseData,
  WorkoutProgramDetail,
  WorkoutProgramSummary,
} from "../../../types/api";
import { cn } from "../../../lib/utils";

type Mode =
  | { kind: "view" }
  | { kind: "create" }
  | { kind: "edit"; program: WorkoutProgramDetail };

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

function durationLabel(start: string, end: string | null): string {
  if (!start) return "";
  const startDate = new Date(start);
  const endDate = end ? new Date(end) : new Date();
  const days = Math.max(
    1,
    Math.round((endDate.getTime() - startDate.getTime()) / 86400000),
  );
  if (days < 14) return `${String(days)}d`;
  const weeks = Math.round(days / 7);
  return `${String(weeks)}w`;
}

function repsLabel(ex: ProgramExerciseData): string {
  if (ex.target_reps_min == null && ex.target_reps_max == null) return "";
  if (
    ex.target_reps_min != null &&
    ex.target_reps_max != null &&
    ex.target_reps_min !== ex.target_reps_max
  ) {
    return `${String(ex.target_reps_min)}-${String(ex.target_reps_max)}`;
  }
  return String(ex.target_reps_max ?? ex.target_reps_min);
}

function rpeLabel(ex: ProgramExerciseData): string {
  if (ex.target_rpe_min == null && ex.target_rpe_max == null) return "";
  if (
    ex.target_rpe_min != null &&
    ex.target_rpe_max != null &&
    ex.target_rpe_min !== ex.target_rpe_max
  ) {
    return `RPE ${String(ex.target_rpe_min)}-${String(ex.target_rpe_max)}`;
  }
  const v = ex.target_rpe_max ?? ex.target_rpe_min;
  return `RPE ${String(v)}`;
}

/**
 * Programs panel — designed to be embedded as a tab inside TrainingsPage.
 * Renders no page-level header; lifts a single "New program" CTA into the
 * panel itself and falls back to the editor view when create/edit is active.
 */
export function ProgramsPanel() {
  const [mode, setMode] = useState<Mode>({ kind: "view" });
  const activeQuery = useActiveWorkoutProgram();
  const listQuery = useWorkoutPrograms();

  if (mode.kind === "create" || mode.kind === "edit") {
    return (
      <ProgramEditor
        program={mode.kind === "edit" ? mode.program : null}
        onSaved={() => {
          setMode({ kind: "view" });
        }}
        onCancel={() => {
          setMode({ kind: "view" });
        }}
      />
    );
  }

  if (activeQuery.isLoading || listQuery.isLoading) {
    return <LoadingState message="Loading programs..." />;
  }

  if (activeQuery.isError || listQuery.isError) {
    const message =
      activeQuery.error instanceof Error
        ? activeQuery.error.message
        : listQuery.error instanceof Error
          ? listQuery.error.message
          : "Failed to load programs";
    return <ErrorCard message={message} />;
  }

  const active = activeQuery.data;
  const all = listQuery.data ?? [];
  const history = all.filter((p) => !p.is_active);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <p className="text-sm text-muted-foreground">
          Plan a mesocycle, run it, swap to the next one. History is kept.
        </p>
        <Button
          onClick={() => {
            setMode({ kind: "create" });
          }}
          size="sm"
        >
          <Plus className="h-4 w-4 mr-1" />
          New program
        </Button>
      </div>

      <ActiveProgramSection
        program={active}
        onEdit={(p) => {
          setMode({ kind: "edit", program: p });
        }}
      />

      <HistorySection
        history={history}
        onEdit={(p) => {
          setMode({ kind: "edit", program: p });
        }}
      />
    </div>
  );
}

interface ActiveProgramSectionProps {
  readonly program: WorkoutProgramDetail | null | undefined;
  readonly onEdit: (program: WorkoutProgramDetail) => void;
}

function ActiveProgramSection({ program, onEdit }: ActiveProgramSectionProps) {
  const archiveMutation = useArchiveWorkoutProgram();

  const handleArchive = async () => {
    if (!program) return;
    if (
      // eslint-disable-next-line no-alert
      !confirm("End this program? It will move to history.")
    ) {
      return;
    }
    try {
      await archiveMutation.mutateAsync(program.id);
      toast.success("Program archived");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to archive");
    }
  };

  if (!program) {
    return (
      <Card>
        <CardContent className="py-10 text-center space-y-3">
          <Dumbbell className="h-10 w-10 text-muted-foreground mx-auto" />
          <h2 className="font-semibold">No active program</h2>
          <p className="text-sm text-muted-foreground">
            Create one to start tracking your training plan.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-primary/40">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-primary/15 text-primary">
                Active
              </span>
              {program.goal && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-muted text-foreground">
                  {program.goal}
                </span>
              )}
            </div>
            <CardTitle className="text-xl">{program.name}</CardTitle>
            {program.description && (
              <p className="text-sm text-muted-foreground whitespace-pre-line">
                {program.description}
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                onEdit(program);
              }}
            >
              <Pencil className="h-4 w-4 mr-1" />
              Edit
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleArchive}
              disabled={archiveMutation.isPending}
            >
              <Archive className="h-4 w-4 mr-1" />
              End program
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <Stat
            icon={CalendarRange}
            label="Started"
            value={formatDate(program.start_date)}
          />
          <Stat
            icon={Clock}
            label="Running"
            value={durationLabel(program.start_date, program.end_date)}
          />
          <Stat icon={Layers} label="Days" value={String(program.day_count)} />
          <Stat
            icon={Dumbbell}
            label="Exercises"
            value={String(program.exercise_count)}
          />
        </div>
        <ProgramDaysView program={program} />
      </CardContent>
    </Card>
  );
}

interface StatProps {
  readonly icon: React.ComponentType<{ className?: string }>;
  readonly label: string;
  readonly value: string;
}

function Stat({ icon: Icon, label, value }: StatProps) {
  return (
    <div className="rounded-lg border bg-muted/20 px-3 py-2">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        <span>{label}</span>
      </div>
      <div className="text-base font-semibold mt-0.5">{value}</div>
    </div>
  );
}

interface ProgramDaysViewProps {
  readonly program: WorkoutProgramDetail;
}

function ProgramDaysView({ program }: ProgramDaysViewProps) {
  if (program.days.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic">
        No training days configured yet. Edit to add some.
      </p>
    );
  }
  return (
    <div className="space-y-3">
      {program.days.map((day) => (
        <div
          key={day.id ?? day.day_order}
          className="rounded-lg border bg-background"
        >
          <div className="px-4 py-3 border-b flex items-baseline justify-between gap-3 flex-wrap">
            <div>
              <h3 className="font-semibold text-sm">{day.name}</h3>
              {day.focus && (
                <p className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
                  <Target className="h-3 w-3" />
                  {day.focus}
                </p>
              )}
            </div>
            <span className="text-xs text-muted-foreground">
              {day.exercises.length} exercise
              {day.exercises.length === 1 ? "" : "s"}
            </span>
          </div>
          {day.notes && (
            <div className="px-4 py-2 text-xs text-muted-foreground border-b bg-muted/10 whitespace-pre-line">
              {day.notes}
            </div>
          )}
          {day.exercises.length === 0 ? (
            <p className="px-4 py-3 text-xs text-muted-foreground italic">
              No exercises in this day.
            </p>
          ) : (
            <ul className="divide-y">
              {day.exercises.map((ex, i) => (
                <ExerciseRowDisplay key={ex.id ?? i} exercise={ex} index={i} />
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}

interface ExerciseRowDisplayProps {
  readonly exercise: ProgramExerciseData;
  readonly index: number;
}

function ExerciseRowDisplay({ exercise, index }: ExerciseRowDisplayProps) {
  const reps = repsLabel(exercise);
  const rpe = rpeLabel(exercise);
  const setsX =
    exercise.target_sets != null ? `${String(exercise.target_sets)}×` : "";
  const prescription = [
    setsX && reps ? `${setsX}${reps}` : setsX || reps,
    exercise.target_weight_kg != null
      ? `${String(exercise.target_weight_kg)} kg`
      : "",
    rpe,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <li className="px-4 py-2.5">
      <div className="flex items-baseline justify-between gap-3 flex-wrap">
        <div className="flex items-baseline gap-2 min-w-0">
          <span className="text-xs font-mono text-muted-foreground">
            {index + 1}.
          </span>
          <span className="font-medium text-sm">{exercise.exercise_title}</span>
        </div>
        <span className="text-xs text-muted-foreground tabular-nums">
          {prescription}
        </span>
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-0.5 text-xs text-muted-foreground pl-5">
        {exercise.tempo && (
          <span className="flex items-center gap-1">
            <Gauge className="h-3 w-3" />
            tempo {exercise.tempo}
          </span>
        )}
        {exercise.rest_seconds != null && (
          <span>rest {String(exercise.rest_seconds)}s</span>
        )}
      </div>
      {exercise.notes && (
        <p className="text-xs text-foreground/80 mt-1 pl-5 italic">
          {exercise.notes}
        </p>
      )}
    </li>
  );
}

interface HistorySectionProps {
  readonly history: WorkoutProgramSummary[];
  readonly onEdit: (program: WorkoutProgramDetail) => void;
}

function HistorySection({ history, onEdit }: HistorySectionProps) {
  if (history.length === 0) {
    return null;
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>History</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 px-3">
        {history.map((p) => (
          <HistoryRow key={p.id} program={p} onEdit={onEdit} />
        ))}
      </CardContent>
    </Card>
  );
}

interface HistoryRowProps {
  readonly program: WorkoutProgramSummary;
  readonly onEdit: (program: WorkoutProgramDetail) => void;
}

function HistoryRow({ program, onEdit }: HistoryRowProps) {
  const [expanded, setExpanded] = useState(false);
  const detailQuery = useWorkoutProgram(expanded ? program.id : null);
  const activateMutation = useActivateWorkoutProgram();
  const deleteMutation = useDeleteWorkoutProgram();
  const queryClient = useQueryClient();

  const handleActivate = async () => {
    if (
      // eslint-disable-next-line no-alert
      !confirm(
        "Re-activate this program? The current active program (if any) will be archived.",
      )
    ) {
      return;
    }
    try {
      await activateMutation.mutateAsync(program.id);
      toast.success("Program activated");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to activate");
    }
  };

  const handleDelete = async () => {
    if (
      // eslint-disable-next-line no-alert
      !confirm(`Delete "${program.name}"? This cannot be undone.`)
    ) {
      return;
    }
    try {
      await deleteMutation.mutateAsync(program.id);
      toast.success("Program deleted");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete");
    }
  };

  const handleEditClick = async () => {
    if (detailQuery.data) {
      onEdit(detailQuery.data);
      return;
    }
    try {
      const detail = await queryClient.fetchQuery({
        queryKey: programKeys.detail(program.id),
        queryFn: () => api.programs.get(program.id),
      });
      onEdit(detail);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to load program",
      );
    }
  };

  return (
    <div className="rounded-lg border bg-background">
      <div className="px-3 py-2.5 flex items-center gap-2 flex-wrap">
        <button
          type="button"
          onClick={() => {
            setExpanded((v) => !v);
          }}
          className="flex items-center gap-1.5 flex-1 min-w-0 text-left hover:text-primary transition-colors"
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
          )}
          <div className="min-w-0">
            <div className="flex items-baseline gap-2 flex-wrap">
              <span className="font-medium text-sm">{program.name}</span>
              {program.goal && (
                <span className="text-xs text-muted-foreground">
                  {program.goal}
                </span>
              )}
            </div>
            <div className="text-xs text-muted-foreground">
              {formatDate(program.start_date)} → {formatDate(program.end_date)}{" "}
              · {durationLabel(program.start_date, program.end_date)} ·{" "}
              {program.day_count} days · {program.exercise_count} exercises
            </div>
          </div>
        </button>
        <div className="flex gap-1 shrink-0">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleActivate}
            disabled={activateMutation.isPending}
            title="Re-activate"
          >
            <Play className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleEditClick}
            title="Edit"
          >
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
            className="text-destructive hover:text-destructive"
            title="Delete"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
      {expanded && (
        <div className={cn("border-t px-3 py-3")}>
          {detailQuery.isLoading && (
            <p className="text-xs text-muted-foreground">Loading...</p>
          )}
          {detailQuery.isError && (
            <p className="text-xs text-destructive">Failed to load detail.</p>
          )}
          {detailQuery.data && <ProgramDaysView program={detailQuery.data} />}
        </div>
      )}
    </div>
  );
}
