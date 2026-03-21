import { memo, useMemo } from "react";
import type {
  WhoopRecoveryData,
  GarminTrainingStatusData,
} from "../../types/api";
import { SOURCE_COLORS } from "./chart-config";
import { MultiProviderLineChart } from "./MultiProviderLineChart";
import {
  LOESS_BANDWIDTH_SHORT,
  LOESS_BANDWIDTH_LONG,
} from "../../lib/constants";

interface RecoveryChartProps {
  readonly whoopData: WhoopRecoveryData[];
  readonly garminData?: GarminTrainingStatusData[];
  readonly showTrends?: boolean;
  readonly bandwidthShort?: number;
  readonly bandwidthLong?: number;
  readonly dateRange?: { start: string; end: string };
}

export const RecoveryChart = memo(
  ({
    whoopData,
    garminData = [],
    showTrends = false,
    bandwidthShort = LOESS_BANDWIDTH_SHORT,
    bandwidthLong = LOESS_BANDWIDTH_LONG,
    dateRange,
  }: RecoveryChartProps) => {
    const config = {
      garminColor: SOURCE_COLORS.garmin,
      whoopColor: SOURCE_COLORS.whoop,
    };

    const mergedData = useMemo(() => {
      const whoopMap = new Map(
        whoopData
          .filter((d) => d.recovery_score !== null)
          .map((d) => [d.date, d.recovery_score]),
      );

      const garminMap = new Map(
        garminData
          .filter((d) => d.training_readiness_score !== null)
          .map((d) => [d.date, d.training_readiness_score]),
      );

      const allDates = new Set([...whoopMap.keys(), ...garminMap.keys()]);

      return Array.from(allDates)
        .map((date) => ({
          date,
          garminValue: garminMap.get(date) ?? null,
          whoopValue: whoopMap.get(date) ?? null,
        }))
        .sort((a, b) => a.date.localeCompare(b.date));
    }, [whoopData, garminData]);

    return (
      <MultiProviderLineChart
        data={mergedData}
        config={config}
        emptyMessage="No recovery data available"
        garminLabel="Training Readiness"
        whoopLabel="Whoop Recovery"
        unit="%"
        yDomain={[0, 100]}
        showTrends={showTrends}
        bandwidthShort={bandwidthShort}
        bandwidthLong={bandwidthLong}
        dateRange={dateRange}
      />
    );
  },
);

RecoveryChart.displayName = "RecoveryChart";
