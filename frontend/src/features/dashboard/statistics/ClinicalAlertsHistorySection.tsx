import { useState } from "react";
import { format, parseISO } from "date-fns";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import { Button } from "../../../components/ui/button";
import { LoadingState } from "../../../components/ui/loading-state";
import { ErrorCard } from "../../../components/ui/error-card";
import {
  useClinicalAlerts,
  useUpdateClinicalAlertStatus,
} from "../../../hooks/useClinicalAlerts";
import type {
  ClinicalAlertEvent,
  ClinicalAlertSeverity,
  ClinicalAlertStatus,
} from "../../../types/api";
import { cn } from "../../../lib/utils";

type StatusFilter = "all" | ClinicalAlertStatus;

const STATUS_FILTERS: {
  readonly value: StatusFilter;
  readonly label: string;
}[] = [
  { value: "all", label: "All" },
  { value: "open", label: "Open" },
  { value: "acknowledged", label: "Acknowledged" },
  { value: "resolved", label: "Resolved" },
];

const SEVERITY_STYLES: Record<ClinicalAlertSeverity, string> = {
  info: "bg-gray-500/15 text-gray-700 dark:text-gray-300 border-gray-500/30",
  warning:
    "bg-yellow-500/15 text-yellow-700 dark:text-yellow-300 border-yellow-500/30",
  alert:
    "bg-orange-500/15 text-orange-700 dark:text-orange-300 border-orange-500/30",
  critical: "bg-red-500/15 text-red-700 dark:text-red-300 border-red-500/30",
};

const STATUS_STYLES: Record<ClinicalAlertStatus, string> = {
  open: "bg-blue-500/15 text-blue-700 dark:text-blue-300 border-blue-500/30",
  acknowledged:
    "bg-gray-500/15 text-gray-700 dark:text-gray-300 border-gray-500/30",
  resolved:
    "bg-green-500/15 text-green-700 dark:text-green-300 border-green-500/30",
};

const DATE_FORMAT = "MMM d, yyyy h:mm a";

function humanizeAlertType(alertType: string): string {
  return alertType
    .split("_")
    .filter((part) => part.length > 0)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatTimestamp(value: string): string {
  try {
    return format(parseISO(value), DATE_FORMAT);
  } catch {
    return value;
  }
}

function SeverityBadge({
  severity,
}: {
  readonly severity: ClinicalAlertSeverity;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border uppercase tracking-wide",
        SEVERITY_STYLES[severity],
      )}
    >
      {severity}
    </span>
  );
}

function StatusBadge({ status }: { readonly status: ClinicalAlertStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border capitalize",
        STATUS_STYLES[status],
      )}
    >
      {status}
    </span>
  );
}

function detailValueText(value: unknown): string {
  if (typeof value === "object") return JSON.stringify(value);
  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return String(value);
  }
  return JSON.stringify(value);
}

function DetailsChips({
  details,
}: {
  readonly details: Record<string, unknown> | null;
}) {
  if (!details) return null;
  const entries = Object.entries(details);
  if (entries.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {entries.map(([key, value]) => (
        <span
          key={key}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-muted text-xs font-mono"
        >
          <span className="text-muted-foreground">{key}:</span>
          <span className="text-foreground">{detailValueText(value)}</span>
        </span>
      ))}
    </div>
  );
}

function AlertRow({ alert }: { readonly alert: ClinicalAlertEvent }) {
  const updateStatus = useUpdateClinicalAlertStatus();
  const reFired = alert.last_detected_at !== alert.first_detected_at;
  const canAct = alert.status === "open" || alert.status === "acknowledged";

  const handleUpdate = (status: ClinicalAlertStatus) => {
    updateStatus.mutate(
      { id: alert.id, status },
      {
        onSuccess: () => {
          toast.success(`Alert marked as ${status}`);
        },
        onError: (err: unknown) => {
          const message = err instanceof Error ? err.message : "Update failed";
          toast.error(message);
        },
      },
    );
  };

  return (
    <div className="p-4 rounded-lg border border-border bg-card flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <SeverityBadge severity={alert.severity} />
        <StatusBadge status={alert.status} />
        <span className="font-medium text-sm">
          {humanizeAlertType(alert.alert_type)}
        </span>
      </div>

      <div className="text-xs text-muted-foreground flex flex-wrap gap-x-4 gap-y-1">
        <span>First detected: {formatTimestamp(alert.first_detected_at)}</span>
        {reFired && (
          <span>Re-fired at: {formatTimestamp(alert.last_detected_at)}</span>
        )}
      </div>

      <DetailsChips details={alert.details_json} />

      {canAct && (
        <div className="flex flex-wrap gap-2 pt-1">
          {alert.status === "open" && (
            <Button
              size="sm"
              variant="outline"
              disabled={updateStatus.isPending}
              onClick={() => {
                handleUpdate("acknowledged");
              }}
            >
              Acknowledge
            </Button>
          )}
          <Button
            size="sm"
            variant="default"
            disabled={updateStatus.isPending}
            onClick={() => {
              handleUpdate("resolved");
            }}
          >
            Resolve
          </Button>
        </div>
      )}
    </div>
  );
}

export function ClinicalAlertsHistorySection() {
  const [filter, setFilter] = useState<StatusFilter>("all");
  const queryStatus = filter === "all" ? undefined : filter;
  const { data, isLoading, error } = useClinicalAlerts(queryStatus);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Clinical Alerts History</CardTitle>
        <div className="flex flex-wrap gap-2 pt-3">
          {STATUS_FILTERS.map((option) => (
            <Button
              key={option.value}
              size="sm"
              variant={filter === option.value ? "default" : "outline"}
              onClick={() => {
                setFilter(option.value);
              }}
              className="rounded-full"
            >
              {option.label}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        {(() => {
          if (isLoading) {
            return <LoadingState message="Loading clinical alerts..." />;
          }
          if (error) {
            return (
              <ErrorCard
                message={`Failed to load clinical alerts: ${error.message}`}
              />
            );
          }
          if (!data || data.length === 0) {
            return (
              <p className="text-sm text-muted-foreground py-6 text-center">
                No clinical alerts
              </p>
            );
          }
          return (
            <div className="flex flex-col gap-3">
              {data.map((alert) => (
                <AlertRow key={alert.id} alert={alert} />
              ))}
            </div>
          );
        })()}
      </CardContent>
    </Card>
  );
}
