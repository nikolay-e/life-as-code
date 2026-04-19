import { memo } from "react";
import type {
  HRVData,
  WhoopRecoveryData,
  EightSleepSessionData,
} from "../../types/api";
import { MULTI_PROVIDER_CONFIGS } from "./chart-config";
import { MultiProviderLineChart } from "./MultiProviderLineChart";
import { mergeProviderData } from "../../lib/chart-utils";
import {
  LOESS_BANDWIDTH_SHORT,
  LOESS_BANDWIDTH_LONG,
} from "../../lib/constants";

interface HRVChartProps {
  readonly garminData: HRVData[];
  readonly whoopData?: WhoopRecoveryData[];
  readonly eightSleepData?: EightSleepSessionData[];
  readonly showTrends?: boolean;
  readonly bandwidthShort?: number;
  readonly bandwidthLong?: number;
  readonly dateRange?: { start: string; end: string };
}

export const HRVChart = memo(
  ({
    garminData,
    whoopData = [],
    eightSleepData = [],
    showTrends = false,
    bandwidthShort = LOESS_BANDWIDTH_SHORT,
    bandwidthLong = LOESS_BANDWIDTH_LONG,
    dateRange,
  }: HRVChartProps) => {
    const config = MULTI_PROVIDER_CONFIGS.hrv;

    const mergedData = mergeProviderData(
      garminData,
      whoopData,
      (d) => d.hrv_avg,
      (d) => d.hrv_rmssd,
      eightSleepData,
      (d) => d.hrv,
    );

    return (
      <MultiProviderLineChart
        data={mergedData}
        config={config}
        emptyMessage="No HRV data available"
        garminLabel="Garmin HRV"
        whoopLabel="Whoop HRV"
        eightSleepLabel="Eight Sleep HRV"
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
