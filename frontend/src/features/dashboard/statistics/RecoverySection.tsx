import { Card, CardContent } from "../../../components/ui/card";
import { formatSleepMinutes } from "../../../lib/metrics";
import type {
  RecoveryMetrics,
  SleepMetrics,
  ActivityMetrics,
} from "../../../types/api";
import { Heart, Moon, Zap, Footprints } from "lucide-react";
import { cn } from "../../../lib/utils";
import {
  getHrvRhrColor,
  getHrvRhrLabel,
  getSleepDebtColor,
  getAcwrColor,
  getAcwrLabel,
  getStepsChangeColor,
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
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center gap-2 mb-2">
            <Heart className="h-4 w-4 text-red-700" />
            <span className="text-sm font-medium">HRV-RHR Imbalance</span>
          </div>
          <p
            className={cn(
              "text-2xl font-bold",
              getHrvRhrColor(recoveryMetrics.hrv_rhr_imbalance),
            )}
          >
            {recoveryMetrics.hrv_rhr_imbalance == null
              ? "—"
              : recoveryMetrics.hrv_rhr_imbalance.toFixed(2)}
          </p>
          <p className="text-xs text-muted-foreground">
            {getHrvRhrLabel(recoveryMetrics.hrv_rhr_imbalance)}
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center gap-2 mb-2">
            <Moon className="h-4 w-4 text-indigo-500" />
            <span className="text-sm font-medium">
              Sleep Debt ({formatDaysLabel(shortTermDays)})
            </span>
          </div>
          <p
            className={cn(
              "text-2xl font-bold",
              getSleepDebtColor(sleepMetrics.sleep_debt_short),
            )}
          >
            {formatSleepMinutes(sleepMetrics.sleep_debt_short)}
          </p>
          <p className="text-xs text-muted-foreground">
            vs target {formatSleepMinutes(sleepMetrics.target_sleep)}/night
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="h-4 w-4 text-orange-500" />
            <span className="text-sm font-medium">Acute:Chronic Ratio</span>
          </div>
          <p
            className={cn(
              "text-2xl font-bold",
              getAcwrColor(activityMetrics.acwr),
            )}
          >
            {activityMetrics.acwr == null
              ? "—"
              : activityMetrics.acwr.toFixed(2)}
          </p>
          <p className="text-xs text-muted-foreground">
            {getAcwrLabel(activityMetrics.acwr)}
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center gap-2 mb-2">
            <Footprints className="h-4 w-4 text-emerald-500" />
            <span className="text-sm font-medium">Steps Trend</span>
          </div>
          <p
            className={cn(
              "text-2xl font-bold",
              getStepsChangeColor(activityMetrics.steps_change),
            )}
          >
            {activityMetrics.steps_change == null
              ? "—"
              : `${signPrefix(activityMetrics.steps_change)}${Math.round(activityMetrics.steps_change).toLocaleString()}`}
          </p>
          <p className="text-xs text-muted-foreground">
            {formatDaysLabel(trendWindow)} vs prev{" "}
            {formatDaysLabel(trendWindow)}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
