import { memo } from "react";
import type { WhoopWorkoutData } from "../../types/api";
import { TREND_CONFIGS } from "./chart-config";
import { useTrendData } from "../../hooks/useTrendData";
import { TrendLineChart } from "./TrendLineChart";

interface WhoopStrainChartProps {
  data: WhoopWorkoutData[];
  showTrends?: boolean;
  showBaseline?: boolean;
}

export const WhoopStrainChart = memo(function WhoopStrainChart({
  data,
  showTrends = false,
  showBaseline = false,
}: WhoopStrainChartProps) {
  const config = TREND_CONFIGS.whoopStrain;

  const normalizedData = data.map((d) => ({
    date: d.date,
    strain: d.strain,
  }));

  const { chartData, baseline, hasData } = useTrendData(
    normalizedData,
    "strain",
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
      emptyMessage="No Whoop strain data available"
      valueLabel="Strain"
      unit=""
      shortTermLabel="7-day trend"
      longTermLabel="30-day trend"
      longerTermLabel="90-day trend"
      showTrends={showTrends}
      showBaseline={showBaseline}
    />
  );
});
