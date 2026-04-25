import { formatSleepMinutes } from "../../../lib/metrics";
import type {
  RecoveryMetrics,
  SleepMetrics,
  ActivityMetrics,
} from "../../../types/api";
import { cn } from "../../../lib/utils";
import { ZCard } from "../../../components/luxury/ZCard";
import {
  getHrvRhrLabel,
  getAcwrLabel,
  signPrefix,
  formatDaysLabel,
} from "./stat-utils";

export interface RecoverySectionProps {
  readonly recoveryMetrics: RecoveryMetrics;
  readonly sleepMetrics: SleepMetrics;
  readonly activityMetrics: ActivityMetrics;
  readonly shortTermDays: number;
  readonly trendWindow: number;
}

export function RecoverySection({
  recoveryMetrics,
  sleepMetrics,
  activityMetrics,
  shortTermDays,
  trendWindow,
}: RecoverySectionProps) {
  const hrvRhr = recoveryMetrics.hrv_rhr_imbalance;
  const sleepDebt = sleepMetrics.sleep_debt_short;
  const acwr = activityMetrics.acwr;
  const stepsChange = activityMetrics.steps_change;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 border-t border-border md:[&>*:nth-child(2n)]:border-l md:[&>*:nth-child(2n)]:border-border lg:[&>*]:border-l lg:[&>*]:border-border lg:[&>*:first-child]:border-l-0">
      <ZCard
        name="HRV–RHR balance"
        period="autonomic axis"
        value={hrvRhr == null ? "—" : hrvRhr.toFixed(2)}
        zScore={hrvRhr == null ? null : -hrvRhr}
        zLabel="balance"
        footer={getHrvRhrLabel(hrvRhr)}
      />
      <ZCard
        name="Sleep debt"
        period={`${formatDaysLabel(shortTermDays)} window`}
        value={formatSleepMinutes(sleepDebt)}
        zScore={null}
        zLabel="debt"
        footer={
          <>vs target {formatSleepMinutes(sleepMetrics.target_sleep)}/night</>
        }
      />
      <ZCard
        name="Acute / chronic"
        period="training load"
        value={acwr == null ? "—" : acwr.toFixed(2)}
        zScore={acwr == null ? null : (acwr - 1) * 2}
        zLabel="ratio"
        footer={getAcwrLabel(acwr)}
      />
      <ZCard
        name="Steps trend"
        period={`${formatDaysLabel(trendWindow)} vs prev`}
        value={
          stepsChange == null
            ? "—"
            : `${signPrefix(stepsChange)}${Math.round(stepsChange).toLocaleString()}`
        }
        zScore={stepsChange == null ? null : stepsChange / 2000}
        zLabel="δ"
        footer={
          <span
            className={cn(
              stepsChange != null && stepsChange < 0 && "text-rust",
            )}
          >
            {formatDaysLabel(trendWindow)} window
          </span>
        }
      />
    </div>
  );
}
