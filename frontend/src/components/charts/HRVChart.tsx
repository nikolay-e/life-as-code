import { memo } from "react";
import type { HRVData, WhoopRecoveryData } from "../../types/api";
import { MULTI_PROVIDER_CONFIGS } from "./chart-config";
import { MultiProviderLineChart } from "./MultiProviderLineChart";
import { mergeProviderData } from "../../lib/chart-utils";

interface HRVChartProps {
  garminData: HRVData[];
  whoopData?: WhoopRecoveryData[];
  showTrends?: boolean;
  bandwidthShort?: number;
  bandwidthLong?: number;
  dateRange?: { start: string; end: string };
}

export const HRVChart = memo(
  ({
    garminData,
    whoopData = [],
    showTrends = false,
    bandwidthShort = 0.17,
    bandwidthLong = 0.33,
    dateRange,
  }: HRVChartProps) => {
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
        showTrends={showTrends}
        bandwidthShort={bandwidthShort}
        bandwidthLong={bandwidthLong}
        dateRange={dateRange}
      />
    );
  },
);

HRVChart.displayName = "HRVChart";
