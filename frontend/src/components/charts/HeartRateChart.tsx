import { memo } from "react";
import type { HeartRateData } from "../../types/api";
import { MULTI_PROVIDER_CONFIGS } from "./chart-config";
import { MultiProviderLineChart } from "./MultiProviderLineChart";
import { splitBySource } from "../../lib/chart-utils";
import type { ChartAnnotation } from "./annotations";
import {
  LOESS_BANDWIDTH_SHORT,
  LOESS_BANDWIDTH_LONG,
} from "../../lib/constants";

interface HeartRateChartProps {
  readonly data: HeartRateData[];
  readonly showTrends?: boolean;
  readonly bandwidthShort?: number;
  readonly bandwidthLong?: number;
  readonly dateRange?: { start: string; end: string };
  readonly annotations?: readonly ChartAnnotation[];
  readonly baselineMean?: number | null;
  readonly baselineStd?: number | null;
}

export const HeartRateChart = memo(
  ({
    data,
    showTrends = false,
    bandwidthShort = LOESS_BANDWIDTH_SHORT,
    bandwidthLong = LOESS_BANDWIDTH_LONG,
    dateRange,
    annotations,
    baselineMean,
    baselineStd,
  }: HeartRateChartProps) => {
    const config = MULTI_PROVIDER_CONFIGS.restingHr;

    const mergedData = splitBySource(data, (d) => d.resting_hr);

    return (
      <MultiProviderLineChart
        data={mergedData}
        config={config}
        emptyMessage="No heart rate data available"
        garminLabel="Garmin RHR"
        whoopLabel="Whoop RHR"
        eightSleepLabel="Eight Sleep HR"
        unit="bpm"
        yDomain={["dataMin - 5", "dataMax + 5"]}
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

HeartRateChart.displayName = "HeartRateChart";
