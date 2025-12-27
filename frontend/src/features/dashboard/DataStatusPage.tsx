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
import type { SyncStatus } from "../../types/api";
import { cn } from "../../lib/utils";

interface DataSourceStatus {
  name: string;
  provider: string;
  count: number;
  latestDate: string | null;
  oldestDate: string | null;
}

function getLastSyncForSource(
  syncs: SyncStatus[] | undefined,
  source: string,
): string | null {
  if (!syncs) return null;
  const sourceSyncs = syncs.filter(
    (s) => s.source === source && s.last_sync_date,
  );
  if (sourceSyncs.length === 0) return null;
  const latest = sourceSyncs.sort(
    (a, b) =>
      new Date(b.last_sync_date!).getTime() -
      new Date(a.last_sync_date!).getTime(),
  )[0];
  return latest.last_sync_date;
}

function getOverallLastSync(syncs: SyncStatus[] | undefined): string | null {
  if (!syncs) return null;
  const withDates = syncs.filter((s) => s.last_sync_date);
  if (withDates.length === 0) return null;
  const latest = withDates.sort(
    (a, b) =>
      new Date(b.last_sync_date!).getTime() -
      new Date(a.last_sync_date!).getTime(),
  )[0];
  return latest.last_sync_date;
}

export function DataStatusPage() {
  const { data, isLoading, error } = useHealthData(365);
  const { data: syncStatus, isLoading: syncLoading } = useSyncStatus();

  if (isLoading || syncLoading) {
    return <LoadingState message="Loading data status..." />;
  }

  if (error) {
    return (
      <ErrorCard message={`Failed to load data status: ${error.message}`} />
    );
  }

  const getDataSourceStatus = (
    items: Array<{ date: string }> | undefined,
    name: string,
    provider: string,
  ): DataSourceStatus => {
    if (!items || items.length === 0) {
      return { name, provider, count: 0, latestDate: null, oldestDate: null };
    }
    const sorted = [...items].sort(
      (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime(),
    );
    return {
      name,
      provider,
      count: items.length,
      latestDate: sorted[0].date,
      oldestDate: sorted[sorted.length - 1].date,
    };
  };

  const dataSources: DataSourceStatus[] = [
    getDataSourceStatus(data?.sleep, "Sleep", "Garmin"),
    getDataSourceStatus(data?.hrv, "HRV", "Garmin"),
    getDataSourceStatus(data?.weight, "Weight", "Garmin"),
    getDataSourceStatus(data?.heart_rate, "Heart Rate", "Garmin"),
    getDataSourceStatus(data?.stress, "Stress", "Garmin"),
    getDataSourceStatus(data?.steps, "Steps", "Garmin"),
    getDataSourceStatus(
      data?.garmin_training_status,
      "Training Status",
      "Garmin",
    ),
    getDataSourceStatus(data?.workouts, "Workouts", "Hevy"),
    getDataSourceStatus(data?.whoop_recovery, "Whoop Recovery", "Whoop"),
    getDataSourceStatus(data?.whoop_sleep, "Whoop Sleep", "Whoop"),
    getDataSourceStatus(data?.whoop_workout, "Whoop Workouts", "Whoop"),
    getDataSourceStatus(data?.whoop_cycle, "Whoop Cycles", "Whoop"),
  ];

  const getStatusInfo = (status: DataSourceStatus) => {
    if (status.count === 0) {
      return {
        icon: AlertCircle,
        colorClass: "text-muted-foreground",
        bgClass: "bg-muted",
        label: "No data",
      };
    }
    if (status.latestDate) {
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
          label: `${daysSinceUpdate}d ago`,
        };
      }
    }
    return {
      icon: AlertCircle,
      colorClass: "text-destructive",
      bgClass: "bg-destructive/10",
      label: "Stale",
    };
  };

  const totalRecords = dataSources.reduce((sum, ds) => sum + ds.count, 0);
  const activeSources = dataSources.filter((ds) => ds.count > 0).length;

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
                    /{dataSources.length}
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
                  const lastSync = syncStatus
                    ?.filter((s) => s.last_sync_date)
                    .sort(
                      (a, b) =>
                        new Date(b.last_sync_date!).getTime() -
                        new Date(a.last_sync_date!).getTime(),
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
          <div className="grid gap-6 sm:grid-cols-4">
            <SyncStatusItem
              label="Last Sync"
              date={getOverallLastSync(syncStatus)}
            />
            <SyncStatusItem
              label="Garmin"
              date={getLastSyncForSource(syncStatus, "garmin")}
            />
            <SyncStatusItem
              label="Hevy"
              date={getLastSyncForSource(syncStatus, "hevy")}
            />
            <SyncStatusItem
              label="Whoop"
              date={getLastSyncForSource(syncStatus, "whoop")}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-4">
          <CardTitle>Data Sources</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="divide-y divide-border">
            {dataSources.map((source) => {
              const statusInfo = getStatusInfo(source);
              const StatusIcon = statusInfo.icon;

              return (
                <div
                  key={source.name}
                  className="flex items-center justify-between py-4 first:pt-0 last:pb-0"
                >
                  <div className="flex items-center gap-4">
                    <div className={cn("p-2 rounded-lg", statusInfo.bgClass)}>
                      <StatusIcon
                        className={cn("h-4 w-4", statusInfo.colorClass)}
                      />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-medium">{source.name}</p>
                        <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                          {source.provider}
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {source.count > 0
                          ? `${source.count.toLocaleString()} records`
                          : "No data available"}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    {source.latestDate ? (
                      <>
                        <p className="text-sm font-medium">
                          {format(parseISO(source.latestDate), "MMM d, yyyy")}
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
    </div>
  );
}

interface SyncStatusItemProps {
  label: string;
  date: string | null;
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
