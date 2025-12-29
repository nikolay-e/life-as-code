import { memo } from "react";
import type { GarminTrainingStatusData, WhoopCycleData } from "../../types/api";
import { MULTI_PROVIDER_CONFIGS } from "./chart-config";
import { MultiProviderLineChart } from "./MultiProviderLineChart";
import { mergeProviderData } from "../../lib/chart-utils";

interface CaloriesChartProps {
  garminData: GarminTrainingStatusData[];
  whoopData?: WhoopCycleData[];
  showTrends?: boolean;
}

export const CaloriesChart = memo(function CaloriesChart({
  garminData,
  whoopData = [],
  showTrends = false,
}: CaloriesChartProps) {
  const config = MULTI_PROVIDER_CONFIGS.calories;

  const mergedData = mergeProviderData(
    garminData,
    whoopData,
    (d) => d.total_kilocalories,
    (d) => (d.kilojoules !== null ? Math.round(d.kilojoules / 4.184) : null),
  );

  return (
    <MultiProviderLineChart
      data={mergedData}
      config={config}
      emptyMessage="No calories data available"
      garminLabel="Garmin"
      whoopLabel="Whoop"
      unit="kcal"
      yDomain={["dataMin - 100", "dataMax + 100"]}
      valueFormatter={(v) => v.toLocaleString()}
      showTrends={showTrends}
    />
  );
});
