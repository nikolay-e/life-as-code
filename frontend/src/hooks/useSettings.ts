import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { UserThresholds, SyncResponse } from "../types/api";
import { healthKeys, settingsKeys } from "../lib/query-keys";

export function useThresholds() {
  return useQuery({
    queryKey: settingsKeys.thresholds(),
    queryFn: api.settings.getThresholds,
  });
}

export function useUpdateThresholds() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (thresholds: Partial<UserThresholds>) =>
      api.settings.updateThresholds(thresholds),
    onSuccess: () => {
      queryClient
        .invalidateQueries({
          queryKey: settingsKeys.thresholds(),
        })
        .catch(() => {});
    },
  });
}

export function useCredentials() {
  return useQuery({
    queryKey: settingsKeys.credentials(),
    queryFn: api.settings.getCredentials,
  });
}

function useSyncMutation(syncFn: () => Promise<SyncResponse>) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: syncFn,
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: healthKeys.data() })
        .catch(() => {});
      queryClient
        .invalidateQueries({ queryKey: healthKeys.syncStatus() })
        .catch(() => {});
    },
  });
}

export function useSyncGarmin() {
  return useSyncMutation(api.sync.garmin);
}

export function useSyncHevy() {
  return useSyncMutation(api.sync.hevy);
}

export function useSyncWhoop() {
  return useSyncMutation(api.sync.whoop);
}
