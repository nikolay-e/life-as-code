import { formatSleepMinutes } from "../../../lib/metrics";
import type { SleepMetrics } from "../../../types/api";
import { formatDaysLabel } from "./stat-utils";

export interface SleepSectionProps {
  readonly sleepMetrics: SleepMetrics;
  readonly shortTermDays: number;
  readonly baselineDays: number;
}

interface CellProps {
  readonly label: string;
  readonly value: string;
  readonly tone?: "default" | "good" | "bad";
}

function Cell({ label, value, tone = "default" }: CellProps) {
  const toneClass =
    tone === "good"
      ? "text-moss"
      : tone === "bad"
        ? "text-rust"
        : "text-foreground";
  return (
    <div className="flex flex-col gap-1.5 px-6 py-7">
      <span className="type-mono-label text-muted-foreground">{label}</span>
      <span
        className={`font-serif text-[clamp(28px,3.2vw,40px)] leading-none tracking-[-0.03em] ${toneClass}`}
        style={{
          fontVariationSettings: '"opsz" 144, "SOFT" 60',
          fontWeight: 350,
          fontFeatureSettings: '"lnum","tnum"',
        }}
      >
        {value}
      </span>
    </div>
  );
}

export function SleepSection({
  sleepMetrics,
  shortTermDays,
  baselineDays,
}: SleepSectionProps) {
  return (
    <div className="border-t border-border">
      <div className="grid grid-cols-2 lg:grid-cols-4 divide-x divide-border">
        <Cell
          label="Target / night"
          value={formatSleepMinutes(sleepMetrics.target_sleep)}
        />
        <Cell
          label="Consistency · CV"
          value={`${(sleepMetrics.sleep_cv * 100).toFixed(1)}%`}
        />
        <Cell
          label={`${formatDaysLabel(shortTermDays)} average`}
          value={
            sleepMetrics.avg_sleep_short == null
              ? "—"
              : formatSleepMinutes(sleepMetrics.avg_sleep_short)
          }
        />
        <Cell
          label={`${formatDaysLabel(baselineDays)} average`}
          value={
            sleepMetrics.avg_sleep_long == null
              ? "—"
              : formatSleepMinutes(sleepMetrics.avg_sleep_long)
          }
        />
      </div>
      <div className="grid grid-cols-2 divide-x divide-border border-t border-border">
        <Cell
          label="Debt"
          value={formatSleepMinutes(sleepMetrics.sleep_debt_short)}
          tone="bad"
        />
        <Cell
          label="Surplus"
          value={formatSleepMinutes(sleepMetrics.sleep_surplus_short)}
          tone="good"
        />
      </div>
    </div>
  );
}
