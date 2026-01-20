import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { api } from "../lib/api";
import { format, subDays, differenceInDays, parseISO } from "date-fns";
import { healthKeys, settingsKeys } from "../lib/query-keys";
import {
  HEALTH_DATA_STALE_TIME,
  SYNC_REFETCH_INTERVAL,
  DEFAULT_SYNC_DAYS,
} from "../lib/constants";
import type { SyncStatus, CredentialsStatus } from "../types/api";

export function useHealthData(
  days: number = 90,
  excludeToday: boolean = false,
) {
  const today = new Date();
  const endDate = excludeToday
    ? format(subDays(today, 1), "yyyy-MM-dd")
    : format(today, "yyyy-MM-dd");
  const startDate = format(subDays(today, days), "yyyy-MM-dd");

  return useQuery({
    queryKey: healthKeys.dataRange(startDate, endDate),
    queryFn: () => api.data.getRange(startDate, endDate),
    staleTime: HEALTH_DATA_STALE_TIME,
    refetchInterval: SYNC_REFETCH_INTERVAL,
    refetchOnWindowFocus: true,
  });
}

export function useHealthDataRange(startDate: string, endDate: string) {
  return useQuery({
    queryKey: healthKeys.dataRange(startDate, endDate),
    queryFn: () => api.data.getRange(startDate, endDate),
    staleTime: HEALTH_DATA_STALE_TIME,
    refetchInterval: SYNC_REFETCH_INTERVAL,
    refetchOnWindowFocus: true,
  });
}

export function useSyncStatus() {
  return useQuery({
    queryKey: healthKeys.syncStatus(),
    queryFn: api.sync.getStatus,
    refetchInterval: SYNC_REFETCH_INTERVAL,
  });
}

type SyncSource = "garmin" | "hevy" | "whoop";

function getDaysSinceLastSync(
  syncStatuses: SyncStatus[] | undefined,
  source: SyncSource,
): number {
  const sourceSync = syncStatuses?.find(
    (s) => s.source === source && s.data_type === "all",
  );

  if (!sourceSync?.last_sync_date) {
    return DEFAULT_SYNC_DAYS;
  }

  const lastSyncDate = parseISO(sourceSync.last_sync_date);
  const today = new Date();
  const days = differenceInDays(today, lastSyncDate) + 1;
  return Math.max(1, Math.min(days, DEFAULT_SYNC_DAYS));
}

function isSyncInProgress(
  syncStatuses: SyncStatus[] | undefined,
  source: SyncSource,
): boolean {
  if (!syncStatuses) return false;
  return syncStatuses.some(
    (s) => s.source === source && s.status === "in_progress",
  );
}

function getCredentialsFingerprint(
  credentials: CredentialsStatus | undefined,
): string | null {
  if (!credentials) return null;
  return `${String(credentials.garmin_configured)}-${String(credentials.hevy_configured)}-${String(credentials.whoop_configured)}`;
}

export function useAutoSync() {
  const queryClient = useQueryClient();
  const [syncingProviders, setSyncingProviders] = useState<Set<SyncSource>>(
    new Set(),
  );
  const hasTriggeredRef = useRef(false);
  const syncInFlightRef = useRef<Set<SyncSource>>(new Set());
  const prevCredentialsFingerprintRef = useRef<string | null>(null);

  const { data: syncStatus } = useSyncStatus();
  const { data: credentials } = useQuery({
    queryKey: settingsKeys.credentials(),
    queryFn: api.settings.getCredentials,
  });

  const credentialsFingerprint = useMemo(
    () => getCredentialsFingerprint(credentials),
    [credentials],
  );

  useEffect(() => {
    if (
      credentialsFingerprint &&
      prevCredentialsFingerprintRef.current !== null &&
      prevCredentialsFingerprintRef.current !== credentialsFingerprint
    ) {
      hasTriggeredRef.current = false;
    }
    prevCredentialsFingerprintRef.current = credentialsFingerprint;
  }, [credentialsFingerprint]);

  const triggerSync = useCallback(
    async (source: SyncSource, days: number) => {
      if (syncInFlightRef.current.has(source)) return;
      syncInFlightRef.current.add(source);
      setSyncingProviders((prev) => new Set(prev).add(source));

      const syncEndDate = format(new Date(), "yyyy-MM-dd");
      const syncStartDate = format(subDays(new Date(), days), "yyyy-MM-dd");

      try {
        const syncFnMap = {
          garmin: api.sync.garmin,
          hevy: api.sync.hevy,
          whoop: api.sync.whoop,
        } as const;
        const syncFn = syncFnMap[source];

        await syncFn(days);
        void queryClient.invalidateQueries({
          queryKey: healthKeys.syncStatus(),
        });
      } catch (error) {
        console.error(`Auto-sync failed for ${source}:`, error);
      } finally {
        syncInFlightRef.current.delete(source);
        setSyncingProviders((prev) => {
          const next = new Set(prev);
          next.delete(source);
          return next;
        });
        void queryClient.invalidateQueries({
          predicate: (query) => {
            const key = query.queryKey;
            if (key[0] !== "health" || key[1] !== "data") return false;
            if (key.length < 4) return true;
            const [, , queryStart, queryEnd] = key as [
              string,
              string,
              string,
              string,
            ];
            return queryStart <= syncEndDate && queryEnd >= syncStartDate;
          },
        });
      }
    },
    [queryClient],
  );

  useEffect(() => {
    if (hasTriggeredRef.current || !credentials || !syncStatus) return;

    hasTriggeredRef.current = true;

    if (
      credentials.garmin_configured &&
      !isSyncInProgress(syncStatus, "garmin")
    ) {
      const days = getDaysSinceLastSync(syncStatus, "garmin");
      void triggerSync("garmin", days);
    }

    if (credentials.hevy_configured && !isSyncInProgress(syncStatus, "hevy")) {
      const days = getDaysSinceLastSync(syncStatus, "hevy");
      void triggerSync("hevy", days);
    }

    if (
      credentials.whoop_configured &&
      !isSyncInProgress(syncStatus, "whoop")
    ) {
      const days = getDaysSinceLastSync(syncStatus, "whoop");
      void triggerSync("whoop", days);
    }
  }, [credentials, syncStatus, triggerSync]);

  const isSyncing =
    syncingProviders.size > 0 ||
    (syncStatus?.some((s) => s.status === "in_progress") ?? false);

  return { isSyncing, syncingProviders: Array.from(syncingProviders) };
}
