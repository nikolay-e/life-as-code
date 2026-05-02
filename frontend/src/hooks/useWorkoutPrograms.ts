import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { programKeys } from "../lib/query-keys";

export function useWorkoutPrograms() {
  return useQuery({
    queryKey: programKeys.list(),
    queryFn: () => api.programs.list(),
  });
}

export function useActiveWorkoutProgram() {
  return useQuery({
    queryKey: programKeys.active(),
    queryFn: () => api.programs.getActive(),
  });
}

export function useWorkoutProgram(id: number | null) {
  return useQuery({
    queryKey: programKeys.detail(id ?? -1),
    queryFn: () => api.programs.get(id as number),
    enabled: id !== null && id > 0,
  });
}

function invalidatePrograms(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: programKeys.all }).catch(() => {});
}

export function useCreateWorkoutProgram() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.programs.create,
    onSuccess: () => { invalidatePrograms(queryClient); },
  });
}

export function useUpdateWorkoutProgram() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
      data: Parameters<typeof api.programs.update>[1];
    }) => api.programs.update(id, data),
    onSuccess: () => { invalidatePrograms(queryClient); },
  });
}

export function useActivateWorkoutProgram() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.programs.activate(id),
    onSuccess: () => { invalidatePrograms(queryClient); },
  });
}

export function useArchiveWorkoutProgram() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.programs.archive(id),
    onSuccess: () => { invalidatePrograms(queryClient); },
  });
}

export function useDeleteWorkoutProgram() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.programs.delete(id),
    onSuccess: () => { invalidatePrograms(queryClient); },
  });
}

export function useExerciseTemplates(
  q: string,
  muscle: string,
  equipment: string,
) {
  return useQuery({
    queryKey: programKeys.templates(q, muscle, equipment),
    queryFn: () =>
      api.exerciseTemplates.list({
        q: q || undefined,
        muscle: muscle || undefined,
        equipment: equipment || undefined,
        limit: 200,
      }),
    staleTime: 60_000,
  });
}

export function useSyncExerciseTemplates() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.exerciseTemplates.sync(),
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: [...programKeys.all, "templates"] })
        .catch(() => {});
    },
  });
}
