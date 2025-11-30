import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { HealthData } from "@/types/health";

interface DateRange {
  startDate: string;
  endDate: string;
}

async function fetchHealthData({
  startDate,
  endDate,
}: DateRange): Promise<HealthData> {
  const response = await api.get(
    `/api/data/range?start_date=${startDate}&end_date=${endDate}`,
  );
  if (!response.ok) {
    throw new Error("Failed to fetch health data");
  }
  return response.json();
}

export function useHealthData(dateRange: DateRange) {
  return useQuery({
    queryKey: ["healthData", dateRange.startDate, dateRange.endDate],
    queryFn: () => fetchHealthData(dateRange),
    staleTime: 5 * 60 * 1000,
  });
}
