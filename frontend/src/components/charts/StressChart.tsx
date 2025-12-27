import { memo } from "react";
import {
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Line,
  Legend,
  ComposedChart,
} from "recharts";
import { format, parseISO } from "date-fns";
import type { StressData } from "../../types/api";
import { EmptyChartMessage } from "./shared";
import { chartTooltipStyle, TREND_CONFIGS } from "./chart-config";
import { useTrendData } from "../../hooks/useTrendData";

interface StressChartProps {
  data: StressData[];
  showTrends?: boolean;
}

export const StressChart = memo(function StressChart({
  data,
  showTrends = false,
}: StressChartProps) {
  const config = TREND_CONFIGS.stress;

  const normalizedData = data.map((d) => ({
    date: d.date,
    avg_stress: d.avg_stress,
    max_stress: d.max_stress,
  }));

  const { chartData, hasData } = useTrendData(normalizedData, "avg_stress", {
    method: config.method,
    shortTermWindow: config.shortTermWindow,
    longTermWindow: config.longTermWindow,
    showBaseline: false,
  });

  if (!hasData) {
    return <EmptyChartMessage message="No stress data available" />;
  }

  return (
    <ResponsiveContainer width="100%" height={250}>
      <ComposedChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis
          dataKey="date"
          tickFormatter={(value) => format(parseISO(value), "MMM d")}
          className="text-xs"
        />
        <YAxis domain={[0, 100]} className="text-xs" />
        <Tooltip
          labelFormatter={(value) => format(parseISO(value as string), "PPP")}
          formatter={(value, name) => {
            const v = value as number | undefined;
            if (v === undefined) return ["-", name];
            if (name === "value") return [v.toFixed(0), "Avg Stress"];
            if (name === "shortTermTrend") return [v.toFixed(0), "5-day trend"];
            if (name === "longTermTrend") return [v.toFixed(0), "14-day trend"];
            return [v, name];
          }}
          contentStyle={chartTooltipStyle}
        />

        <Area
          type="monotone"
          dataKey="value"
          stroke={config.color}
          fill={config.color}
          fillOpacity={0.3}
          strokeWidth={2}
          name="value"
        />

        {showTrends && (
          <Line
            type="monotone"
            dataKey="shortTermTrend"
            stroke={config.trendColor}
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={false}
            name="shortTermTrend"
          />
        )}

        {showTrends && (
          <Line
            type="monotone"
            dataKey="longTermTrend"
            stroke={config.longTermTrendColor}
            strokeWidth={2}
            strokeOpacity={0.7}
            dot={false}
            name="longTermTrend"
          />
        )}

        {showTrends && <Legend />}
      </ComposedChart>
    </ResponsiveContainer>
  );
});
