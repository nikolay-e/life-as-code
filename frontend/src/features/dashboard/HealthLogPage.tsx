import { useState, type FormEvent } from "react";
import { format } from "date-fns";
import { toast } from "sonner";
import { Plus, Square, Trash2, ChevronDown, ChevronRight } from "lucide-react";
import {
  useInterventions,
  useCreateIntervention,
  useUpdateIntervention,
  useDeleteIntervention,
  useBiomarkers,
  useCreateBiomarker,
  useDeleteBiomarker,
} from "../../hooks/useHealthLog";
import { Button } from "../../components/ui/button";
import { Label } from "../../components/ui/label";
import { LoadingState } from "../../components/ui/loading-state";
import { ErrorCard } from "../../components/ui/error-card";
import { cn } from "../../lib/utils";
import { getLocalDateString, getLocalToday } from "../../lib/health";
import type { InterventionData, BloodBiomarkerData } from "../../types/api";
import { Masthead } from "../../components/luxury/Masthead";
import { SectionHead, SerifEm } from "../../components/luxury/SectionHead";

type Tab = "medications" | "labs";
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

const todayStr = () => getLocalDateString(getLocalToday());

const editorialFieldClass =
  "w-full bg-transparent border-0 border-b border-border px-0 py-2 text-sm font-serif text-foreground placeholder:text-muted-foreground placeholder:font-serif placeholder:italic focus:outline-none focus:border-foreground transition-colors";

const editorialLabelClass =
  "type-mono-label text-muted-foreground block mb-1.5";

function formatDayKey(dateStr: string): { day: string; rest: string } {
  try {
    const d = new Date(`${dateStr}T00:00:00`);
    if (Number.isNaN(d.getTime())) return { day: dateStr, rest: "" };
    return {
      day: format(d, "dd MMM").toUpperCase(),
      rest: format(d, "EEE").toUpperCase(),
    };
  } catch {
    return { day: dateStr, rest: "" };
  }
}

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
    <div className="border-t border-b border-border py-7 my-2">
      <div className="type-mono-eyebrow text-muted-foreground mb-5">
        new entry · intervention
      </div>
      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-5">
          <div>
            <Label htmlFor="med-name" className={editorialLabelClass}>
              Name *
            </Label>
            <input
              id="med-name"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
              }}
              placeholder="Metformin"
              required
              className={editorialFieldClass}
            />
          </div>
          <div>
            <Label htmlFor="med-category" className={editorialLabelClass}>
              Category
            </Label>
            <select
              id="med-category"
              value={category}
              onChange={(e) => {
                setCategory(e.target.value as Category);
              }}
              className={editorialFieldClass}
            >
              {CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="med-dosage" className={editorialLabelClass}>
              Dosage
            </Label>
            <input
              id="med-dosage"
              value={dosage}
              onChange={(e) => {
                setDosage(e.target.value);
              }}
              placeholder="500 mg"
              className={editorialFieldClass}
            />
          </div>
          <div>
            <Label htmlFor="med-frequency" className={editorialLabelClass}>
              Frequency
            </Label>
            <input
              id="med-frequency"
              value={frequency}
              onChange={(e) => {
                setFrequency(e.target.value);
              }}
              placeholder="twice daily"
              className={editorialFieldClass}
            />
          </div>
          <div>
            <Label htmlFor="med-start" className={editorialLabelClass}>
              Start Date
            </Label>
            <input
              id="med-start"
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
              }}
              required
              className={editorialFieldClass}
            />
          </div>
          <div>
            <Label htmlFor="med-notes" className={editorialLabelClass}>
              Notes
            </Label>
            <input
              id="med-notes"
              value={notes}
              onChange={(e) => {
                setNotes(e.target.value);
              }}
              placeholder="optional"
              className={editorialFieldClass}
            />
          </div>
        </div>
        <div className="flex gap-2 justify-end pt-2">
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" size="sm" disabled={create.isPending}>
            {create.isPending ? "Saving..." : "Save"}
          </Button>
        </div>
      </form>
    </div>
  );
}

