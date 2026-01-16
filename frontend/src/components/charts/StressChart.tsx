import { memo, useMemo } from "react";
import {
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ComposedChart,
} from "recharts";
import { format, parseISO, startOfDay } from "date-fns";
import type { StressData } from "../../types/api";
import { EmptyChartMessage } from "./shared";
import { chartTooltipStyle, TREND_CONFIGS } from "./chart-config";
import { renderTrendLines } from "./TrendLines";
import { useTrendData } from "../../hooks/useTrendData";

function dateToTimestamp(dateStr: string): number {
  return startOfDay(parseISO(dateStr)).getTime();
}

interface StressChartProps {
  data: StressData[];
  showTrends?: boolean;
  bandwidthShort?: number;
  bandwidthLong?: number;
  height?: number;
  dateRange?: { start: string; end: string };
}

export const StressChart = memo(
  ({
    data,
    showTrends = false,
    bandwidthShort = 0.17,
    bandwidthLong = 0.33,
    height = 250,
    dateRange,
  }: StressChartProps) => {
    const config = TREND_CONFIGS.stress;

    const normalizedData = data.map((d) => ({
      date: d.date,
      avg_stress: d.avg_stress,
    }));

    const { chartData, hasData } = useTrendData(normalizedData, "avg_stress", {
      method: "loess",
      bandwidthShort,
      bandwidthLong,
      showBaseline: false,
    });

    const xDomain = useMemo(() => {
      if (dateRange) {
        return [
          dateToTimestamp(dateRange.start),
          dateToTimestamp(dateRange.end),
        ];
      }
      return undefined;
    }, [dateRange]);

    if (!hasData) {
      return <EmptyChartMessage message="No stress data available" />;
    }

    return (
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={chartData} syncId="health-dashboard">
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis
            dataKey="timestamp"
            tickFormatter={(value: number) => format(new Date(value), "MMM d")}
            className="text-xs"
            type="number"
            scale="time"
            domain={xDomain ?? ["dataMin", "dataMax"]}
          />
          <YAxis domain={[0, 100]} className="text-xs" />
          <Tooltip
            labelFormatter={(value) =>
              format(new Date(value as number), "MMM d")
            }
            formatter={(value, name) => {
              if (name === "trendShort" || name === "trendLong") return null;
              const v = value as number | undefined;
              if (v === undefined) return ["-", name];
              if (name === "value") return [v.toFixed(0), "Stress"];
              return [v, name];
            }}
            contentStyle={chartTooltipStyle}
          />

          <Bar
            dataKey="value"
            fill={config.color}
            radius={[4, 4, 0, 0]}
            name="value"
          />

          {/* Trend lines on top */}
          {renderTrendLines(showTrends)}

          {showTrends && (
            <Legend
              formatter={(value: string) => {
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
