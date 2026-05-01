import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import {
  Pill,
  FlaskConical,
  Dumbbell,
  Trophy,
  Plus,
  Square,
  Trash2,
  Pencil,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import {
  useInterventions,
  useCreateIntervention,
  useUpdateIntervention,
  useDeleteIntervention,
  useBiomarkers,
  useCreateBiomarker,
  useDeleteBiomarker,
} from "../../hooks/useHealthLog";
import {
  useFunctionalTests,
  useCreateFunctionalTest,
  useDeleteFunctionalTest,
} from "../../hooks/useFunctionalTests";
import {
  useLongevityGoals,
  useCreateLongevityGoal,
  useUpdateLongevityGoal,
  useDeleteLongevityGoal,
} from "../../hooks/useLongevityGoals";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { DateInputPicker } from "../../components/ui/date-range-picker";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../../components/ui/card";
import { LoadingState } from "../../components/ui/loading-state";
import { ErrorCard } from "../../components/ui/error-card";
import { cn } from "../../lib/utils";
import { getLocalDateString, getLocalToday } from "../../lib/health";
import type {
  InterventionData,
  BloodBiomarkerData,
  FunctionalTestData,
  LongevityGoalData,
} from "../../types/api";

type Tab = "medications" | "labs" | "tests" | "goals";
type Category = InterventionData["category"];

const CATEGORIES: { value: Category; label: string }[] = [
  { value: "medication", label: "Medication" },
  { value: "supplement", label: "Supplement" },
  { value: "protocol", label: "Protocol" },
  { value: "lifestyle", label: "Lifestyle" },
  { value: "diet", label: "Diet" },
];

const BIOMARKER_PRESETS: { name: string; unit: string }[] = [
  { name: "TSH", unit: "mIU/L" },
  { name: "Vitamin D", unit: "ng/mL" },
  { name: "HbA1c", unit: "%" },
  { name: "Total Testosterone", unit: "ng/dL" },
  { name: "Free Testosterone", unit: "pg/mL" },
  { name: "Ferritin", unit: "ng/mL" },
  { name: "hsCRP", unit: "mg/L" },
  { name: "Fasting Glucose", unit: "mg/dL" },
  { name: "Insulin", unit: "uIU/mL" },
  { name: "ApoB", unit: "mg/dL" },
  { name: "Lp(a)", unit: "nmol/L" },
  { name: "Homocysteine", unit: "umol/L" },
  { name: "Total Cholesterol", unit: "mg/dL" },
  { name: "LDL", unit: "mg/dL" },
  { name: "HDL", unit: "mg/dL" },
  { name: "Triglycerides", unit: "mg/dL" },
  { name: "ALT", unit: "U/L" },
  { name: "AST", unit: "U/L" },
  { name: "Creatinine", unit: "mg/dL" },
  { name: "eGFR", unit: "mL/min" },
  { name: "Vitamin B12", unit: "pg/mL" },
  { name: "Folate", unit: "ng/mL" },
  { name: "DHEA-S", unit: "ug/dL" },
  { name: "IGF-1", unit: "ng/mL" },
  { name: "Cortisol", unit: "ug/dL" },
];

const TEST_PRESETS: { name: string; unit: string }[] = [
  { name: "VO2max (lab)", unit: "ml/kg/min" },
  { name: "1RM Squat", unit: "kg" },
  { name: "1RM Bench Press", unit: "kg" },
  { name: "1RM Deadlift", unit: "kg" },
  { name: "Plank Hold", unit: "seconds" },
  { name: "Max Pullups", unit: "reps" },
  { name: "Max Pushups", unit: "reps" },
  { name: "Grip Strength", unit: "kg" },
  { name: "Wall Sit", unit: "seconds" },
  { name: "Vertical Jump", unit: "cm" },
  { name: "Sit & Reach", unit: "cm" },
  { name: "Resting HR (manual)", unit: "bpm" },
  { name: "Cooper Test 12min", unit: "meters" },
];

const todayStr = () => getLocalDateString(getLocalToday());

function InterventionForm({
  onClose,
}: Readonly<{
  onClose: () => void;
}>) {
  const create = useCreateIntervention();
  const [name, setName] = useState("");
  const [category, setCategory] = useState<Category>("supplement");
  const [dosage, setDosage] = useState("");
  const [frequency, setFrequency] = useState("");
  const [startDate, setStartDate] = useState(todayStr());
  const [notes, setNotes] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    create.mutate(
      {
        name: name.trim(),
        category,
        dosage: dosage.trim() || undefined,
        frequency: frequency.trim() || undefined,
        start_date: startDate,
        notes: notes.trim() || undefined,
      },
      {
        onSuccess: () => {
          toast.success("Medication added");
          onClose();
        },
        onError: (err) =>
          toast.error(err instanceof Error ? err.message : "Failed to add"),
      },
    );
  };

  return (
    <Card className="border-dashed">
      <CardContent className="pt-4">
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label htmlFor="med-name">Name *</Label>
              <Input
                id="med-name"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                }}
                placeholder="e.g. Metformin"
                required
              />
            </div>
            <div>
              <Label htmlFor="med-category">Category</Label>
              <select
                id="med-category"
                value={category}
                onChange={(e) => {
                  setCategory(e.target.value as Category);
                }}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="med-dosage">Dosage</Label>
              <Input
                id="med-dosage"
                value={dosage}
                onChange={(e) => {
                  setDosage(e.target.value);
                }}
                placeholder="e.g. 500mg"
              />
            </div>
            <div>
              <Label htmlFor="med-frequency">Frequency</Label>
              <Input
                id="med-frequency"
                value={frequency}
                onChange={(e) => {
                  setFrequency(e.target.value);
                }}
                placeholder="e.g. 2x daily"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="med-start">Start Date</Label>
              <DateInputPicker
                value={startDate}
                onChange={setStartDate}
                className="w-full justify-start"
              />
            </div>
            <div>
              <Label htmlFor="med-notes">Notes</Label>
              <Input
                id="med-notes"
                value={notes}
                onChange={(e) => {
                  setNotes(e.target.value);
                }}
                placeholder="Optional notes"
              />
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <Button type="button" variant="ghost" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={create.isPending}>
              {create.isPending ? "Saving..." : "Save"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function InterventionCard({
  item,
}: Readonly<{
  item: InterventionData;
}>) {
  const update = useUpdateIntervention();
  const remove = useDeleteIntervention();

  const handleStop = () => {
    update.mutate(
      { id: item.id, data: { active: false, end_date: todayStr() } },
      {
        onSuccess: () => toast.success(`Stopped ${item.name}`),
        onError: (err) =>
          toast.error(err instanceof Error ? err.message : "Failed"),
      },
    );
  };

  const handleDelete = () => {
    remove.mutate(item.id, {
      onSuccess: () => toast.success(`Deleted ${item.name}`),
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "Failed"),
    });
  };

  const isActive = item.active;

  return (
    <div
      className={cn(
        "flex items-center justify-between p-3 rounded-lg border",
        isActive ? "bg-background" : "bg-muted/30 opacity-70",
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm truncate">{item.name}</span>
          <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
            {item.category}
          </span>
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-0.5 text-xs text-muted-foreground">
          {item.dosage && <span>{item.dosage}</span>}
          {item.frequency && <span>{item.frequency}</span>}
          <span>from {item.start_date}</span>
          {item.end_date && <span>to {item.end_date}</span>}
        </div>
        {item.notes && (
          <p className="text-xs text-muted-foreground mt-0.5 truncate">
            {item.notes}
          </p>
        )}
      </div>
      <div className="flex items-center gap-1 ml-2 shrink-0">
        {isActive && (
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={handleStop}
            disabled={update.isPending}
            aria-label="Stop medication"
          >
            <Square className="h-3.5 w-3.5" />
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 hover:text-destructive"
          onClick={handleDelete}
          disabled={remove.isPending}
          aria-label={`Delete ${item.name}`}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}

function MedicationsTab() {
  const { data: interventions, isLoading, error } = useInterventions();
  const [showForm, setShowForm] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  if (isLoading) return <LoadingState message="Loading medications..." />;
  if (error) return <ErrorCard message="Failed to load medications" />;

  const active = (interventions ?? []).filter((i) => i.active);
  const inactive = (interventions ?? []).filter((i) => !i.active);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Active</h2>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setShowForm(!showForm);
          }}
        >
          <Plus className="h-4 w-4 mr-1" />
          Add
        </Button>
      </div>

      {showForm && (
        <InterventionForm
          onClose={() => {
            setShowForm(false);
          }}
        />
      )}

      {active.length === 0 ? (
        <p className="text-sm text-muted-foreground py-4 text-center">
          No active medications or supplements
        </p>
      ) : (
        <div className="space-y-2">
          {active.map((item) => (
            <InterventionCard key={item.id} item={item} />
          ))}
        </div>
      )}

      {inactive.length > 0 && (
        <div>
          <button
            type="button"
            onClick={() => {
              setShowHistory(!showHistory);
            }}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            {showHistory ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
            History ({inactive.length})
          </button>
          {showHistory && (
            <div className="space-y-2 mt-2">
              {inactive.map((item) => (
                <InterventionCard key={item.id} item={item} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function BiomarkerForm({
  onClose,
}: Readonly<{
  onClose: () => void;
}>) {
  const create = useCreateBiomarker();
  const [date, setDate] = useState(todayStr());
  const [markerName, setMarkerName] = useState("");
  const [value, setValue] = useState("");
  const [unit, setUnit] = useState("");
  const [refLow, setRefLow] = useState("");
  const [refHigh, setRefHigh] = useState("");
  const [labName, setLabName] = useState("");
  const [notes, setNotes] = useState("");

  const handleMarkerChange = (newName: string) => {
    setMarkerName(newName);
    const preset = BIOMARKER_PRESETS.find((p) => p.name === newName);
    if (preset && !unit) {
      setUnit(preset.unit);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!markerName.trim() || !value) return;
    create.mutate(
      {
        date,
        marker_name: markerName.trim(),
        value: Number.parseFloat(value),
        unit: unit.trim() || "units",
        reference_range_low: refLow ? Number.parseFloat(refLow) : undefined,
        reference_range_high: refHigh ? Number.parseFloat(refHigh) : undefined,
        lab_name: labName.trim() || undefined,
        notes: notes.trim() || undefined,
      },
      {
        onSuccess: () => {
          toast.success("Lab result added");
          setMarkerName("");
          setValue("");
          setUnit("");
          setRefLow("");
          setRefHigh("");
          setNotes("");
        },
        onError: (err) =>
          toast.error(err instanceof Error ? err.message : "Failed to add"),
      },
    );
  };

  return (
    <Card className="border-dashed">
      <CardContent className="pt-4">
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="bio-date">Date *</Label>
              <DateInputPicker
                value={date}
                onChange={setDate}
                className="w-full justify-start"
              />
            </div>
            <div>
              <Label htmlFor="bio-marker">Marker *</Label>
              <Input
                id="bio-marker"
                list="biomarker-presets"
                value={markerName}
                onChange={(e) => {
                  handleMarkerChange(e.target.value);
                }}
                placeholder="e.g. TSH"
                required
              />
              <datalist id="biomarker-presets">
                {BIOMARKER_PRESETS.map((p) => (
                  <option key={p.name} value={p.name} />
                ))}
              </datalist>
            </div>
            <div>
              <Label htmlFor="bio-value">Value *</Label>
              <Input
                id="bio-value"
                type="number"
                step="any"
                value={value}
                onChange={(e) => {
                  setValue(e.target.value);
                }}
                placeholder="e.g. 2.5"
                required
              />
            </div>
            <div>
              <Label htmlFor="bio-unit">Unit</Label>
              <Input
                id="bio-unit"
                list="unit-presets"
                value={unit}
                onChange={(e) => {
                  setUnit(e.target.value);
                }}
                placeholder="e.g. mIU/L"
              />
              <datalist id="unit-presets">
                {[...new Set(BIOMARKER_PRESETS.map((p) => p.unit))].map((u) => (
                  <option key={u} value={u} />
                ))}
              </datalist>
            </div>
            <div>
              <Label htmlFor="bio-ref-low">Ref. Low</Label>
              <Input
                id="bio-ref-low"
                type="number"
                step="any"
                value={refLow}
                onChange={(e) => {
                  setRefLow(e.target.value);
                }}
                placeholder="Optional"
              />
            </div>
            <div>
              <Label htmlFor="bio-ref-high">Ref. High</Label>
              <Input
                id="bio-ref-high"
                type="number"
                step="any"
                value={refHigh}
                onChange={(e) => {
                  setRefHigh(e.target.value);
                }}
                placeholder="Optional"
              />
            </div>
            <div>
              <Label htmlFor="bio-lab">Lab Name</Label>
              <Input
                id="bio-lab"
                value={labName}
                onChange={(e) => {
                  setLabName(e.target.value);
                }}
                placeholder="Optional"
              />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="bio-notes">Notes</Label>
              <Input
                id="bio-notes"
                value={notes}
                onChange={(e) => {
                  setNotes(e.target.value);
                }}
                placeholder="Optional notes"
              />
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <Button type="button" variant="ghost" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={create.isPending}>
              {create.isPending ? "Saving..." : "Save"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function isOutOfRange(item: BloodBiomarkerData): boolean {
  if (
    item.reference_range_low != null &&
    item.value < item.reference_range_low
  ) {
    return true;
  }
  if (
    item.reference_range_high != null &&
    item.value > item.reference_range_high
  ) {
    return true;
  }
  return false;
}

function formatRange(low: number | null, high: number | null): string | null {
  if (low != null && high != null) return `${String(low)} – ${String(high)}`;
  if (low != null) return `>= ${String(low)}`;
  if (high != null) return `<= ${String(high)}`;
  return null;
}

function LabResultsTab() {
  const { data: biomarkers, isLoading, error } = useBiomarkers();
  const remove = useDeleteBiomarker();
  const [showForm, setShowForm] = useState(false);

  if (isLoading) return <LoadingState message="Loading lab results..." />;
  if (error) return <ErrorCard message="Failed to load lab results" />;

  const items = biomarkers ?? [];

  const grouped = new Map<string, BloodBiomarkerData[]>();
  for (const item of items) {
    const existing = grouped.get(item.date);
    if (existing) {
      existing.push(item);
    } else {
      grouped.set(item.date, [item]);
    }
  }

  const handleDelete = (id: number, name: string) => {
    remove.mutate(id, {
      onSuccess: () => toast.success(`Deleted ${name}`),
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "Failed"),
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Lab Results</h2>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setShowForm(!showForm);
          }}
        >
          <Plus className="h-4 w-4 mr-1" />
          Add
        </Button>
      </div>

      {showForm && (
        <BiomarkerForm
          onClose={() => {
            setShowForm(false);
          }}
        />
      )}

      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground py-4 text-center">
          No lab results recorded
        </p>
      ) : (
        <div className="space-y-4">
          {[...grouped.entries()].map(([date, dateItems]) => (
            <Card key={date}>
              <CardHeader className="py-3 px-4">
                <CardTitle className="text-sm font-medium">{date}</CardTitle>
              </CardHeader>
              <CardContent className="px-4 pb-3 pt-0">
                <div className="divide-y">
                  {dateItems.map((item) => {
                    const outOfRange = isOutOfRange(item);
                    const range = formatRange(
                      item.reference_range_low,
                      item.reference_range_high,
                    );
                    return (
                      <div
                        key={item.id}
                        className="flex items-center justify-between py-2 first:pt-0 last:pb-0"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-baseline gap-2">
                            <span className="text-sm font-medium">
                              {item.marker_name}
                            </span>
                            <span
                              className={cn(
                                "text-sm font-mono",
                                outOfRange
                                  ? "text-red-700 dark:text-red-400 font-semibold"
                                  : "text-foreground",
                              )}
                            >
                              {item.value} {item.unit}
                            </span>
                            {range && (
                              <span className="text-xs text-muted-foreground">
                                ref: {range}
                              </span>
                            )}
                          </div>
                          {(item.lab_name ?? item.notes) && (
                            <p className="text-xs text-muted-foreground truncate">
                              {[item.lab_name, item.notes]
                                .filter(Boolean)
                                .join(" — ")}
                            </p>
                          )}
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 hover:text-destructive shrink-0"
                          onClick={() => {
                            handleDelete(item.id, item.marker_name);
                          }}
                          disabled={remove.isPending}
                          aria-label={`Delete ${item.marker_name}`}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function FunctionalTestForm({
  onClose,
}: Readonly<{
  onClose: () => void;
}>) {
  const create = useCreateFunctionalTest();
  const [date, setDate] = useState(todayStr());
  const [testName, setTestName] = useState("");
  const [value, setValue] = useState("");
  const [unit, setUnit] = useState("");
  const [notes, setNotes] = useState("");

  const handleTestNameChange = (newName: string) => {
    setTestName(newName);
    const preset = TEST_PRESETS.find((p) => p.name === newName);
    if (preset && !unit) {
      setUnit(preset.unit);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!testName.trim() || !value) return;
    create.mutate(
      {
        date,
        test_name: testName.trim(),
        value: Number.parseFloat(value),
        unit: unit.trim() || "units",
        notes: notes.trim() || undefined,
      },
      {
        onSuccess: () => {
          toast.success("Test result added");
          setTestName("");
          setValue("");
          setUnit("");
          setNotes("");
        },
        onError: (err) =>
          toast.error(err instanceof Error ? err.message : "Failed to add"),
      },
    );
  };

  return (
    <Card className="border-dashed">
      <CardContent className="pt-4">
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="test-date">Date *</Label>
              <DateInputPicker
                value={date}
                onChange={setDate}
                className="w-full justify-start"
              />
            </div>
            <div>
              <Label htmlFor="test-name">Test *</Label>
              <Input
                id="test-name"
                list="test-presets"
                value={testName}
                onChange={(e) => {
                  handleTestNameChange(e.target.value);
                }}
                placeholder="e.g. 1RM Squat"
                required
              />
              <datalist id="test-presets">
                {TEST_PRESETS.map((p) => (
                  <option key={p.name} value={p.name} />
                ))}
              </datalist>
            </div>
            <div>
              <Label htmlFor="test-value">Value *</Label>
              <Input
                id="test-value"
                type="number"
                step="any"
                value={value}
                onChange={(e) => {
                  setValue(e.target.value);
                }}
                placeholder="e.g. 100"
                required
              />
            </div>
            <div>
              <Label htmlFor="test-unit">Unit</Label>
              <Input
                id="test-unit"
                list="test-unit-presets"
                value={unit}
                onChange={(e) => {
                  setUnit(e.target.value);
                }}
                placeholder="e.g. kg"
              />
              <datalist id="test-unit-presets">
                {[...new Set(TEST_PRESETS.map((p) => p.unit))].map((u) => (
                  <option key={u} value={u} />
                ))}
              </datalist>
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="test-notes">Notes</Label>
              <Input
                id="test-notes"
                value={notes}
                onChange={(e) => {
                  setNotes(e.target.value);
                }}
                placeholder="Optional notes"
              />
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <Button type="button" variant="ghost" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={create.isPending}>
              {create.isPending ? "Saving..." : "Save"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function FunctionalTestList({
  items,
}: Readonly<{
  items: FunctionalTestData[];
}>) {
  const remove = useDeleteFunctionalTest();

  const grouped = new Map<string, FunctionalTestData[]>();
  const sorted = [...items].sort((a, b) => b.date.localeCompare(a.date));
  for (const item of sorted) {
    const existing = grouped.get(item.date);
    if (existing) {
      existing.push(item);
    } else {
      grouped.set(item.date, [item]);
    }
  }

  const handleDelete = (id: number, name: string) => {
    remove.mutate(id, {
      onSuccess: () => toast.success(`Deleted ${name}`),
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "Failed"),
    });
  };

  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4 text-center">
        No functional test results recorded
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {[...grouped.entries()].map(([date, dateItems]) => (
        <Card key={date}>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-sm font-medium">{date}</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3 pt-0">
            <div className="divide-y">
              {dateItems.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between py-2 first:pt-0 last:pb-0"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline gap-2">
                      <span className="text-sm font-medium">
                        {item.test_name}
                      </span>
                      <span className="text-sm font-mono text-foreground">
                        {item.value} {item.unit}
                      </span>
                    </div>
                    {item.notes && (
                      <p className="text-xs text-muted-foreground truncate">
                        {item.notes}
                      </p>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 hover:text-destructive shrink-0"
                    onClick={() => {
                      handleDelete(item.id, item.test_name);
                    }}
                    disabled={remove.isPending}
                    aria-label={`Delete ${item.test_name}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function FunctionalTestsTab() {
  const { data: tests, isLoading, error } = useFunctionalTests();
  const [showForm, setShowForm] = useState(false);

  if (isLoading) return <LoadingState message="Loading functional tests..." />;
  if (error) return <ErrorCard message="Failed to load functional tests" />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Functional Tests</h2>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setShowForm(!showForm);
          }}
        >
          <Plus className="h-4 w-4 mr-1" />
          Add
        </Button>
      </div>

      {showForm && (
        <FunctionalTestForm
          onClose={() => {
            setShowForm(false);
          }}
        />
      )}

      <FunctionalTestList items={tests ?? []} />
    </div>
  );
}

function GoalForm({
  initial,
  onClose,
}: Readonly<{
  initial?: LongevityGoalData;
  onClose: () => void;
}>) {
  const create = useCreateLongevityGoal();
  const update = useUpdateLongevityGoal();
  const [category, setCategory] = useState(initial?.category ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [targetValue, setTargetValue] = useState(
    initial?.target_value != null ? String(initial.target_value) : "",
  );
  const [currentValue, setCurrentValue] = useState(
    initial?.current_value != null ? String(initial.current_value) : "",
  );
  const [unit, setUnit] = useState(initial?.unit ?? "");
  const [targetAge, setTargetAge] = useState(
    initial?.target_age != null ? String(initial.target_age) : "",
  );

  const isPending = initial ? update.isPending : create.isPending;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!category.trim() || !description.trim()) return;

    const payload = {
      category: category.trim(),
      description: description.trim(),
      target_value: targetValue ? Number.parseFloat(targetValue) : null,
      current_value: currentValue ? Number.parseFloat(currentValue) : null,
      unit: unit.trim() || null,
      target_age: targetAge ? Number.parseInt(targetAge, 10) : null,
    };

    if (initial) {
      update.mutate(
        { id: initial.id, data: payload },
        {
          onSuccess: () => {
            toast.success("Goal updated");
            onClose();
          },
          onError: (err) =>
            toast.error(err instanceof Error ? err.message : "Failed"),
        },
      );
    } else {
      create.mutate(payload, {
        onSuccess: () => {
          toast.success("Goal added");
          onClose();
        },
        onError: (err) =>
          toast.error(err instanceof Error ? err.message : "Failed"),
      });
    }
  };

  return (
    <Card className="border-dashed">
      <CardContent className="pt-4">
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label htmlFor="goal-category">Category *</Label>
              <Input
                id="goal-category"
                value={category}
                onChange={(e) => {
                  setCategory(e.target.value);
                }}
                placeholder="e.g. cardiovascular"
                required
              />
            </div>
            <div>
              <Label htmlFor="goal-target-age">Target Age</Label>
              <Input
                id="goal-target-age"
                type="number"
                value={targetAge}
                onChange={(e) => {
                  setTargetAge(e.target.value);
                }}
                placeholder="e.g. 80"
              />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="goal-description">Description *</Label>
              <textarea
                id="goal-description"
                value={description}
                onChange={(e) => {
                  setDescription(e.target.value);
                }}
                placeholder="e.g. Maintain VO2max above 50 ml/kg/min"
                required
                rows={3}
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
            <div>
              <Label htmlFor="goal-current">Current Value</Label>
              <Input
                id="goal-current"
                type="number"
                step="any"
                value={currentValue}
                onChange={(e) => {
                  setCurrentValue(e.target.value);
                }}
                placeholder="Optional"
              />
            </div>
            <div>
              <Label htmlFor="goal-target">Target Value</Label>
              <Input
                id="goal-target"
                type="number"
                step="any"
                value={targetValue}
                onChange={(e) => {
                  setTargetValue(e.target.value);
                }}
                placeholder="Optional"
              />
            </div>
            <div>
              <Label htmlFor="goal-unit">Unit</Label>
              <Input
                id="goal-unit"
                value={unit}
                onChange={(e) => {
                  setUnit(e.target.value);
                }}
                placeholder="e.g. ml/kg/min"
              />
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <Button type="button" variant="ghost" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={isPending}>
              {isPending ? "Saving..." : initial ? "Update" : "Save"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function GoalRow({
  goal,
}: Readonly<{
  goal: LongevityGoalData;
}>) {
  const remove = useDeleteLongevityGoal();
  const [isEditing, setIsEditing] = useState(false);

  const handleDelete = () => {
    remove.mutate(goal.id, {
      onSuccess: () => toast.success("Goal deleted"),
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "Failed"),
    });
  };

  if (isEditing) {
    return (
      <GoalForm
        initial={goal}
        onClose={() => {
          setIsEditing(false);
        }}
      />
    );
  }

  const hasProgress =
    goal.target_value != null &&
    goal.current_value != null &&
    goal.target_value !== 0;
  const percent = hasProgress
    ? Math.max(
        0,
        Math.min(
          100,
          ((goal.current_value ?? 0) / (goal.target_value ?? 1)) * 100,
        ),
      )
    : null;

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
                {goal.category}
              </span>
              {goal.target_age != null && (
                <span className="text-xs text-muted-foreground">
                  by age {goal.target_age}
                </span>
              )}
            </div>
            <p className="text-sm">{goal.description}</p>
            {(goal.current_value != null || goal.target_value != null) && (
              <div className="space-y-1">
                <div className="flex items-baseline justify-between text-xs text-muted-foreground">
                  <span className="font-mono">
                    {goal.current_value ?? "—"}
                    {goal.target_value != null &&
                      ` / ${String(goal.target_value)}`}
                    {goal.unit && ` ${goal.unit}`}
                  </span>
                  {percent != null && (
                    <span className="font-medium">{Math.round(percent)}%</span>
                  )}
                </div>
                {percent != null && (
                  <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary transition-all"
                      style={{ width: `${String(percent)}%` }}
                    />
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => {
                setIsEditing(true);
              }}
              aria-label="Edit goal"
            >
              <Pencil className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 hover:text-destructive"
              onClick={handleDelete}
              disabled={remove.isPending}
              aria-label="Delete goal"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function GoalList({
  items,
}: Readonly<{
  items: LongevityGoalData[];
}>) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4 text-center">
        No longevity goals defined
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {items.map((goal) => (
        <GoalRow key={goal.id} goal={goal} />
      ))}
    </div>
  );
}

function LongevityGoalsTab() {
  const { data: goals, isLoading, error } = useLongevityGoals();
  const [showForm, setShowForm] = useState(false);

  if (isLoading) return <LoadingState message="Loading goals..." />;
  if (error) return <ErrorCard message="Failed to load goals" />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Longevity Goals</h2>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setShowForm(!showForm);
          }}
        >
          <Plus className="h-4 w-4 mr-1" />
          Add
        </Button>
      </div>

      {showForm && (
        <GoalForm
          onClose={() => {
            setShowForm(false);
          }}
        />
      )}

      <GoalList items={goals ?? []} />
    </div>
  );
}

export function HealthLogPage() {
  const [tab, setTab] = useState<Tab>("medications");

  const renderTab = () => {
    if (tab === "medications") return <MedicationsTab />;
    if (tab === "labs") return <LabResultsTab />;
    if (tab === "tests") return <FunctionalTestsTab />;
    return <LongevityGoalsTab />;
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Health Log</h1>
        <p className="text-muted-foreground mt-1">
          Track medications, labs, functional tests, and longevity goals
        </p>
      </div>

      <div className="flex items-center gap-1 p-1 bg-muted/50 rounded-lg w-fit flex-wrap">
        <Button
          variant={tab === "medications" ? "default" : "ghost"}
          size="sm"
          onClick={() => {
            setTab("medications");
          }}
          className="gap-1.5"
        >
          <Pill className="h-4 w-4" />
          Medications
        </Button>
        <Button
          variant={tab === "labs" ? "default" : "ghost"}
          size="sm"
          onClick={() => {
            setTab("labs");
          }}
          className="gap-1.5"
        >
          <FlaskConical className="h-4 w-4" />
          Lab Results
        </Button>
        <Button
          variant={tab === "tests" ? "default" : "ghost"}
          size="sm"
          onClick={() => {
            setTab("tests");
          }}
          className="gap-1.5"
        >
          <Dumbbell className="h-4 w-4" />
          Functional Tests
        </Button>
        <Button
          variant={tab === "goals" ? "default" : "ghost"}
          size="sm"
          onClick={() => {
            setTab("goals");
          }}
          className="gap-1.5"
        >
          <Trophy className="h-4 w-4" />
          Longevity Goals
        </Button>
      </div>

      {renderTab()}
    </div>
  );
}
