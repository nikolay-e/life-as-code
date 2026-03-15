import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { api } from "../lib/api";
import { healthKeys } from "../lib/query-keys";
import { HEALTH_DATA_STALE_TIME } from "../lib/constants";

export function useAnalytics(mode: string = "recent") {
  return useQuery({
    queryKey: healthKeys.analytics(mode),
    queryFn: () => api.analytics.get(mode),
    staleTime: HEALTH_DATA_STALE_TIME,
    refetchOnWindowFocus: true,
    placeholderData: keepPreviousData,
  });
}
