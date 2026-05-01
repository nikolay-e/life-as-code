import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { clinicalAlertsKeys } from "../lib/query-keys";
import type { ClinicalAlertStatus } from "../types/api";

export function useClinicalAlerts(status?: string) {
  return useQuery({
    queryKey: clinicalAlertsKeys.list(status),
    queryFn: () => api.clinicalAlerts.list(status),
  });
}

export function useUpdateClinicalAlertStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: ClinicalAlertStatus }) =>
      api.clinicalAlerts.updateStatus(id, status),
    onSuccess: () => {
      queryClient
        .invalidateQueries({ queryKey: clinicalAlertsKeys.all })
        .catch(() => {});
    },
  });
}
