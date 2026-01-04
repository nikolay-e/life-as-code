import type { SyncStatus } from "../types/api";

export function getLatestSyncDate(
  syncs: SyncStatus[] | undefined,
): string | null {
  if (!syncs) return null;
  const withDates = syncs.filter(
    (s): s is SyncStatus & { last_sync_date: string } =>
      s.last_sync_date !== null,
  );
  if (withDates.length === 0) return null;
  const latest = withDates.sort(
    (a, b) =>
      new Date(b.last_sync_date).getTime() -
      new Date(a.last_sync_date).getTime(),
  )[0];
  return latest.last_sync_date;
}

export function getLastSyncForSource(
  syncs: SyncStatus[] | undefined,
  source: string,
): string | null {
  if (!syncs) return null;
  const sourceSyncs = syncs.filter(
    (s): s is SyncStatus & { last_sync_date: string } =>
      s.source === source && s.last_sync_date !== null,
  );
  if (sourceSyncs.length === 0) return null;
  const latest = sourceSyncs.sort(
    (a, b) =>
      new Date(b.last_sync_date).getTime() -
      new Date(a.last_sync_date).getTime(),
  )[0];
  return latest.last_sync_date;
}
