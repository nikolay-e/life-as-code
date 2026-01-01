import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, useCallback } from "react";
import { api } from "../lib/api";
import { format, subDays, differenceInDays, parseISO } from "date-fns";
import { healthKeys, settingsKeys } from "../lib/query-keys";
import {
  HEALTH_DATA_STALE_TIME,
  SYNC_REFETCH_INTERVAL,
} from "../lib/constants";
import type { SyncStatus } from "../types/api";

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
    return 90;
  }

  const lastSyncDate = parseISO(sourceSync.last_sync_date);
  const today = new Date();
  const days = differenceInDays(today, lastSyncDate) + 1;
  return Math.max(1, Math.min(days, 90));
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

export function useAutoSync() {
  const queryClient = useQueryClient();
  const [syncingProviders, setSyncingProviders] = useState<Set<SyncSource>>(
    new Set(),
  );
  const hasTriggeredRef = useRef(false);

  const { data: syncStatus } = useSyncStatus();
  const { data: credentials } = useQuery({
    queryKey: settingsKeys.credentials(),
    queryFn: api.settings.getCredentials,
  });

  const triggerSync = useCallback(
    async (source: SyncSource, days: number) => {
      setSyncingProviders((prev) => new Set(prev).add(source));

      try {
        const syncFn =
          source === "garmin"
            ? api.sync.garmin
            : source === "hevy"
              ? api.sync.hevy
              : api.sync.whoop;

        await syncFn(days);
        queryClient.invalidateQueries({ queryKey: healthKeys.syncStatus() });
      } catch {
        // Sync errors are handled by the backend
      } finally {
        setSyncingProviders((prev) => {
          const next = new Set(prev);
          next.delete(source);
          return next;
        });
        queryClient.invalidateQueries({ queryKey: healthKeys.data() });
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
      triggerSync("garmin", days);
    }

    if (credentials.hevy_configured && !isSyncInProgress(syncStatus, "hevy")) {
      const days = getDaysSinceLastSync(syncStatus, "hevy");
      triggerSync("hevy", days);
    }

    if (
      credentials.whoop_configured &&
      !isSyncInProgress(syncStatus, "whoop")
    ) {
      const days = getDaysSinceLastSync(syncStatus, "whoop");
      triggerSync("whoop", days);
    }
  }, [credentials, syncStatus, triggerSync]);

  const isSyncing =
    syncingProviders.size > 0 ||
    (syncStatus?.some((s) => s.status === "in_progress") ?? false);

  return { isSyncing, syncingProviders: Array.from(syncingProviders) };
}
