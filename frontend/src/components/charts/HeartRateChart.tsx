import { memo } from "react";
import type { HeartRateData, WhoopRecoveryData } from "../../types/api";
import { MULTI_PROVIDER_CONFIGS } from "./chart-config";
import { MultiProviderLineChart } from "./MultiProviderLineChart";
import { mergeProviderData } from "../../lib/chart-utils";

interface HeartRateChartProps {
  garminData: HeartRateData[];
  whoopData?: WhoopRecoveryData[];
}

export const HeartRateChart = memo(function HeartRateChart({
  garminData,
  whoopData = [],
}: HeartRateChartProps) {
  const config = MULTI_PROVIDER_CONFIGS.restingHr;

  const mergedData = mergeProviderData(
    garminData,
    whoopData,
    (d) => d.resting_hr,
    (d) => d.resting_heart_rate,
  );

  return (
    <MultiProviderLineChart
      data={mergedData}
      config={config}
      emptyMessage="No heart rate data available"
      garminLabel="Garmin RHR"
      whoopLabel="Whoop RHR"
      unit="bpm"
      yDomain={["dataMin - 5", "dataMax + 5"]}
    />
  );
});
