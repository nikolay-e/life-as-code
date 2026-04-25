import { useHealthData, useSyncStatus } from "../../hooks/useHealthData";
import { LoadingState } from "../../components/ui/loading-state";
import { ErrorCard } from "../../components/ui/error-card";
import { format, parseISO, differenceInDays } from "date-fns";
import { cn } from "../../lib/utils";
import { getLatestSyncDate, getLastSyncForSource } from "../../lib/sync-utils";
import { Masthead } from "../../components/luxury/Masthead";
import { SectionHead, SerifEm } from "../../components/luxury/SectionHead";

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
  items: DataSourceStatus[];
}

type StatusTone = "ok" | "warn" | "off";

interface ProviderStatusInfo {
  tone: StatusTone;
  label: string;
}

const TONE_TEXT: Record<StatusTone, string> = {
  ok: "text-moss",
  warn: "text-brass",
  off: "text-muted-foreground",
};

const TONE_DOT: Record<StatusTone, string> = {
  ok: "bg-moss",
  warn: "bg-brass",
  off: "bg-muted-foreground",
};

const TONE_RING: Record<StatusTone, string> = {
  ok: "ring-moss/20",
  warn: "ring-brass/20",
  off: "ring-muted-foreground/15",
};

const PROVIDER_TITLE: Record<string, string> = {
  garmin: "Garmin Connect",
  whoop: "Whoop",
  hevy: "Hevy",
  eight_sleep: "Eight Sleep",
};

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
      items: [
        getDataSourceStatus(data?.workouts, "Workouts", "Hevy", "sporadic"),
      ],
    },
    {
      name: "Eight Sleep",
      syncKey: "eight_sleep",
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

  const getStatusInfo = (
    status: DataSourceStatus,
  ): ProviderStatusInfo & { detailLabel: string } => {
    if (status.count === 0) {
      return { tone: "off", label: "Idle", detailLabel: "No data" };
    }
    if (!status.latestDate) {
      return { tone: "warn", label: "Stale", detailLabel: "Stale" };
    }

    const daysSinceUpdate = differenceInDays(
      new Date(),
      parseISO(status.latestDate),
    );

    if (daysSinceUpdate <= 1) {
      return { tone: "ok", label: "Live", detailLabel: "Up to date" };
    }
    if (daysSinceUpdate <= 7) {
      return {
        tone: "warn",
        label: "Lag",
        detailLabel: `${String(daysSinceUpdate)}d ago`,
      };
    }
    if (status.cadence === "sporadic" && isSporadicRecentlySynced(status)) {
      return {
        tone: "warn",
        label: "Quiet",
        detailLabel: `No new data · ${String(daysSinceUpdate)}d ago`,
      };
    }
    if (status.cadence === "sporadic" && daysSinceUpdate <= 30) {
      return {
        tone: "warn",
        label: "Lag",
        detailLabel: `${String(daysSinceUpdate)}d ago`,
      };
    }
    return { tone: "off", label: "Stale", detailLabel: "Stale" };
  };

  const getProviderStatus = (group: SourceGroup): ProviderStatusInfo => {
    const activeItems = group.items.filter((i) => i.count > 0);
    if (activeItems.length === 0) {
      return { tone: "off", label: "Idle" };
    }
    const itemTones = activeItems.map((i) => getStatusInfo(i).tone);
    if (itemTones.every((t) => t === "ok")) {
      return { tone: "ok", label: "Live" };
    }
    if (itemTones.some((t) => t === "off")) {
      return { tone: "warn", label: "Partial" };
    }
    return { tone: "warn", label: "Lag" };
  };

  const getProviderDomains = (group: SourceGroup): string => {
    const active = group.items.filter((i) => i.count > 0);
    const names = (active.length > 0 ? active : group.items).map((i) => i.name);
    return names.join(" · ");
  };

  const totalRecords = allSources.reduce((sum, ds) => sum + ds.count, 0);
  const activeSources = allSources.filter((ds) => ds.count > 0).length;
  const latestSyncDate = getLatestSyncDate(syncStatus);
  const todayDate = new Date();
  const dateLine = format(todayDate, "d LLLL yyyy");

  const visibleGroups = sourceGroups.filter(
    (g) =>
      g.items.some((i) => i.count > 0) ||
      getLastSyncForSource(syncStatus, g.syncKey) != null,
  );

  return (
    <div className="space-y-0">
      <Masthead
        leftLine="Section · Data"
        title={
          <>
            The <SerifEm>pipeline</SerifEm>
          </>
        }
        rightLine={
          <>
            {dateLine}
            <br />
            {totalRecords.toLocaleString()} records · {activeSources}/
            {String(allSources.length)} sources
          </>
        }
      />

      <section className="pt-12">
        <SectionHead
          title={
            <>
              Connected <SerifEm>sources</SerifEm>
            </>
          }
          meta="freshness window 24h"
        />

        <div className="border-t border-border">
          {visibleGroups.map((group) => {
            const groupRecords = group.items.reduce((s, i) => s + i.count, 0);
            const lastSync = getLastSyncForSource(syncStatus, group.syncKey);
            const providerStatus = getProviderStatus(group);
            const title = PROVIDER_TITLE[group.syncKey] ?? group.name;
            const domains = getProviderDomains(group);

            return (
              <div
                key={group.syncKey}
                className="grid grid-cols-1 md:grid-cols-[200px_1fr_auto] gap-4 md:gap-8 items-start md:items-center py-7 border-b border-border"
              >
                <span
                  className="font-serif italic text-[24px] leading-none"
                  style={{
                    fontVariationSettings: '"opsz" 144, "SOFT" 100',
                    fontWeight: 400,
                  }}
                >
                  {title}
                </span>
                <div className="type-mono-label text-muted-foreground space-y-1.5">
                  <div>
                    <strong className="text-foreground font-medium">
                      Last sync
                    </strong>{" "}
                    ·{" "}
                    {lastSync
                      ? format(parseISO(lastSync), "d LLL HH:mm").toLowerCase()
                      : "never"}
                    {" · "}
                    {groupRecords.toLocaleString()} records
                  </div>
                  <div>{domains}</div>
                </div>
                <ProviderStatusBadge
                  tone={providerStatus.tone}
                  label={providerStatus.label}
                />
              </div>
            );
          })}
        </div>
      </section>

      <section className="pt-14">
        <SectionHead
          title={
            <>
              Pipeline <SerifEm>vitals</SerifEm>
            </>
          }
          meta="aggregate state"
        />
        <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-border border-y border-border">
          <FieldCell
            label="Records, total"
            value={totalRecords.toLocaleString()}
            mono
          />
          <FieldCell
            label="Active sources"
            value={`${String(activeSources)} / ${String(allSources.length)}`}
            mono
          />
          <FieldCell
            label="Last sync"
            value={
              latestSyncDate
                ? format(
                    parseISO(latestSyncDate),
                    "d LLL · HH:mm",
                  ).toLowerCase()
                : "never"
            }
            mono
          />
        </div>
      </section>

      <section className="pt-14">
        <SectionHead
          title={
            <>
              Synchronisation <SerifEm>cadence</SerifEm>
            </>
          }
          meta="last touch per provider"
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-border border-y border-border lg:[&>*:nth-child(3)]:border-l">
          {sourceGroups
            .filter((g) => g.items.some((i) => i.count > 0))
            .map((group) => {
              const lastSync = getLastSyncForSource(syncStatus, group.syncKey);
              return (
                <FieldCell
                  key={group.syncKey}
                  label={PROVIDER_TITLE[group.syncKey] ?? group.name}
                  value={
                    lastSync
                      ? format(
                          parseISO(lastSync),
                          "d LLL · HH:mm",
                        ).toLowerCase()
                      : "never"
                  }
                  mono
                />
              );
            })}
        </div>
      </section>

      {sourceGroups.map((group) => {
        const groupRecords = group.items.reduce((s, i) => s + i.count, 0);
        if (
          groupRecords === 0 &&
          !getLastSyncForSource(syncStatus, group.syncKey)
        ) {
          return null;
        }
        const lastSync = getLastSyncForSource(syncStatus, group.syncKey);
        const title = PROVIDER_TITLE[group.syncKey] ?? group.name;

        return (
          <section key={group.syncKey} className="pt-14">
            <SectionHead
              title={
                <>
                  {title.split(" ")[0]}{" "}
                  <SerifEm>
                    {title.split(" ").slice(1).join(" ") || "stream"}
                  </SerifEm>
                </>
              }
              meta={
                <>
                  {groupRecords.toLocaleString()} records
                  {lastSync && (
                    <>
                      <br />
                      last sync ·{" "}
                      {format(parseISO(lastSync), "d LLL HH:mm").toLowerCase()}
                    </>
                  )}
                </>
              }
            />
            <div className="border-t border-border">
              {group.items.map((source) => {
                const statusInfo = getStatusInfo(source);
                return (
                  <div
                    key={`${group.syncKey}-${source.name}`}
                    className="grid grid-cols-1 md:grid-cols-[200px_1fr_auto] gap-4 md:gap-8 items-start md:items-center py-5 border-b border-border"
                  >
                    <span
                      className="font-serif italic text-[20px] leading-none"
                      style={{
                        fontVariationSettings: '"opsz" 144, "SOFT" 100',
                        fontWeight: 400,
                      }}
                    >
                      {source.name}
                    </span>
                    <div className="type-mono-label text-muted-foreground space-y-1">
                      <div>
                        <strong className="text-foreground font-medium">
                          {source.count > 0
                            ? source.count.toLocaleString()
                            : "0"}{" "}
                          records
                        </strong>
                        {source.latestDate && (
                          <>
                            {" · latest "}
                            {format(
                              parseISO(source.latestDate),
                              "d LLL yyyy",
                            ).toLowerCase()}
                          </>
                        )}
                      </div>
                      {source.oldestDate && source.count > 0 && (
                        <div>
                          since{" "}
                          {format(
                            parseISO(source.oldestDate),
                            "d LLL yyyy",
                          ).toLowerCase()}
                          {" · "}
                          {source.cadence === "sporadic"
                            ? "sporadic cadence"
                            : "daily cadence"}
                        </div>
                      )}
                    </div>
                    <ProviderStatusBadge
                      tone={statusInfo.tone}
                      label={statusInfo.detailLabel}
                    />
                  </div>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}

interface ProviderStatusBadgeProps {
  readonly tone: StatusTone;
  readonly label: string;
}

function ProviderStatusBadge({ tone, label }: ProviderStatusBadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-2.5 type-mono-label",
        TONE_TEXT[tone],
      )}
    >
      <span className="relative inline-flex items-center justify-center">
        <span
          className={cn(
            "w-1.5 h-1.5 rounded-full ring-4",
            TONE_DOT[tone],
            TONE_RING[tone],
          )}
        />
        {tone === "ok" && (
          <span
            className={cn(
              "absolute inline-flex w-1.5 h-1.5 rounded-full opacity-60 animate-ping",
              TONE_DOT[tone],
            )}
          />
        )}
      </span>
      <span className="uppercase">{label}</span>
    </div>
  );
}

interface FieldCellProps {
  readonly label: string;
  readonly value: string;
  readonly mono?: boolean;
}

function FieldCell({ label, value, mono = false }: FieldCellProps) {
  return (
    <div className="px-0 sm:px-6 py-5 first:pl-0 last:pr-0">
      <div className="type-mono-label text-muted-foreground mb-2">{label}</div>
      <div
        className={cn(
          mono
            ? "font-mono text-[14px] tracking-[0.02em] text-foreground"
            : "font-serif text-[19px] text-foreground",
        )}
        style={
          mono
            ? undefined
            : {
                fontVariationSettings: '"opsz" 14, "SOFT" 40',
                fontWeight: 400,
              }
        }
      >
        {value}
      </div>
    </div>
  );
}