function InterventionRow({
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
  const dateLabel = formatDayKey(item.start_date);

  return (
    <div
      className={cn(
        "grid grid-cols-[80px_1fr_auto] gap-6 items-start py-6 border-b border-border",
        !isActive && "opacity-60",
      )}
    >
      <div className="type-mono-label text-muted-foreground leading-tight">
        <div className="text-foreground">{dateLabel.day}</div>
        <div className="mt-0.5">{dateLabel.rest}</div>
      </div>

      <div className="min-w-0">
        <div
          className="font-serif text-[19px] leading-snug tracking-[-0.01em] text-foreground"
          style={{
            fontVariationSettings: '"opsz" 14, "SOFT" 30',
            fontWeight: 400,
          }}
        >
          {item.name}
        </div>
        <div className="mt-1 flex flex-wrap gap-x-5 gap-y-0.5 type-mono-label text-muted-foreground">
          {item.dosage && <span>{item.dosage}</span>}
          {item.frequency && <span>{item.frequency}</span>}
          <span>from {item.start_date}</span>
          {item.end_date && <span>to {item.end_date}</span>}
        </div>
        {item.notes && (
          <p
            className="mt-2 font-serif italic text-sm text-muted-foreground leading-relaxed max-w-[60ch]"
            style={{
              fontVariationSettings: '"opsz" 14, "SOFT" 50',
              fontWeight: 380,
            }}
          >
            {item.notes}
          </p>
        )}
      </div>

      <div className="flex items-start gap-3 shrink-0">
        <span className="type-mono-label text-muted-foreground border border-border px-2 py-1">
          {item.category}
        </span>
        <div className="flex items-center gap-1">
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
    <section className="pt-10">
      <SectionHead
        title={
          <>
            Active <SerifEm>protocols</SerifEm>
          </>
        }
        meta={
          <>
            {active.length} active · {inactive.length} archived
            <br />
            interventions ledger
          </>
        }
      />

      <div className="flex justify-end mb-4">
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setShowForm(!showForm);
          }}
        >
          <Plus className="h-3.5 w-3.5 mr-1" />
          Add Entry
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
        <p
          className="font-serif italic text-muted-foreground py-12 text-center text-lg"
          style={{
            fontVariationSettings: '"opsz" 14, "SOFT" 50',
            fontWeight: 380,
          }}
        >
          No active interventions recorded.
        </p>
      ) : (
        <div className="border-t border-border">
          {active.map((item) => (
            <InterventionRow key={item.id} item={item} />
          ))}
        </div>
      )}

      {inactive.length > 0 && (
        <div className="mt-10 pt-6 border-t border-border">
          <button
            type="button"
            onClick={() => {
              setShowHistory(!showHistory);
            }}
            className="flex items-center gap-2 type-mono-eyebrow text-muted-foreground hover:text-foreground transition-colors"
          >
            {showHistory ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
            archived · {inactive.length}
          </button>
          {showHistory && (
            <div className="mt-4 border-t border-border">
              {inactive.map((item) => (
                <InterventionRow key={item.id} item={item} />
              ))}
            </div>
          )}
        </div>
      )}
    </section>
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
    <div className="border-t border-b border-border py-7 my-2">
      <div className="type-mono-eyebrow text-muted-foreground mb-5">
        new entry · biomarker
      </div>
      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-5">
          <div>
            <Label htmlFor="bio-date" className={editorialLabelClass}>
              Date *
            </Label>
            <input
              id="bio-date"
              type="date"
              value={date}
              onChange={(e) => {
                setDate(e.target.value);
              }}
              required
              className={editorialFieldClass}
            />
          </div>
          <div>
            <Label htmlFor="bio-marker" className={editorialLabelClass}>
              Marker *
            </Label>
            <input
              id="bio-marker"
              list="biomarker-presets"
              value={markerName}
              onChange={(e) => {
                handleMarkerChange(e.target.value);
              }}
              placeholder="TSH"
              required
              className={editorialFieldClass}
            />
            <datalist id="biomarker-presets">
              {BIOMARKER_PRESETS.map((p) => (
                <option key={p.name} value={p.name} />
              ))}
            </datalist>
          </div>
          <div>
            <Label htmlFor="bio-value" className={editorialLabelClass}>
              Value *
            </Label>
            <input
              id="bio-value"
              type="number"
              step="any"
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
              }}
              placeholder="2.5"
              required
              className={editorialFieldClass}
            />
          </div>
          <div>
            <Label htmlFor="bio-unit" className={editorialLabelClass}>
              Unit
            </Label>
            <input
              id="bio-unit"
              list="unit-presets"
              value={unit}
              onChange={(e) => {
                setUnit(e.target.value);
              }}
              placeholder="mIU/L"
              className={editorialFieldClass}
            />
            <datalist id="unit-presets">
              {[...new Set(BIOMARKER_PRESETS.map((p) => p.unit))].map((u) => (
                <option key={u} value={u} />
              ))}
            </datalist>
          </div>
          <div>
            <Label htmlFor="bio-ref-low" className={editorialLabelClass}>
              Ref. Low
            </Label>
            <input
              id="bio-ref-low"
              type="number"
              step="any"
              value={refLow}
              onChange={(e) => {
                setRefLow(e.target.value);
              }}
              placeholder="optional"
              className={editorialFieldClass}
            />
          </div>
          <div>
            <Label htmlFor="bio-ref-high" className={editorialLabelClass}>
              Ref. High
            </Label>
            <input
              id="bio-ref-high"
              type="number"
              step="any"
              value={refHigh}
              onChange={(e) => {
                setRefHigh(e.target.value);
              }}
              placeholder="optional"
              className={editorialFieldClass}
            />
          </div>
          <div>
            <Label htmlFor="bio-lab" className={editorialLabelClass}>
              Lab Name
            </Label>
            <input
              id="bio-lab"
              value={labName}
              onChange={(e) => {
                setLabName(e.target.value);
              }}
              placeholder="optional"
              className={editorialFieldClass}
            />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="bio-notes" className={editorialLabelClass}>
              Notes
            </Label>
            <input
              id="bio-notes"
              value={notes}
              onChange={(e) => {
                setNotes(e.target.value);
              }}
              placeholder="optional"
              className={editorialFieldClass}
            />
          </div>
        </div>
        <div className="flex gap-2 justify-end pt-2">
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" size="sm" disabled={create.isPending}>
            {create.isPending ? "Saving..." : "Save"}
          </Button>
        </div>
      </form>
    </div>
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
    <section className="pt-10">
      <SectionHead
        title={
          <>
            Lab <SerifEm>results</SerifEm>
          </>
        }
        meta={
          <>
            {items.length} measurements · {grouped.size} dates
            <br />
            biomarker archive
          </>
        }
      />

      <div className="flex justify-end mb-4">
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setShowForm(!showForm);
          }}
        >
          <Plus className="h-3.5 w-3.5 mr-1" />
          Add Result
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
        <p
          className="font-serif italic text-muted-foreground py-12 text-center text-lg"
          style={{
            fontVariationSettings: '"opsz" 14, "SOFT" 50',
            fontWeight: 380,
          }}
        >
          No lab results recorded.
        </p>
      ) : (
        <div className="border-t border-border">
          {[...grouped.entries()].map(([date, dateItems]) => {
            const dateLabel = formatDayKey(date);
            return (
              <div
                key={date}
                className="grid grid-cols-[80px_1fr] gap-6 items-start py-6 border-b border-border"
              >
                <div className="type-mono-label text-muted-foreground leading-tight">
                  <div className="text-foreground">{dateLabel.day}</div>
                  <div className="mt-0.5">{dateLabel.rest}</div>
                </div>
                <div className="space-y-3">
                  {dateItems.map((item) => {
                    const outOfRange = isOutOfRange(item);
                    const range = formatRange(
                      item.reference_range_low,
                      item.reference_range_high,
                    );
                    return (
                      <div
                        key={item.id}
                        className="flex items-baseline justify-between gap-4 py-2 border-b border-border/50 last:border-b-0"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                            <span
                              className="font-serif text-[17px] tracking-[-0.01em] text-foreground"
                              style={{
                                fontVariationSettings: '"opsz" 14, "SOFT" 30',
                                fontWeight: 400,
                              }}
                            >
                              {item.marker_name}
                            </span>
                            <span
                              className={cn(
                                "font-mono text-sm tabular-nums",
                                outOfRange
                                  ? "text-brass font-medium"
                                  : "text-foreground",
                              )}
                            >
                              {item.value} {item.unit}
                            </span>
                            {range && (
                              <span className="type-mono-label text-muted-foreground">
                                ref · {range}
                              </span>
                            )}
                          </div>
                          {(item.lab_name ?? item.notes) && (
                            <p
                              className="mt-1 font-serif italic text-sm text-muted-foreground"
                              style={{
                                fontVariationSettings: '"opsz" 14, "SOFT" 50',
                                fontWeight: 380,
                              }}
                            >
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
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

export function HealthLogPage() {
  const [tab, setTab] = useState<Tab>("medications");
  const todayDate = new Date();

  return (
    <div className="space-y-0">
      <Masthead
        leftLine="Section · Log"
        title={
          <>
            The <SerifEm>diary</SerifEm>
          </>
        }
        rightLine={format(todayDate, "d LLLL yyyy")}
      />

      <section className="py-7">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-5 pb-4 border-b border-border">
          <span className="type-mono-eyebrow text-muted-foreground">
            ledger
          </span>
          <div className="flex flex-wrap gap-0">
            <Button
              variant={tab === "medications" ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setTab("medications");
              }}
              className="first:ml-0"
            >
              Interventions
            </Button>
            <Button
              variant={tab === "labs" ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setTab("labs");
              }}
              className="-ml-px"
            >
              Lab Results
            </Button>
          </div>
        </div>
      </section>

      {tab === "medications" ? <MedicationsTab /> : <LabResultsTab />}
    </div>
  );
}
