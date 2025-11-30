import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { UserSettings, UserCredentials, SyncStatus } from "@/types/health";

async function fetchSettings(): Promise<UserSettings> {
  const response = await api.get("/api/settings/thresholds");
  if (!response.ok) throw new Error("Failed to fetch settings");
  return response.json();
}

async function saveSettings(
  settings: Partial<UserSettings>,
): Promise<UserSettings> {
  const response = await api.put("/api/settings/thresholds", settings);
  if (!response.ok) throw new Error("Failed to save settings");
  return response.json();
}

async function fetchCredentials(): Promise<UserCredentials> {
  const response = await api.get("/api/settings/credentials");
  if (!response.ok) throw new Error("Failed to fetch credentials");
  return response.json();
}

async function saveCredentials(credentials: {
  garmin_email?: string;
  garmin_password?: string;
  hevy_api_key?: string;
}): Promise<void> {
  const response = await api.put("/api/settings/credentials", credentials);
  if (!response.ok) throw new Error("Failed to save credentials");
}

async function fetchSyncStatus(): Promise<SyncStatus[]> {
  const response = await api.get("/api/sync/status");
  if (!response.ok) throw new Error("Failed to fetch sync status");
  return response.json();
}

async function triggerSync(
  source: "garmin" | "heavy",
): Promise<{ message: string }> {
  const response = await api.post(`/api/sync/${source}`);
  if (!response.ok) throw new Error(`Failed to sync ${source}`);
  return response.json();
}

export function useSettings() {
  return useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
  });
}

export function useSaveSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: saveSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });
}

export function useCredentials() {
  return useQuery({
    queryKey: ["credentials"],
    queryFn: fetchCredentials,
  });
}

export function useSaveCredentials() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: saveCredentials,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["credentials"] });
    },
  });
}

export function useSyncStatus() {
  return useQuery({
    queryKey: ["syncStatus"],
    queryFn: fetchSyncStatus,
    refetchInterval: 30000,
  });
}

export function useTriggerSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: triggerSync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["syncStatus"] });
    },
  });
}
