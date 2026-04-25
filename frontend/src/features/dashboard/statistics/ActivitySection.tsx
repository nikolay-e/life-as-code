import type {
  ActivityMetrics,
  WeightMetrics,
  RecoveryMetrics,
} from "../../../types/api";
import { cn } from "../../../lib/utils";
import {
  getWeightChangeColor,
  getStressTrendColor,
  signPrefix,
  formatDaysLabel,
} from "./stat-utils";

export interface ActivitySectionProps {
  readonly activityMetrics: ActivityMetrics;
  readonly weightMetrics: WeightMetrics;
  readonly recoveryMetrics: RecoveryMetrics;
  readonly shortTermDays: number;
  readonly baselineDays: number;
}

interface PanelProps {
  readonly title: string;
  readonly children: React.ReactNode;
}

function Panel({ title, children }: PanelProps) {
  return (
    <article className="border border-border bg-background transition-colors duration-300 hover:bg-secondary/40">
      <header className="px-6 py-4 border-b border-border">
        <h3
          className="font-serif text-[20px] leading-none tracking-[-0.01em]"
          style={{
            fontVariationSettings: '"opsz" 144, "SOFT" 100',
            fontStyle: "italic",
            fontWeight: 400,
          }}
        >
          {title}
        </h3>
      </header>
      <div className="p-6">{children}</div>
    </article>
  );
}

interface RowProps {
  readonly label: string;
  readonly value: React.ReactNode;
  readonly toneClass?: string;
}

function Row({ label, value, toneClass }: RowProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="type-mono-label text-muted-foreground">{label}</span>
      <span
        className={cn(
          "font-mono text-[15px] tracking-tight",
          toneClass ?? "text-foreground",
        )}
        style={{ fontFeatureSettings: '"lnum","tnum"' }}
      >
        {value}
      </span>
    </div>
  );
}

export function ActivitySection({
  activityMetrics,
  weightMetrics,
  recoveryMetrics,
  shortTermDays,
  baselineDays,
}: ActivitySectionProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      <Panel title="Activity">
        <div className="grid grid-cols-2 gap-x-6 gap-y-5">
          <Row
            label={`Steps · ${formatDaysLabel(shortTermDays)} avg`}
            value={
              activityMetrics.steps_avg_short == null
                ? "—"
                : Math.round(activityMetrics.steps_avg_short).toLocaleString()
            }
          />
          <Row
            label={`Steps · ${formatDaysLabel(baselineDays)} avg`}
            value={
              activityMetrics.steps_avg_long == null
                ? "—"
                : Math.round(activityMetrics.steps_avg_long).toLocaleString()
            }
          />
          <Row
            label="Acute load"
            value={activityMetrics.acute_load?.toFixed(1) ?? "—"}
          />
          <Row
            label="Chronic load"
            value={activityMetrics.chronic_load?.toFixed(1) ?? "—"}
          />
        </div>
        <div className="mt-5 pt-4 border-t border-border grid grid-cols-2 gap-x-6">
          <Row label="ACWR" value={activityMetrics.acwr?.toFixed(2) ?? "—"} />
          <Row
            label="Steps CV"
            value={`${(activityMetrics.steps_cv * 100).toFixed(0)}%`}
          />
        </div>
      </Panel>

      <Panel title="Weight">
        <div className="grid grid-cols-2 gap-x-6 gap-y-5">
          <Row
            label={`EMA · ${formatDaysLabel(shortTermDays)}`}
            value={
              weightMetrics.ema_short == null
                ? "—"
                : `${weightMetrics.ema_short.toFixed(1)} kg`
            }
          />
          <Row
            label={`EMA · ${formatDaysLabel(baselineDays)}`}
            value={
              weightMetrics.ema_long == null
                ? "—"
                : `${weightMetrics.ema_long.toFixed(1)} kg`
            }
          />
          <Row
            label={`${formatDaysLabel(shortTermDays)} change`}
            value={
              weightMetrics.period_change == null
                ? "—"
                : `${signPrefix(weightMetrics.period_change)}${weightMetrics.period_change.toFixed(2)} kg`
            }
            toneClass={getWeightChangeColor(weightMetrics.period_change)}
          />
          <Row
            label={`Volatility · ${formatDaysLabel(shortTermDays)}`}
            value={`±${weightMetrics.volatility_short.toFixed(2)} kg`}
          />
        </div>
      </Panel>

      <Panel title="Stress">
        <div className="grid grid-cols-2 gap-x-6 gap-y-5">
          <Row
            label={`${formatDaysLabel(shortTermDays)} load`}
            value={
              recoveryMetrics.stress_load_short == null
                ? "—"
                : Math.round(recoveryMetrics.stress_load_short)
            }
          />
          <Row
            label={`${formatDaysLabel(baselineDays)} load`}
            value={
              recoveryMetrics.stress_load_long == null
                ? "—"
                : Math.round(recoveryMetrics.stress_load_long)
            }
          />
          <Row
            label="Trend"
            value={
              recoveryMetrics.stress_trend == null
                ? "—"
                : `${signPrefix(recoveryMetrics.stress_trend)}${recoveryMetrics.stress_trend.toFixed(1)}`
            }
            toneClass={getStressTrendColor(recoveryMetrics.stress_trend)}
          />
          <Row
            label="Recovery CV"
            value={
              recoveryMetrics.recovery_cv == null
                ? "—"
                : `${(recoveryMetrics.recovery_cv * 100).toFixed(1)}%`
            }
          />
        </div>
      </Panel>
    </div>
  );
}
