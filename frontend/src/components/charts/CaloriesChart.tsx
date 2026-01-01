import { memo, useMemo } from "react";
import type {
  GarminTrainingStatusData,
  WhoopCycleData,
  EnergyData,
} from "../../types/api";
import { MULTI_PROVIDER_CONFIGS } from "./chart-config";
import { MultiProviderLineChart } from "./MultiProviderLineChart";
import { mergeProviderData } from "../../lib/chart-utils";

interface CaloriesChartProps {
  garminData: GarminTrainingStatusData[];
  whoopData?: WhoopCycleData[];
  energyData?: EnergyData[];
  showTrends?: boolean;
}

export const CaloriesChart = memo(function CaloriesChart({
  garminData,
  whoopData = [],
  energyData = [],
  showTrends = false,
}: CaloriesChartProps) {
  const config = MULTI_PROVIDER_CONFIGS.calories;

  const combinedGarminData = useMemo(() => {
    const energyByDate = new Map(
      energyData
        .filter((d) => d.active_energy !== null)
        .map((d) => [d.date, d.active_energy]),
    );

    const garminByDate = new Map(
      garminData
        .filter((d) => d.total_kilocalories !== null)
        .map((d) => [d.date, d]),
    );

    const allDates = new Set([...energyByDate.keys(), ...garminByDate.keys()]);

    return Array.from(allDates).map((date) => {
      const garmin = garminByDate.get(date);
      const energy = energyByDate.get(date);
      return {
        date,
        total_kilocalories: garmin?.total_kilocalories ?? energy ?? null,
      } as GarminTrainingStatusData;
    });
  }, [garminData, energyData]);

  const mergedData = mergeProviderData(
    combinedGarminData,
    whoopData,
    (d) => d.total_kilocalories,
    (d) => (d.kilojoules !== null ? Math.round(d.kilojoules / 4.184) : null),
  );

  return (
    <MultiProviderLineChart
      data={mergedData}
      config={config}
      emptyMessage="No calories data available"
      garminLabel="Active"
      whoopLabel="Whoop"
      unit="kcal"
      yDomain={["dataMin - 100", "dataMax + 100"]}
      valueFormatter={(v) => v.toLocaleString()}
      showTrends={showTrends}
    />
  );
});
