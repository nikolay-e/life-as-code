import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { longevityKeys } from "../lib/query-keys";

export function useFunctionalTests(testName?: string) {
  return useQuery({
    queryKey: [...longevityKeys.functionalTests(), testName ?? "all"],
    queryFn: () => api.longevity.getFunctionalTests(testName),
  });
}

export function useCreateFunctionalTest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.longevity.createFunctionalTest,
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: longevityKeys.functionalTests() })
        .catch(() => {});
    },
  });
}

export function useDeleteFunctionalTest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.longevity.deleteFunctionalTest(id),
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: longevityKeys.functionalTests() })
        .catch(() => {});
    },
  });
}
