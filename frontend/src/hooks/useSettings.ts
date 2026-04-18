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

export function useUpdateGarminCredentials() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      api.settings.updateGarminCredentials(email, password),
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: settingsKeys.credentials() })
        .catch(() => {});
    },
  });
}

export function useUpdateHevyCredentials() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ apiKey }: { apiKey: string }) =>
      api.settings.updateHevyCredentials(apiKey),
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: settingsKeys.credentials() })
        .catch(() => {});
    },
  });
}

export function useDeleteGarminCredentials() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => api.settings.deleteGarminCredentials(),
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: settingsKeys.credentials() })
        .catch(() => {});
    },
  });
}

export function useDeleteHevyCredentials() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => api.settings.deleteHevyCredentials(),
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: settingsKeys.credentials() })
        .catch(() => {});
    },
  });
}

export function useTestGarminCredentials() {
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      api.settings.testGarminCredentials(email, password),
  });
}

export function useTestHevyCredentials() {
  return useMutation({
    mutationFn: ({ apiKey }: { apiKey: string }) =>
      api.settings.testHevyCredentials(apiKey),
  });
}

export function useUpdateEightSleepCredentials() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      api.settings.updateEightSleepCredentials(email, password),
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: settingsKeys.credentials() })
        .catch(() => {});
    },
  });
}

export function useDeleteEightSleepCredentials() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => api.settings.deleteEightSleepCredentials(),
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: settingsKeys.credentials() })
        .catch(() => {});
    },
  });
}

export function useTestEightSleepCredentials() {
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      api.settings.testEightSleepCredentials(email, password),
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
      queryClient
        .invalidateQueries({ queryKey: healthKeys.backoffStatus() })
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

export function useSyncEightSleep() {
  return useSyncMutation(api.sync.eightSleep);
}
