import { memo } from "react";
import type { WhoopRecoveryData } from "../../types/api";
import { TREND_CONFIGS } from "./chart-config";
import { useTrendData } from "../../hooks/useTrendData";
import { TrendLineChart } from "./TrendLineChart";

interface WhoopRecoveryChartProps {
  data: WhoopRecoveryData[];
  showTrends?: boolean;
  showBaseline?: boolean;
}

export const WhoopRecoveryChart = memo(function WhoopRecoveryChart({
  data,
  showTrends = false,
  showBaseline = false,
}: WhoopRecoveryChartProps) {
  const config = TREND_CONFIGS.whoopRecovery;

  const normalizedData = data.map((d) => ({
    date: d.date,
    recovery_score: d.recovery_score,
  }));

  const { chartData, baseline, hasData } = useTrendData(
    normalizedData,
    "recovery_score",
    {
      method: config.method,
      shortTermWindow: config.shortTermWindow,
      longTermWindow: config.longTermWindow,
      longerTermWindow: config.longerTermWindow,
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
      shortTermLabel="7-day trend"
      longTermLabel="30-day trend"
      longerTermLabel="90-day trend"
      showTrends={showTrends}
      showBaseline={showBaseline}
    />
  );
});
