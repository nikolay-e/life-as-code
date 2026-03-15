import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { api } from "../lib/api";
import { healthKeys } from "../lib/query-keys";
import { HEALTH_DATA_STALE_TIME } from "../lib/constants";
import type { AnalyticsResponse } from "../types/api";

export function useAnalytics(mode: string = "recent") {
  return useQuery<AnalyticsResponse>({
    queryKey: healthKeys.analytics(mode),
    queryFn: () => api.analytics.get(mode),
    staleTime: HEALTH_DATA_STALE_TIME,
    refetchOnWindowFocus: true,
    placeholderData: keepPreviousData,
  });
}
