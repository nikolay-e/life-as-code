import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import { formatSleepMinutes } from "../../../lib/metrics";
import type { SleepMetrics } from "../../../types/api";
import { Moon } from "lucide-react";
import { formatDaysLabel } from "./stat-utils";

export interface SleepSectionProps {
  readonly sleepMetrics: SleepMetrics;
  readonly shortTermDays: number;
  readonly baselineDays: number;
}

export function SleepSection({
  sleepMetrics,
  shortTermDays,
  baselineDays,
}: SleepSectionProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <Moon className="h-4 w-4" />
          Sleep Analysis
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-muted-foreground">Target</p>
            <p className="font-medium">
              {formatSleepMinutes(sleepMetrics.target_sleep)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Consistency (CV)</p>
            <p className="font-medium">
              {(sleepMetrics.sleep_cv * 100).toFixed(1)}%
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">
              {formatDaysLabel(shortTermDays)} Average
            </p>
            <p className="font-medium">
              {sleepMetrics.avg_sleep_short != null
                ? formatSleepMinutes(sleepMetrics.avg_sleep_short)
                : "—"}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">
              {formatDaysLabel(baselineDays)} Average
            </p>
            <p className="font-medium">
              {sleepMetrics.avg_sleep_long != null
                ? formatSleepMinutes(sleepMetrics.avg_sleep_long)
                : "—"}
            </p>
          </div>
        </div>
        <div className="pt-2 border-t">
          <div className="flex justify-between text-sm">
            <span>
              Debt:{" "}
              <span className="font-medium text-red-500">
                {formatSleepMinutes(sleepMetrics.sleep_debt_short)}
              </span>
            </span>
            <span>
              Surplus:{" "}
              <span className="font-medium text-green-500">
                {formatSleepMinutes(sleepMetrics.sleep_surplus_short)}
              </span>
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
