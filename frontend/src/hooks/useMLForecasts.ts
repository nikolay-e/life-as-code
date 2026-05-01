import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { healthKeys } from "../lib/query-keys";

export function useMLForecasts(metric?: string, horizon: number = 14) {
  return useQuery({
    queryKey: healthKeys.mlForecasts(metric, horizon),
    queryFn: () => api.ml.getForecasts(metric, horizon),
  });
}
