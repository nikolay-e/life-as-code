import { memo } from "react";
import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ComposedChart,
} from "recharts";
import { format, parseISO } from "date-fns";
import type { StressData } from "../../types/api";
import { EmptyChartMessage } from "./shared";
import { chartTooltipStyle, TREND_CONFIGS } from "./chart-config";
import { renderTrendLines } from "./TrendLines";
import { useTrendData } from "../../hooks/useTrendData";

interface StressChartProps {
  data: StressData[];
  showTrends?: boolean;
  bandwidthShort?: number;
  bandwidthLong?: number;
}

export const StressChart = memo(
  ({
    data,
    showTrends = false,
    bandwidthShort = 0.17,
    bandwidthLong = 0.33,
  }: StressChartProps) => {
    const config = TREND_CONFIGS.stress;

    const normalizedData = data.map((d) => ({
      date: d.date,
      avg_stress: d.avg_stress,
      max_stress: d.max_stress,
    }));

    const { chartData, hasData } = useTrendData(normalizedData, "avg_stress", {
      method: "loess",
      bandwidthShort,
      bandwidthLong,
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
              if (name === "trendShort") return [v.toFixed(0), "Short trend"];
              if (name === "trendLong") return [v.toFixed(0), "Long trend"];
              return [v, name];
            }}
            contentStyle={chartTooltipStyle}
          />

          {/* Data points first (rendered below) */}
          <Line
            type="linear"
            dataKey="value"
            stroke="transparent"
            strokeWidth={0}
            dot={{ fill: config.color, r: 2, strokeWidth: 0 }}
            activeDot={{ fill: config.color, r: 4, strokeWidth: 0 }}
            name="value"
            isAnimationActive={false}
          />

          {/* Trend lines on top */}
          {renderTrendLines(showTrends)}

          {showTrends && (
            <Legend
              formatter={(value) => {
                if (value === "value") return "Stress";
                if (value === "trendShort") return "Short trend";
                if (value === "trendLong") return "Long trend";
                return value;
              }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    );
  },
);

StressChart.displayName = "StressChart";
