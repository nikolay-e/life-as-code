import { memo } from "react";
import type { HRVData } from "../../types/api";
import { MULTI_PROVIDER_CONFIGS } from "./chart-config";
import { MultiProviderLineChart } from "./MultiProviderLineChart";
import { splitBySource } from "../../lib/chart-utils";
import type { ChartAnnotation } from "./annotations";
import {
  LOESS_BANDWIDTH_SHORT,
  LOESS_BANDWIDTH_LONG,
} from "../../lib/constants";

interface HRVChartProps {
  readonly data: HRVData[];
  readonly showTrends?: boolean;
  readonly bandwidthShort?: number;
  readonly bandwidthLong?: number;
  readonly dateRange?: { start: string; end: string };
  readonly annotations?: readonly ChartAnnotation[];
  readonly baselineMean?: number | null;
  readonly baselineStd?: number | null;
}

export const HRVChart = memo(
  ({
    data,
    showTrends = false,
    bandwidthShort = LOESS_BANDWIDTH_SHORT,
    bandwidthLong = LOESS_BANDWIDTH_LONG,
    dateRange,
    annotations,
    baselineMean,
    baselineStd,
  }: HRVChartProps) => {
    const config = MULTI_PROVIDER_CONFIGS.hrv;

    const mergedData = splitBySource(data, (d) => d.hrv_avg);

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
        annotations={annotations}
        baselineMean={baselineMean}
        baselineStd={baselineStd}
      />
    );
  },
);

HRVChart.displayName = "HRVChart";
