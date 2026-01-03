import { memo } from "react";
import type { WhoopRecoveryData } from "../../types/api";
import { TREND_CONFIGS } from "./chart-config";
import { useTrendData } from "../../hooks/useTrendData";
import { TrendLineChart } from "./TrendLineChart";

interface WhoopRecoveryChartProps {
  data: WhoopRecoveryData[];
  showTrends?: boolean;
  showBaseline?: boolean;
  bandwidthShort?: number;
  bandwidthLong?: number;
  dateRange?: { start: string; end: string };
}

export const WhoopRecoveryChart = memo(
  ({
    data,
    showTrends = false,
    showBaseline = false,
    bandwidthShort = 0.17,
    bandwidthLong = 0.33,
    dateRange,
  }: WhoopRecoveryChartProps) => {
    const config = TREND_CONFIGS.whoopRecovery;

    const normalizedData = data.map((d) => ({
      date: d.date,
      recovery_score: d.recovery_score,
    }));

    const { chartData, baseline, hasData } = useTrendData(
      normalizedData,
      "recovery_score",
      {
        method: "loess",
        bandwidthShort,
        bandwidthLong,
        showBaseline,
        baselineWindow: config.baselineWindow,
      },
    );

    return (
      <TrendLineChart
        chartData={chartData}
        hasData={hasData}
        baseline={baseline}
        config={config}
        emptyMessage="No Whoop recovery data available"
        valueLabel="Recovery"
        unit="%"
        shortTermLabel="Short trend"
        longTermLabel="Long trend"
        showTrends={showTrends}
        showBaseline={showBaseline}
        dateRange={dateRange}
      />
    );
  },
);

WhoopRecoveryChart.displayName = "WhoopRecoveryChart";
