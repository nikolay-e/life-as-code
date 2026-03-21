import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import type {
  ActivityMetrics,
  WeightMetrics,
  RecoveryMetrics,
} from "../../../types/api";
import { Activity, Scale, Brain } from "lucide-react";
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

export function ActivitySection({
  activityMetrics,
  weightMetrics,
  recoveryMetrics,
  shortTermDays,
  baselineDays,
}: ActivitySectionProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Activity Analysis
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-muted-foreground">
                Steps {formatDaysLabel(shortTermDays)} avg
              </p>
              <p className="font-medium">
                {activityMetrics.steps_avg_short != null
                  ? Math.round(activityMetrics.steps_avg_short).toLocaleString()
                  : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">
                Steps {formatDaysLabel(baselineDays)} avg
              </p>
              <p className="font-medium">
                {activityMetrics.steps_avg_long != null
                  ? Math.round(activityMetrics.steps_avg_long).toLocaleString()
                  : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Acute Load</p>
              <p className="font-medium">
                {activityMetrics.acute_load?.toFixed(1) ?? "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Chronic Load</p>
              <p className="font-medium">
                {activityMetrics.chronic_load?.toFixed(1) ?? "—"}
              </p>
            </div>
          </div>
          <div className="pt-2 border-t">
            <div className="flex justify-between text-sm">
              <span>
                ACWR:{" "}
                <span className="font-medium">
                  {activityMetrics.acwr?.toFixed(2) ?? "—"}
                </span>
              </span>
              <span>
                Steps CV:{" "}
                <span className="font-medium">
                  {(activityMetrics.steps_cv * 100).toFixed(0)}%
                </span>
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Scale className="h-4 w-4" />
            Weight Analysis
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-muted-foreground">
                EMA {formatDaysLabel(shortTermDays)}
              </p>
              <p className="font-medium">
                {weightMetrics.ema_short != null
                  ? `${weightMetrics.ema_short.toFixed(1)} kg`
                  : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">
                EMA {formatDaysLabel(baselineDays)}
              </p>
              <p className="font-medium">
                {weightMetrics.ema_long != null
                  ? `${weightMetrics.ema_long.toFixed(1)} kg`
                  : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">
                {formatDaysLabel(shortTermDays)} change
              </p>
              <p
                className={cn(
                  "font-medium",
                  getWeightChangeColor(weightMetrics.period_change),
                )}
              >
                {weightMetrics.period_change != null
                  ? `${signPrefix(weightMetrics.period_change)}${weightMetrics.period_change.toFixed(2)} kg`
                  : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">
                Volatility {formatDaysLabel(shortTermDays)}
              </p>
              <p className="font-medium">
                ±{weightMetrics.volatility_short.toFixed(2)} kg
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Brain className="h-4 w-4" />
            Stress Analysis
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-muted-foreground">
                {formatDaysLabel(shortTermDays)} load
              </p>
              <p className="font-medium">
                {recoveryMetrics.stress_load_short != null
                  ? Math.round(recoveryMetrics.stress_load_short)
                  : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">
                {formatDaysLabel(baselineDays)} load
              </p>
              <p className="font-medium">
                {recoveryMetrics.stress_load_long != null
                  ? Math.round(recoveryMetrics.stress_load_long)
                  : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Trend</p>
              <p
                className={cn(
                  "font-medium",
                  getStressTrendColor(recoveryMetrics.stress_trend),
                )}
              >
                {recoveryMetrics.stress_trend != null
                  ? `${signPrefix(recoveryMetrics.stress_trend)}${recoveryMetrics.stress_trend.toFixed(1)}`
                  : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Recovery CV</p>
              <p className="font-medium">
                {recoveryMetrics.recovery_cv != null
                  ? `${(recoveryMetrics.recovery_cv * 100).toFixed(1)}%`
                  : "—"}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
