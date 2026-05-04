import { useMemo, useState } from "react";
import { format, parseISO, isValid } from "date-fns";
import type { DateRange, Matcher } from "react-day-picker";
import { Calendar as CalendarIcon } from "lucide-react";
import { Button } from "./button";
import { Calendar } from "./calendar";
import { Popover } from "./popover";
import { cn } from "../../lib/utils";

interface DateRangePickerProps {
  readonly start: string;
  readonly end: string;
  readonly onChange: (range: { start: string; end: string }) => void;
  readonly className?: string;
  readonly disabled?: Matcher | Matcher[];
}

const toDate = (value: string): Date | undefined => {
  if (!value) return undefined;
  const parsed = parseISO(value);
  return isValid(parsed) ? parsed : undefined;
};

const toIso = (date: Date): string => format(date, "yyyy-MM-dd");

export function DateRangePicker({
  start,
  end,
  onChange,
  className,
  disabled,
}: DateRangePickerProps) {
  const [open, setOpen] = useState(false);

  const selected = useMemo<DateRange | undefined>(() => {
    const from = toDate(start);
    const to = toDate(end);
    if (!from && !to) return undefined;
    return { from, to };
  }, [start, end]);

  const label = useMemo(() => {
    const from = toDate(start);
    const to = toDate(end);
    if (from && to) {
      const sameYear = from.getFullYear() === to.getFullYear();
      const fmt = sameYear ? "MMM d" : "MMM d, yyyy";
      return `${format(from, fmt)} — ${format(to, "MMM d, yyyy")}`;
    }
    if (from) return `${format(from, "MMM d, yyyy")} — …`;
    return "Select range";
  }, [start, end]);

  return (
    <Popover
      open={open}
      onOpenChange={setOpen}
      align="end"
      contentClassName="p-0"
      trigger={
        <Button
          variant="outline"
          size="sm"
          className={cn("gap-2 font-normal text-sm", className)}
        >
          <CalendarIcon className="h-3.5 w-3.5 text-muted-foreground" />
          <span>{label}</span>
        </Button>
      }
    >
      <Calendar
        mode="range"
        numberOfMonths={2}
        selected={selected}
        defaultMonth={selected?.from}
        disabled={disabled}
        onSelect={(range) => {
          if (!range) return;
          const from = range.from;
          const to = range.to ?? range.from;
          if (!from || !to) return;
          onChange({ start: toIso(from), end: toIso(to) });
          if (range.from && range.to) {
            setOpen(false);
          }
        }}
      />
    </Popover>
  );
}

interface DateInputPickerProps {
  readonly value: string;
  readonly onChange: (next: string) => void;
  readonly className?: string;
  readonly disabled?: Matcher | Matcher[];
  readonly placeholder?: string;
  readonly fromYear?: number;
  readonly toYear?: number;
  readonly captionLayout?:
    | "label"
    | "dropdown"
    | "dropdown-months"
    | "dropdown-years";
}

export function DateInputPicker({
  value,
  onChange,
  className,
  disabled,
  placeholder = "Select date",
  fromYear,
  toYear,
  captionLayout,
}: DateInputPickerProps) {
  const [open, setOpen] = useState(false);
  const selected = toDate(value);
  const label = selected ? format(selected, "MMM d, yyyy") : placeholder;

  return (
    <Popover
      open={open}
      onOpenChange={setOpen}
      align="start"
      contentClassName="p-0"
      trigger={
        <Button
          variant="outline"
          size="sm"
          type="button"
          className={cn("gap-2 font-normal text-sm justify-start", className)}
        >
          <CalendarIcon className="h-3.5 w-3.5 text-muted-foreground" />
          <span>{label}</span>
        </Button>
      }
    >
      <Calendar
        mode="single"
        selected={selected}
        defaultMonth={selected ?? (toYear ? new Date(toYear, 0) : undefined)}
        disabled={disabled}
        captionLayout={captionLayout}
        startMonth={fromYear ? new Date(fromYear, 0) : undefined}
        endMonth={toYear ? new Date(toYear, 11) : undefined}
        onSelect={(date) => {
          if (!date) return;
          onChange(toIso(date));
          setOpen(false);
        }}
      />
    </Popover>
  );
}
