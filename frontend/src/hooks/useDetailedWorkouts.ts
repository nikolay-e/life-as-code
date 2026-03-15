import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { api } from "../lib/api";
import { format, subDays } from "date-fns";
import { healthKeys } from "../lib/query-keys";
import { HEALTH_DATA_STALE_TIME } from "../lib/constants";

export function useDetailedWorkouts(days: number = 90) {
  const today = new Date();
  const endDate = format(today, "yyyy-MM-dd");
  const startDate = format(subDays(today, days), "yyyy-MM-dd");

  return useQuery({
    queryKey: healthKeys.detailedWorkouts(startDate, endDate),
    queryFn: () => api.data.getDetailedWorkouts(startDate, endDate),
    staleTime: HEALTH_DATA_STALE_TIME,
    refetchOnWindowFocus: true,
    placeholderData: keepPreviousData,
  });
}
