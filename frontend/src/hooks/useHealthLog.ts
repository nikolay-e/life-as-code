import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { longevityKeys } from "../lib/query-keys";

export function useInterventions() {
  return useQuery({
    queryKey: longevityKeys.interventions(),
    queryFn: () => api.longevity.getInterventions(),
  });
}

export function useCreateIntervention() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: api.longevity.createIntervention,
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: longevityKeys.interventions() })
        .catch(() => {});
    },
  });
}

export function useUpdateIntervention() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
      data: Parameters<typeof api.longevity.updateIntervention>[1];
    }) => api.longevity.updateIntervention(id, data),
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: longevityKeys.interventions() })
        .catch(() => {});
    },
  });
}

export function useDeleteIntervention() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => api.longevity.deleteIntervention(id),
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: longevityKeys.interventions() })
        .catch(() => {});
    },
  });
}

export function useBiomarkers() {
  return useQuery({
    queryKey: longevityKeys.biomarkers(),
    queryFn: () => api.longevity.getBiomarkers(),
  });
}

export function useCreateBiomarker() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: api.longevity.createBiomarker,
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: longevityKeys.biomarkers() })
        .catch(() => {});
    },
  });
}

export function useDeleteBiomarker() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => api.longevity.deleteBiomarker(id),
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: longevityKeys.biomarkers() })
        .catch(() => {});
    },
  });
}
