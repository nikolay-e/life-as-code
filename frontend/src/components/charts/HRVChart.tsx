import { memo, useMemo } from "react";
import type { HRVData } from "../../types/api";
import { MULTI_PROVIDER_CONFIGS } from "./chart-config";
import { MultiProviderLineChart } from "./MultiProviderLineChart";
import { splitBySource } from "../../lib/chart-utils";
import type { ChartAnnotation } from "./annotations";
import {
  LOESS_BANDWIDTH_SHORT,
  LOESS_BANDWIDTH_LONG,
} from "../../lib/constants";
import { toTimeMs } from "../../lib/health";

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

const HRV_STATUS_STYLES: Record<string, { label: string; classes: string }> = {
  balanced: {
    label: "Balanced",
    classes:
      "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30",
  },
  unbalanced: {
    label: "Unbalanced",
    classes:
      "bg-orange-500/15 text-orange-700 dark:text-orange-300 border-orange-500/30",
  },
  low: {
    label: "Low",
    classes: "bg-red-500/15 text-red-700 dark:text-red-300 border-red-500/30",
  },
  poor: {
    label: "Poor",
    classes: "bg-red-500/15 text-red-700 dark:text-red-300 border-red-500/30",
  },
  stressed: {
    label: "Stressed",
    classes:
      "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30",
  },
  no_status: {
    label: "No status",
    classes: "bg-muted text-muted-foreground border-muted-foreground/20",
  },
};

function styleForStatus(status: string): {
  label: string;
  classes: string;
} {
  const key = status.toLowerCase().trim();
  if (Object.hasOwn(HRV_STATUS_STYLES, key)) return HRV_STATUS_STYLES[key];
  return {
    label: status.charAt(0).toUpperCase() + status.slice(1).toLowerCase(),
    classes: "bg-muted text-foreground border-muted-foreground/20",
  };
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

    const sortedDesc = useMemo(
      () => [...data].sort((a, b) => toTimeMs(b.date) - toTimeMs(a.date)),
      [data],
    );

    const latestBaseline = useMemo(() => {
      const found = sortedDesc.find(
        (d) => d.baseline_low_ms != null && d.baseline_high_ms != null,
      );
      if (!found) return null;
      return {
        low: found.baseline_low_ms as number,
        high: found.baseline_high_ms as number,
      };
    }, [sortedDesc]);

    const latestStatus = useMemo(() => {
      const found = sortedDesc.find(
        (d) => d.hrv_status != null && d.hrv_status !== "",
      );
      return found?.hrv_status ?? null;
    }, [sortedDesc]);

    const latestFeedback = useMemo(() => {
      const found = sortedDesc.find(
        (d) => d.feedback_phrase != null && d.feedback_phrase !== "",
      );
      return found?.feedback_phrase ?? null;
    }, [sortedDesc]);

    const statusStyle = latestStatus ? styleForStatus(latestStatus) : null;

    return (
      <div className="space-y-2">
        {(statusStyle ?? latestFeedback ?? latestBaseline) != null && (
          <div className="flex flex-wrap items-center gap-2">
            {statusStyle && (
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${statusStyle.classes}`}
              >
                {statusStyle.label}
              </span>
            )}
            {latestBaseline && (
              <span className="text-xs text-muted-foreground">
                Baseline {Math.round(latestBaseline.low)}–
                {Math.round(latestBaseline.high)} ms
              </span>
            )}
            {latestFeedback && (
              <span className="text-xs italic text-muted-foreground">
                {latestFeedback}
              </span>
            )}
          </div>
        )}
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
          bandLow={latestBaseline?.low ?? null}
          bandHigh={latestBaseline?.high ?? null}
          bandLabel="Baseline range"
        />
      </div>
    );
  },
);

HRVChart.displayName = "HRVChart";
