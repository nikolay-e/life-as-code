import {
  useMemo,
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react";
import { toast } from "sonner";
import {
  Plus,
  Trash2,
  ArrowUp,
  ArrowDown,
  Save,
  X,
  Search,
  RefreshCw,
  Library,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { LoadingState } from "../../../components/ui/loading-state";
import { cn } from "../../../lib/utils";
import {
  useCreateWorkoutProgram,
  useExerciseTemplates,
  useSyncExerciseTemplates,
  useUpdateWorkoutProgram,
} from "../../../hooks/useWorkoutPrograms";
import type {
  ExerciseTemplate,
  ProgramDayData,
  ProgramExerciseData,
  ProgramGoal,
  WorkoutProgramDetail,
} from "../../../types/api";

const GOALS: { value: ProgramGoal; label: string }[] = [
  { value: "hypertrophy", label: "Hypertrophy" },
  { value: "strength", label: "Strength" },
  { value: "peaking", label: "Peaking" },
  { value: "recomp", label: "Recomp" },
  { value: "conditioning", label: "Conditioning" },
  { value: "endurance", label: "Endurance" },
  { value: "general", label: "General" },
];

function newExercise(order: number): ProgramExerciseData {
  return {
    exercise_order: order,
    exercise_title: "",
    template_id: null,
    target_sets: 3,
    target_reps_min: 8,
    target_reps_max: 12,
    target_rpe_min: 7,
    target_rpe_max: 8,
    target_weight_kg: null,
    rest_seconds: 120,
    tempo: null,
    notes: null,
  };
}

function newDay(order: number, name?: string): ProgramDayData {
  return {
    day_order: order,
    name: name ?? `Day ${String(order + 1)}`,
    focus: null,
    notes: null,
    exercises: [],
  };
}

function todayIso(): string {
  const d = new Date();
  const y = String(d.getFullYear());
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

interface ProgramEditorProps {
  readonly program: WorkoutProgramDetail | null;
  readonly onSaved: (program: WorkoutProgramDetail) => void;
  readonly onCancel: () => void;
}

export function ProgramEditor({
  program,
  onSaved,
  onCancel,
}: ProgramEditorProps) {
  const isEdit = program !== null;
  const [name, setName] = useState(program?.name ?? "");
  const [description, setDescription] = useState(program?.description ?? "");
  const [goal, setGoal] = useState<ProgramGoal | "">(program?.goal ?? "");
  const [startDate, setStartDate] = useState(
    program?.start_date ?? todayIso(),
  );
  const [activate, setActivate] = useState(program ? program.is_active : true);
  const [days, setDays] = useState<ProgramDayData[]>(
    program?.days.length ? program.days : [newDay(0, "Day 1")],
  );
  const [activeDayIdx, setActiveDayIdx] = useState(0);
  const [pickerForExercise, setPickerForExercise] = useState<{
    dayIdx: number;
    exIdx: number;
  } | null>(null);

  const createMutation = useCreateWorkoutProgram();
  const updateMutation = useUpdateWorkoutProgram();
  const isSaving = createMutation.isPending || updateMutation.isPending;

  // Derive a safe index instead of syncing via setState in an effect.
  const safeDayIdx = Math.min(activeDayIdx, Math.max(0, days.length - 1));

  const handleAddDay = () => {
    setDays((prev) => [...prev, newDay(prev.length)]);
    setActiveDayIdx(days.length);
  };

  const handleRemoveDay = (idx: number) => {
    if (days.length === 1) {
      toast.error("Program must have at least one day");
      return;
    }
    setDays((prev) =>
      prev
        .filter((_, i) => i !== idx)
        .map((d, i) => ({ ...d, day_order: i })),
    );
  };

  const handleDayChange = (idx: number, patch: Partial<ProgramDayData>) => {
    setDays((prev) =>
      prev.map((d, i) => (i === idx ? { ...d, ...patch } : d)),
    );
  };

  const handleAddExercise = (dayIdx: number) => {
    setDays((prev) =>
      prev.map((d, i) =>
        i === dayIdx
          ? {
              ...d,
              exercises: [...d.exercises, newExercise(d.exercises.length)],
            }
          : d,
      ),
    );
  };

  const handleExerciseChange = (
    dayIdx: number,
    exIdx: number,
    patch: Partial<ProgramExerciseData>,
  ) => {
    setDays((prev) =>
      prev.map((d, i) =>
        i === dayIdx
          ? {
              ...d,
              exercises: d.exercises.map((ex, j) =>
                j === exIdx ? { ...ex, ...patch } : ex,
              ),
            }
          : d,
      ),
    );
  };

  const handleRemoveExercise = (dayIdx: number, exIdx: number) => {
    setDays((prev) =>
      prev.map((d, i) =>
        i === dayIdx
          ? {
              ...d,
              exercises: d.exercises
                .filter((_, j) => j !== exIdx)
                .map((ex, j) => ({ ...ex, exercise_order: j })),
            }
          : d,
      ),
    );
  };

  const handleMoveExercise = (
    dayIdx: number,
    exIdx: number,
    dir: -1 | 1,
  ) => {
    setDays((prev) =>
      prev.map((d, i) => {
        if (i !== dayIdx) return d;
        const target = exIdx + dir;
        if (target < 0 || target >= d.exercises.length) return d;
        const next = [...d.exercises];
        [next[exIdx], next[target]] = [next[target], next[exIdx]];
        return {
          ...d,
          exercises: next.map((ex, j) => ({ ...ex, exercise_order: j })),
        };
      }),
    );
  };

  const handlePickTemplate = (template: ExerciseTemplate) => {
    if (!pickerForExercise) return;
    const { dayIdx, exIdx } = pickerForExercise;
    handleExerciseChange(dayIdx, exIdx, {
      template_id: template.id,
      exercise_title: template.title,
    });
    setPickerForExercise(null);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      toast.error("Program name is required");
      return;
    }
    // Drop exercises with empty title to keep payload tidy.
    const cleaned = days.map((d) => ({
      ...d,
      exercises: d.exercises
        .filter((ex) => ex.exercise_title.trim() !== "")
        .map((ex, j) => ({ ...ex, exercise_order: j })),
    }));
    const payload = {
      name: name.trim(),
      description: description.trim() || null,
      goal: goal === "" ? null : goal,
      start_date: startDate,
      days: cleaned,
    };
    try {
      if (program) {
        const updated = await updateMutation.mutateAsync({
          id: program.id,
          data: payload,
        });
        toast.success("Program updated");
        onSaved(updated);
      } else {
        const created = await createMutation.mutateAsync({
          ...payload,
          activate,
        });
        toast.success(activate ? "Program created and activated" : "Program saved");
        onSaved(created);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save program");
    }
  };

  const activeDay = days[safeDayIdx];

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between gap-2">
            <span>{isEdit ? "Edit Program" : "New Program"}</span>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={onCancel}
                disabled={isSaving}
              >
                <X className="h-4 w-4 mr-1" />
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={isSaving}>
                <Save className="h-4 w-4 mr-1" />
                {isSaving ? "Saving..." : "Save"}
              </Button>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="prog-name">Name</Label>
              <Input
                id="prog-name"
                value={name}
                onChange={(e) => { setName(e.target.value); }}
                placeholder="e.g. 12-Week Hypertrophy Block"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="prog-goal">Goal</Label>
              <select
                id="prog-goal"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={goal}
                onChange={(e) => { setGoal(e.target.value as ProgramGoal | ""); }}
              >
                <option value="">—</option>
                {GOALS.map((g) => (
                  <option key={g.value} value={g.value}>
                    {g.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="prog-start">Start date</Label>
              <Input
                id="prog-start"
                type="date"
                value={startDate}
                onChange={(e) => { setStartDate(e.target.value); }}
                required
              />
            </div>
            {!isEdit && (
              <div className="space-y-2">
                <Label className="block">Status</Label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={activate}
                    onChange={(e) => { setActivate(e.target.checked); }}
                  />
                  Make this the active program (auto-archives any current one)
                </label>
              </div>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="prog-desc">Description / accents</Label>
            <textarea
              id="prog-desc"
              className="flex min-h-20 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={description}
              onChange={(e) => { setDescription(e.target.value); }}
              placeholder="Block focus, deload schedule, cues to keep front-of-mind..."
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between gap-2">
            <span>Training days</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleAddDay}
            >
              <Plus className="h-4 w-4 mr-1" />
              Add day
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2 border-b pb-2">
            {days.map((d, i) => (
              <button
                key={i}
                type="button"
                onClick={() => { setActiveDayIdx(i); }}
                className={cn(
                  "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                  i === safeDayIdx
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80",
                )}
              >
                {d.name || `Day ${String(i + 1)}`}
                <span className="ml-2 text-xs opacity-70">
                  ({d.exercises.length})
                </span>
              </button>
            ))}
          </div>
          <DayEditor
            day={activeDay}
            onDayChange={(patch) => { handleDayChange(safeDayIdx, patch); }}
            onRemoveDay={() => { handleRemoveDay(safeDayIdx); }}
            onAddExercise={() => { handleAddExercise(safeDayIdx); }}
            onChangeExercise={(exIdx, patch) => {
              handleExerciseChange(safeDayIdx, exIdx, patch);
            }}
            onMoveExercise={(exIdx, dir) => {
              handleMoveExercise(safeDayIdx, exIdx, dir);
            }}
            onRemoveExercise={(exIdx) => {
              handleRemoveExercise(safeDayIdx, exIdx);
            }}
            onPickTemplate={(exIdx) => {
              setPickerForExercise({ dayIdx: safeDayIdx, exIdx });
            }}
          />
        </CardContent>
      </Card>

      {pickerForExercise && (
        <ExerciseTemplatePicker
          onSelect={handlePickTemplate}
          onClose={() => { setPickerForExercise(null); }}
        />
      )}
    </form>
  );
}

interface DayEditorProps {
  readonly day: ProgramDayData;
  readonly onDayChange: (patch: Partial<ProgramDayData>) => void;
  readonly onRemoveDay: () => void;
  readonly onAddExercise: () => void;
  readonly onChangeExercise: (
    exIdx: number,
    patch: Partial<ProgramExerciseData>,
  ) => void;
  readonly onMoveExercise: (exIdx: number, dir: -1 | 1) => void;
  readonly onRemoveExercise: (exIdx: number) => void;
  readonly onPickTemplate: (exIdx: number) => void;
}

function DayEditor({
  day,
  onDayChange,
  onRemoveDay,
  onAddExercise,
  onChangeExercise,
  onMoveExercise,
  onRemoveExercise,
  onPickTemplate,
}: DayEditorProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor={`day-name-${String(day.day_order)}`}>Day name</Label>
          <Input
            id={`day-name-${String(day.day_order)}`}
            value={day.name}
            onChange={(e) => { onDayChange({ name: e.target.value }); }}
            placeholder="Push, Pull, Legs, Day A..."
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor={`day-focus-${String(day.day_order)}`}>
            Focus / accent
          </Label>
          <Input
            id={`day-focus-${String(day.day_order)}`}
            value={day.focus ?? ""}
            onChange={(e) => { onDayChange({ focus: e.target.value || null }); }}
            placeholder="Heavy push, posterior chain hypertrophy..."
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor={`day-notes-${String(day.day_order)}`}>Day notes</Label>
        <textarea
          id={`day-notes-${String(day.day_order)}`}
          className="flex min-h-16 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          value={day.notes ?? ""}
          onChange={(e) => { onDayChange({ notes: e.target.value || null }); }}
          placeholder="Warm-up, conditioning finisher..."
        />
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Exercises</h3>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onRemoveDay}
              className="text-destructive hover:text-destructive"
            >
              <Trash2 className="h-4 w-4 mr-1" />
              Remove day
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onAddExercise}
            >
              <Plus className="h-4 w-4 mr-1" />
              Add exercise
            </Button>
          </div>
        </div>
        {day.exercises.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No exercises yet. Add one to start prescribing sets.
          </p>
        ) : (
          <div className="space-y-3">
            {day.exercises.map((ex, exIdx) => (
              <ExerciseRow
                key={exIdx}
                exercise={ex}
                index={exIdx}
                isFirst={exIdx === 0}
                isLast={exIdx === day.exercises.length - 1}
                onChange={(patch) => { onChangeExercise(exIdx, patch); }}
                onMove={(dir) => { onMoveExercise(exIdx, dir); }}
                onRemove={() => { onRemoveExercise(exIdx); }}
                onPickTemplate={() => { onPickTemplate(exIdx); }}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface ExerciseRowProps {
  readonly exercise: ProgramExerciseData;
  readonly index: number;
  readonly isFirst: boolean;
  readonly isLast: boolean;
  readonly onChange: (patch: Partial<ProgramExerciseData>) => void;
  readonly onMove: (dir: -1 | 1) => void;
  readonly onRemove: () => void;
  readonly onPickTemplate: () => void;
}

function ExerciseRow({
  exercise,
  index,
  isFirst,
  isLast,
  onChange,
  onMove,
  onRemove,
  onPickTemplate,
}: ExerciseRowProps) {
  const numField =
    (setter: (v: number | null) => void) =>
    (e: ChangeEvent<HTMLInputElement>) => {
      const raw = e.target.value;
      if (raw === "") {
        setter(null);
        return;
      }
      const n = Number(raw);
      if (!Number.isFinite(n)) return;
      setter(n);
    };

  return (
    <div className="rounded-lg border bg-muted/20 p-4 space-y-3">
      <div className="flex items-start gap-2">
        <span className="text-sm font-mono text-muted-foreground pt-2">
          {index + 1}.
        </span>
        <div className="flex-1 space-y-2">
          <div className="flex gap-2">
            <Input
              value={exercise.exercise_title}
              onChange={(e) => { onChange({ exercise_title: e.target.value }); }}
              placeholder="Exercise name (e.g. Barbell Back Squat)"
              className="flex-1"
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onPickTemplate}
              title="Pick from Hevy catalog"
            >
              <Library className="h-4 w-4" />
            </Button>
          </div>
          {exercise.template_id !== null && (
            <p className="text-xs text-muted-foreground">
              Linked to Hevy template (logged sets will auto-match)
            </p>
          )}
        </div>
        <div className="flex flex-col gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            disabled={isFirst}
            onClick={() => { onMove(-1); }}
          >
            <ArrowUp className="h-3.5 w-3.5" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            disabled={isLast}
            onClick={() => { onMove(1); }}
          >
            <ArrowDown className="h-3.5 w-3.5" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-destructive"
            onClick={onRemove}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-2">
        <NumField
          label="Sets"
          value={exercise.target_sets}
          onChange={numField((v) => {
            onChange({ target_sets: v });
          })}
          step="1"
        />
        <NumField
          label="Reps min"
          value={exercise.target_reps_min}
          onChange={numField((v) => {
            onChange({ target_reps_min: v });
          })}
          step="1"
        />
        <NumField
          label="Reps max"
          value={exercise.target_reps_max}
          onChange={numField((v) => {
            onChange({ target_reps_max: v });
          })}
          step="1"
        />
        <NumField
          label="RPE min"
          value={exercise.target_rpe_min}
          onChange={numField((v) => {
            onChange({ target_rpe_min: v });
          })}
          step="0.5"
        />
        <NumField
          label="RPE max"
          value={exercise.target_rpe_max}
          onChange={numField((v) => {
            onChange({ target_rpe_max: v });
          })}
          step="0.5"
        />
        <NumField
          label="Weight (kg)"
          value={exercise.target_weight_kg}
          onChange={numField((v) => {
            onChange({ target_weight_kg: v });
          })}
          step="0.5"
        />
        <NumField
          label="Rest (s)"
          value={exercise.rest_seconds}
          onChange={numField((v) => {
            onChange({ rest_seconds: v });
          })}
          step="15"
        />
        <div className="space-y-1">
          <Label className="text-xs">Tempo</Label>
          <Input
            value={exercise.tempo ?? ""}
            onChange={(e) => { onChange({ tempo: e.target.value || null }); }}
            placeholder="3-1-1-0"
            className="h-8 text-sm"
          />
        </div>
      </div>

      <div className="space-y-1">
        <Label className="text-xs">Accents / cues</Label>
        <textarea
          className="flex min-h-12 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          value={exercise.notes ?? ""}
          onChange={(e) => { onChange({ notes: e.target.value || null }); }}
          placeholder="Pause at bottom, drive through heels, control eccentric..."
        />
      </div>
    </div>
  );
}

interface NumFieldProps {
  readonly label: string;
  readonly value: number | null;
  readonly onChange: (e: ChangeEvent<HTMLInputElement>) => void;
  readonly step?: string;
}

function NumField({ label, value, onChange, step }: NumFieldProps) {
  return (
    <div className="space-y-1">
      <Label className="text-xs">{label}</Label>
      <Input
        type="number"
        value={value ?? ""}
        onChange={onChange}
        step={step}
        min="0"
        className="h-8 text-sm"
      />
    </div>
  );
}

interface ExerciseTemplatePickerProps {
  readonly onSelect: (template: ExerciseTemplate) => void;
  readonly onClose: () => void;
}

function ExerciseTemplatePicker({
  onSelect,
  onClose,
}: ExerciseTemplatePickerProps) {
  const [q, setQ] = useState("");
  const [muscle, setMuscle] = useState("");
  const [equipment, setEquipment] = useState("");
  const { data, isLoading, isError } = useExerciseTemplates(q, muscle, equipment);
  const syncMutation = useSyncExerciseTemplates();

  const handleSync = async () => {
    try {
      const res = await syncMutation.mutateAsync();
      toast.success(
        `Synced ${String(res.fetched)} exercises (${String(res.created)} new)`,
      );
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to sync exercises",
      );
    }
  };

  const isEmpty = !isLoading && !isError && (data?.length ?? 0) === 0;
  const showSyncHint = isEmpty && !q && !muscle && !equipment;

  const muscles = useMemo(() => {
    const set = new Set<string>();
    (data ?? []).forEach((t) => {
      if (t.primary_muscle_group) set.add(t.primary_muscle_group);
    });
    return Array.from(set).sort();
  }, [data]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <Card className="w-full max-w-2xl max-h-[80vh] flex flex-col">
        <CardHeader className="border-b">
          <CardTitle className="flex items-center justify-between gap-2">
            <span>Pick exercise from Hevy catalog</span>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleSync}
                disabled={syncMutation.isPending}
              >
                <RefreshCw
                  className={cn(
                    "h-4 w-4 mr-1",
                    syncMutation.isPending && "animate-spin",
                  )}
                />
                Sync from Hevy
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={onClose}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent className="flex-1 overflow-hidden flex flex-col gap-3 pt-4">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                value={q}
                onChange={(e) => { setQ(e.target.value); }}
                placeholder="Search by name..."
                className="pl-8"
              />
            </div>
            <select
              value={muscle}
              onChange={(e) => { setMuscle(e.target.value); }}
              className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">All muscles</option>
              {muscles.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
            <Input
              value={equipment}
              onChange={(e) => { setEquipment(e.target.value); }}
              placeholder="Equipment"
              className="w-32"
            />
          </div>

          <div className="flex-1 overflow-y-auto -mx-1 px-1">
            {isLoading && <LoadingState message="Loading exercises..." />}
            {isError && (
              <p className="text-sm text-destructive">
                Failed to load exercises.
              </p>
            )}
            {showSyncHint && (
              <div className="text-center py-8 space-y-2">
                <p className="text-sm text-muted-foreground">
                  No exercises cached yet.
                </p>
                <p className="text-xs text-muted-foreground">
                  Click &ldquo;Sync from Hevy&rdquo; to load your exercise library.
                </p>
              </div>
            )}
            {isEmpty && !showSyncHint && (
              <p className="text-sm text-muted-foreground text-center py-8">
                No matches.
              </p>
            )}
            <ul className="divide-y">
              {(data ?? []).map((tpl) => (
                <li key={tpl.id}>
                  <button
                    type="button"
                    onClick={() => { onSelect(tpl); }}
                    className="w-full text-left px-2 py-2.5 hover:bg-muted/50 rounded-md transition-colors"
                  >
                    <div className="font-medium text-sm">{tpl.title}</div>
                    <div className="text-xs text-muted-foreground flex flex-wrap gap-x-3 gap-y-0.5 mt-0.5">
                      {tpl.primary_muscle_group && (
                        <span>{tpl.primary_muscle_group}</span>
                      )}
                      {tpl.equipment && <span>{tpl.equipment}</span>}
                      {tpl.is_custom && (
                        <span className="text-primary">custom</span>
                      )}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
