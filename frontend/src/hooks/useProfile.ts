import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { settingsKeys } from "../lib/query-keys";

export function useProfile() {
  return useQuery({
    queryKey: settingsKeys.profile(),
    queryFn: () => api.settings.getProfile(),
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.settings.updateProfile,
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: settingsKeys.profile() })
        .catch(() => {});
    },
  });
}
