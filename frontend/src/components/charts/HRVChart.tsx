import { memo } from "react";
import type { HRVData, WhoopRecoveryData } from "../../types/api";
import { MULTI_PROVIDER_CONFIGS } from "./chart-config";
import { MultiProviderLineChart } from "./MultiProviderLineChart";
import { mergeProviderData } from "../../lib/chart-utils";

interface HRVChartProps {
  garminData: HRVData[];
  whoopData?: WhoopRecoveryData[];
}

export const HRVChart = memo(function HRVChart({
  garminData,
  whoopData = [],
}: HRVChartProps) {
  const config = MULTI_PROVIDER_CONFIGS.hrv;

  const mergedData = mergeProviderData(
    garminData,
    whoopData,
    (d) => d.hrv_avg,
    (d) => d.hrv_rmssd,
  );

  return (
    <MultiProviderLineChart
      data={mergedData}
      config={config}
      emptyMessage="No HRV data available"
      garminLabel="Garmin HRV"
      whoopLabel="Whoop HRV"
      unit="ms"
    />
  );
});
