import { useHealthData, useSyncStatus } from "../../hooks/useHealthData";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../../components/ui/card";
import { LoadingState } from "../../components/ui/loading-state";
import { ErrorCard } from "../../components/ui/error-card";
import { format, parseISO, differenceInDays } from "date-fns";
import {
  CheckCircle,
  AlertCircle,
  Clock,
  Database,
  Activity,
  RefreshCw,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { getLatestSyncDate, getLastSyncForSource } from "../../lib/sync-utils";

type DataCadence = "daily" | "sporadic";

interface DataSourceStatus {
  name: string;
  provider: string;
  count: number;
  latestDate: string | null;
  oldestDate: string | null;
  cadence: DataCadence;
}

interface SourceGroup {
  name: string;
  syncKey: string;
  color: string;
  items: DataSourceStatus[];
}

export function DataStatusPage() {
  const { data, isLoading, error } = useHealthData(365);
  const { data: syncStatus, isLoading: syncLoading } = useSyncStatus();

  if (isLoading || syncLoading) {
    return <LoadingState message="Loading data status..." />;
  }

  if (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Unknown error";
    return (
      <ErrorCard message={`Failed to load data status: ${errorMessage}`} />
    );
  }

  const getDataSourceStatus = (
    items: Array<{ date: string }> | undefined,
    name: string,
    provider: string,
    cadence: DataCadence = "daily",
  ): DataSourceStatus => {
    if (!items || items.length === 0) {
      return {
        name,
        provider,
        count: 0,
        latestDate: null,
        oldestDate: null,
        cadence,
      };
    }
    const sorted = [...items].sort(
      (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime(),
    );
    return {
      name,
      provider,
      count: items.length,
      latestDate: sorted[0].date,
      oldestDate: (sorted.at(-1) ?? sorted[0]).date,
      cadence,
    };
  };

  const sourceGroups: SourceGroup[] = [
    {
      name: "Garmin",
      syncKey: "garmin",
      color: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
      items: [
        getDataSourceStatus(data?.sleep, "Sleep", "Garmin"),
        getDataSourceStatus(data?.hrv, "HRV", "Garmin"),
        getDataSourceStatus(data?.heart_rate, "Heart Rate", "Garmin"),
        getDataSourceStatus(data?.weight, "Weight", "Garmin"),
        getDataSourceStatus(data?.stress, "Stress", "Garmin"),
        getDataSourceStatus(data?.steps, "Steps", "Garmin"),
        getDataSourceStatus(data?.energy, "Energy", "Garmin"),
        getDataSourceStatus(
          data?.garmin_training_status,
          "Training Status",
          "Garmin",
        ),
        getDataSourceStatus(
          data?.garmin_activity,
          "Activities",
          "Garmin",
          "sporadic",
        ),
        getDataSourceStatus(
          data?.garmin_race_prediction,
          "Race Predictions",
          "Garmin",
        ),
      ],
    },
    {
      name: "Whoop",
      syncKey: "whoop",
      color:
        "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
      items: [
        getDataSourceStatus(data?.whoop_recovery, "Recovery", "Whoop"),
        getDataSourceStatus(data?.whoop_sleep, "Sleep", "Whoop"),
        getDataSourceStatus(
          data?.whoop_workout,
          "Workouts",
          "Whoop",
          "sporadic",
        ),
        getDataSourceStatus(data?.whoop_cycle, "Cycles", "Whoop"),
      ],
    },
    {
      name: "Hevy",
      syncKey: "hevy",
      color:
        "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
      items: [
        getDataSourceStatus(data?.workouts, "Workouts", "Hevy", "sporadic"),
      ],
    },
    {
      name: "Eight Sleep",
      syncKey: "eight_sleep",
      color:
        "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300",
      items: [
        getDataSourceStatus(
          data?.eight_sleep_sessions,
          "Sleep Sessions",
          "Eight Sleep",
        ),
      ],
    },
  ];

  const allSources = sourceGroups.flatMap((g) => g.items);

  const getSporadicSourceSyncProvider = (
    status: DataSourceStatus,
  ): string | null => {
    const providerToSource: Record<string, string> = {
      Hevy: "hevy",
      Whoop: "whoop",
      Garmin: "garmin",
      "Eight Sleep": "eight_sleep",
    };
    const source = providerToSource[status.provider];
    return source ? getLastSyncForSource(syncStatus, source) : null;
  };

  const isSporadicRecentlySynced = (status: DataSourceStatus): boolean => {
    const lastSync = getSporadicSourceSyncProvider(status);
    if (!lastSync) return false;
    return differenceInDays(new Date(), parseISO(lastSync)) <= 7;
  };

  const getStatusInfo = (status: DataSourceStatus) => {
    if (status.count === 0) {
      return {
        icon: AlertCircle,
        colorClass: "text-muted-foreground",
        bgClass: "bg-muted",
        label: "No data",
      };
    }
    if (!status.latestDate) {
      return {
        icon: AlertCircle,
        colorClass: "text-destructive",
        bgClass: "bg-destructive/10",
        label: "Stale",
      };
    }

    const daysSinceUpdate = differenceInDays(
      new Date(),
      parseISO(status.latestDate),
    );

    if (daysSinceUpdate <= 1) {
      return {
        icon: CheckCircle,
        colorClass: "text-success",
        bgClass: "bg-success/10",
        label: "Up to date",
      };
    }
    if (daysSinceUpdate <= 7) {
      return {
        icon: Clock,
        colorClass: "text-warning",
        bgClass: "bg-warning/10",
        label: `${String(daysSinceUpdate)}d ago`,
      };
    }
    if (status.cadence === "sporadic" && isSporadicRecentlySynced(status)) {
      return {
        icon: Clock,
        colorClass: "text-warning",
        bgClass: "bg-warning/10",
        label: `No new data · ${String(daysSinceUpdate)}d ago`,
      };
    }
    if (status.cadence === "sporadic" && daysSinceUpdate <= 30) {
      return {
        icon: Clock,
        colorClass: "text-warning",
        bgClass: "bg-warning/10",
        label: `${String(daysSinceUpdate)}d ago`,
      };
    }
    return {
      icon: AlertCircle,
      colorClass: "text-destructive",
      bgClass: "bg-destructive/10",
      label: "Stale",
    };
  };

  const totalRecords = allSources.reduce((sum, ds) => sum + ds.count, 0);
  const activeSources = allSources.filter((ds) => ds.count > 0).length;

  const syncSources = sourceGroups.filter((g) =>
    g.items.some((i) => i.count > 0),
  );

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Data Status</h1>
        <p className="text-muted-foreground mt-1">
          Monitor your health data sources
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div className="space-y-2">
                <p className="text-sm font-medium text-muted-foreground">
                  Total Records
                </p>
                <p className="text-3xl font-bold tracking-tight">
                  {totalRecords.toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground">
                  Across all sources
                </p>
              </div>
              <div className="p-2.5 rounded-xl bg-primary/10">
                <Database className="h-5 w-5 text-primary" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div className="space-y-2">
                <p className="text-sm font-medium text-muted-foreground">
                  Active Sources
                </p>
                <p className="text-3xl font-bold tracking-tight">
                  {activeSources}
                  <span className="text-lg font-normal text-muted-foreground">
                    /{String(allSources.length)}
                  </span>
                </p>
                <p className="text-xs text-muted-foreground">
                  Data types tracked
                </p>
              </div>
              <div className="p-2.5 rounded-xl bg-success/10">
                <Activity className="h-5 w-5 text-success" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div className="space-y-2">
                <p className="text-sm font-medium text-muted-foreground">
                  Last Sync
                </p>
                {(() => {
                  const withDates = syncStatus?.filter(
                    (s): s is typeof s & { last_sync_date: string } =>
                      s.last_sync_date != null,
                  );
                  const lastSync = withDates?.sort(
                    (a, b) =>
                      new Date(b.last_sync_date).getTime() -
                      new Date(a.last_sync_date).getTime(),
                  )[0];
                  return (
                    <>
                      <p className="text-3xl font-bold tracking-tight">
                        {lastSync?.last_sync_date
                          ? format(parseISO(lastSync.last_sync_date), "MMM d")
                          : "Never"}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {lastSync?.source ?? "No sync recorded"}
                      </p>
                    </>
                  );
                })()}
              </div>
              <div className="p-2.5 rounded-xl bg-muted">
                <Clock className="h-5 w-5 text-muted-foreground" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-4">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-muted">
              <RefreshCw className="h-4 w-4 text-muted-foreground" />
            </div>
            <div>
              <CardTitle>Sync Status</CardTitle>
              <p className="text-sm text-muted-foreground mt-1">
                Recent synchronization activity
              </p>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 md:grid-cols-5">
            <SyncStatusItem
              label="Last Sync"
              date={getLatestSyncDate(syncStatus)}
            />
            {syncSources.map((group) => (
              <SyncStatusItem
                key={group.syncKey}
                label={group.name}
                date={getLastSyncForSource(syncStatus, group.syncKey)}
              />
            ))}
          </div>
        </CardContent>
      </Card>

      {sourceGroups.map((group) => {
        const groupRecords = group.items.reduce((s, i) => s + i.count, 0);
        if (
          groupRecords === 0 &&
          !getLastSyncForSource(syncStatus, group.syncKey)
        ) {
          return null;
        }

        return (
          <Card key={group.syncKey}>
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span
                    className={cn(
                      "text-xs font-bold px-2.5 py-1 rounded-full",
                      group.color,
                    )}
                  >
                    {group.name}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {groupRecords.toLocaleString()} records
                  </span>
                </div>
                <SyncTimestamp
                  date={getLastSyncForSource(syncStatus, group.syncKey)}
                />
              </div>
            </CardHeader>
            <CardContent>
              <div className="divide-y divide-border">
                {group.items.map((source) => {
                  const statusInfo = getStatusInfo(source);
                  const StatusIcon = statusInfo.icon;

                  return (
                    <div
                      key={`${group.syncKey}-${source.name}`}
                      className="flex items-center justify-between py-3 first:pt-0 last:pb-0"
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={cn("p-1.5 rounded-lg", statusInfo.bgClass)}
                        >
                          <StatusIcon
                            className={cn("h-3.5 w-3.5", statusInfo.colorClass)}
                          />
                        </div>
                        <div>
                          <p className="font-medium text-sm">{source.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {source.count > 0
                              ? `${source.count.toLocaleString()} records`
                              : "No data"}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        {source.latestDate ? (
                          <>
                            <p className="text-sm font-medium">
                              {format(
                                parseISO(source.latestDate),
                                "MMM d, yyyy",
                              )}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {statusInfo.label}
                            </p>
                          </>
                        ) : (
                          <p className="text-sm text-muted-foreground">-</p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

interface SyncStatusItemProps {
  readonly label: string;
  readonly date: string | null;
}

function SyncStatusItem({ label, date }: SyncStatusItemProps) {
  return (
    <div className="space-y-1">
      <p className="text-sm font-medium text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold">
        {date ? format(parseISO(date), "PPp") : "Never"}
      </p>
    </div>
  );
}

function SyncTimestamp({ date }: { readonly date: string | null }) {
  if (!date) return null;
  return (
    <p className="text-xs text-muted-foreground">
      Last sync: {format(parseISO(date), "MMM d, h:mm a")}
    </p>
  );
}
