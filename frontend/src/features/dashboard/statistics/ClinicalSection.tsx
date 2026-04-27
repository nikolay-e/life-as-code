import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../../../components/ui/card";
import type { ClinicalAlerts } from "../../../types/api";
import { Heart, TrendingDown, Scale, Flame, ShieldAlert } from "lucide-react";

export interface ClinicalSectionProps {
  readonly clinicalAlerts: ClinicalAlerts;
}

export function ClinicalSection({ clinicalAlerts }: ClinicalSectionProps) {
  if (!clinicalAlerts.any_alert) return null;
  return (
    <Card className="border-red-500/50 bg-red-500/5">
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-red-500/20">
            <ShieldAlert className="h-6 w-6 text-red-500" />
          </div>
          <div>
            <CardTitle className="text-red-700 dark:text-red-400">
              Clinical Alerts
            </CardTitle>
            <CardDescription>
              Potential health concerns detected
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          {clinicalAlerts.persistent_tachycardia && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
              <div className="flex items-center gap-2 mb-1">
                <Heart className="h-4 w-4 text-red-500" />
                <span className="text-sm font-medium text-red-700 dark:text-red-400">
                  Elevated RHR
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                {clinicalAlerts.tachycardia_days} consecutive days above
                baseline +2σ
              </p>
            </div>
          )}
          {clinicalAlerts.acute_hrv_drop && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
              <div className="flex items-center gap-2 mb-1">
                <TrendingDown className="h-4 w-4 text-red-500" />
                <span className="text-sm font-medium text-red-700 dark:text-red-400">
                  Acute HRV Drop
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                {clinicalAlerts.hrv_drop_percent == null
                  ? "—"
                  : `${(clinicalAlerts.hrv_drop_percent * 100).toFixed(0)}%`}{" "}
                drop from previous day
              </p>
            </div>
          )}
          {clinicalAlerts.progressive_weight_loss && (
            <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
              <div className="flex items-center gap-2 mb-1">
                <Scale className="h-4 w-4 text-yellow-500" />
                <span className="text-sm font-medium text-yellow-700 dark:text-yellow-400">
                  Weight Loss
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                {clinicalAlerts.weight_loss_percent == null
                  ? "—"
                  : `${(clinicalAlerts.weight_loss_percent * 100).toFixed(1)}%`}{" "}
                loss over 30 days
              </p>
            </div>
          )}
          {clinicalAlerts.severe_overtraining && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
              <div className="flex items-center gap-2 mb-1">
                <Flame className="h-4 w-4 text-red-500" />
                <span className="text-sm font-medium text-red-700 dark:text-red-400">
                  Overtraining Risk
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                High ACWR + suppressed HRV detected
              </p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
