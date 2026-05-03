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

export function useHealthEvents(days?: number) {
  return useQuery({
    queryKey: longevityKeys.events(),
    queryFn: () => api.longevity.getHealthEvents(days),
  });
}

export function useCreateHealthEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.longevity.createHealthEvent,
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: longevityKeys.events() })
        .catch(() => {});
      queryClient
        .invalidateQueries({ queryKey: longevityKeys.interventions() })
        .catch(() => {});
    },
  });
}

export function useDeleteHealthEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.longevity.deleteHealthEvent(id),
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: longevityKeys.events() })
        .catch(() => {});
    },
  });
}

export function useProtocols(activeOnly?: boolean) {
  return useQuery({
    queryKey: longevityKeys.protocols(),
    queryFn: () => api.longevity.getProtocols(activeOnly),
  });
}

export function useCreateProtocol() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.longevity.createProtocol,
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: longevityKeys.protocols() })
        .catch(() => {});
    },
  });
}

export function useUpdateProtocol() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
      data: Parameters<typeof api.longevity.updateProtocol>[1];
    }) => api.longevity.updateProtocol(id, data),
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: longevityKeys.protocols() })
        .catch(() => {});
    },
  });
}

export function useDeleteProtocol() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.longevity.deleteProtocol(id),
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: longevityKeys.protocols() })
        .catch(() => {});
    },
  });
}

export function useHealthNotes(days?: number) {
  return useQuery({
    queryKey: longevityKeys.notes(),
    queryFn: () => api.longevity.getHealthNotes(days),
  });
}

export function useCreateHealthNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.longevity.createHealthNote,
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: longevityKeys.notes() })
        .catch(() => {});
    },
  });
}

export function useDeleteHealthNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.longevity.deleteHealthNote(id),
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: longevityKeys.notes() })
        .catch(() => {});
    },
  });
}

export function useUnifiedLog(days?: number) {
  return useQuery({
    queryKey: longevityKeys.unifiedLog(days),
    queryFn: () => api.longevity.getUnifiedLog(days),
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
