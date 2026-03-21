import { memo, useMemo } from "react";
import type { WhoopCycleData, EnergyData } from "../../types/api";
import { MULTI_PROVIDER_CONFIGS } from "./chart-config";
import { MultiProviderLineChart } from "./MultiProviderLineChart";
import { mergeProviderData } from "../../lib/chart-utils";
import {
  LOESS_BANDWIDTH_SHORT,
  LOESS_BANDWIDTH_LONG,
} from "../../lib/constants";

interface GarminCaloriesData {
  readonly date: string;
  readonly total_kilocalories: number | null;
}

interface CaloriesChartProps {
  readonly garminData: GarminCaloriesData[];
  readonly whoopData?: WhoopCycleData[];
  readonly energyData?: EnergyData[];
  readonly showTrends?: boolean;
  readonly bandwidthShort?: number;
  readonly bandwidthLong?: number;
  readonly dateRange?: { start: string; end: string };
}

export const CaloriesChart = memo(
  ({
    garminData,
    whoopData = [],
    energyData = [],
    showTrends = false,
    bandwidthShort = LOESS_BANDWIDTH_SHORT,
    bandwidthLong = LOESS_BANDWIDTH_LONG,
    dateRange,
  }: CaloriesChartProps) => {
    const config = MULTI_PROVIDER_CONFIGS.calories;

    const combinedGarminData = useMemo((): GarminCaloriesData[] => {
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

      const allDates = new Set([
        ...energyByDate.keys(),
        ...garminByDate.keys(),
      ]);

      return Array.from(allDates).map((date) => {
        const garmin = garminByDate.get(date);
        const energy = energyByDate.get(date);
        return {
          date,
          total_kilocalories: garmin?.total_kilocalories ?? energy ?? null,
        };
      });
    }, [garminData, energyData]);

    const mergedData = mergeProviderData(
      combinedGarminData,
      whoopData,
      (d) => d.total_kilocalories,
      (d) => (d.kilojoules === null ? null : Math.round(d.kilojoules / 4.184)),
    );

    return (
      <MultiProviderLineChart
        data={mergedData}
        config={config}
        emptyMessage="No calories data available"
        garminLabel="Active"
        whoopLabel="Whoop"
        unit="kcal"
        yDomain={[0, "dataMax + 100"]}
        valueFormatter={(v) => v.toLocaleString()}
        showTrends={showTrends}
        bandwidthShort={bandwidthShort}
        bandwidthLong={bandwidthLong}
        dateRange={dateRange}
      />
    );
  },
);

CaloriesChart.displayName = "CaloriesChart";
