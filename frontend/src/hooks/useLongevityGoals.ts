import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { longevityKeys } from "../lib/query-keys";

export function useLongevityGoals() {
  return useQuery({
    queryKey: longevityKeys.goals(),
    queryFn: () => api.longevity.getGoals(),
  });
}

export function useCreateLongevityGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.longevity.createGoal,
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: longevityKeys.goals() })
        .catch(() => {});
    },
  });
}

export function useUpdateLongevityGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
      data: Parameters<typeof api.longevity.updateGoal>[1];
    }) => api.longevity.updateGoal(id, data),
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: longevityKeys.goals() })
        .catch(() => {});
    },
  });
}

export function useDeleteLongevityGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.longevity.deleteGoal(id),
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: longevityKeys.goals() })
        .catch(() => {});
    },
  });
}
