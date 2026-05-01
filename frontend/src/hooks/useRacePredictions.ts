import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { healthKeys } from "../lib/query-keys";
import { getLocalDateString, getLocalToday } from "../lib/health";

export function useRacePredictions(days: number = 365) {
  const end = getLocalToday();
  const start = new Date(end);
  start.setDate(end.getDate() - days);
  const startStr = getLocalDateString(start);
  const endStr = getLocalDateString(end);

  return useQuery({
    queryKey: healthKeys.racePredictions(startStr, endStr),
    queryFn: () => api.data.getRacePredictions(startStr, endStr),
  });
}
