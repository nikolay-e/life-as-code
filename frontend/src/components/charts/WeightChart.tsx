import { memo, useMemo } from "react";
import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from "recharts";
import { format } from "date-fns";
import type { WeightData } from "../../types/api";
import { EmptyChartMessage } from "./shared";
import { chartTooltipStyle, TREND_CONFIGS } from "./chart-config";
import { renderTrendLines } from "./TrendLines";
import { useWeightTrendData } from "../../hooks/useWeightTrendData";
import { dateToTimestamp } from "../../lib/chart-utils";

interface WeightChartProps {
  readonly data: WeightData[];
  readonly showTrends?: boolean;
  readonly showBaseline?: boolean;
  readonly bandwidthShort?: number;
  readonly bandwidthLong?: number;
  readonly height?: number;
  dateRange?: { start: string; end: string };
}

export const WeightChart = memo(
  ({
    data,
    showTrends = false,
    showBaseline = false,
    bandwidthShort = 0.17,
    bandwidthLong = 0.33,
    height = 250,
    dateRange,
  }: WeightChartProps) => {
    const config = TREND_CONFIGS.weight;

    const { chartData, baseline, minWeight, maxWeight, padding, hasData } =
      useWeightTrendData(data, {
        bandwidthShort,
        bandwidthLong,
        showBaseline,
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
      return <EmptyChartMessage message="No weight data available" />;
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
          <YAxis
            domain={[minWeight - padding, maxWeight + padding]}
            className="text-xs"
            tickFormatter={(v: number) => v.toFixed(1)}
          />
          <Tooltip
            labelFormatter={(value) =>
              format(new Date(value as number), "MMM d")
            }
            formatter={(value, name) => {
              if (name === "trendShort" || name === "trendLong") return null;
              const v = value as number | null;
              if (v === null) return ["-", name];
              if (name === "rawWeight") return [`${v.toFixed(1)}kg`, "Weight"];
              return [v, name];
            }}
            contentStyle={chartTooltipStyle}
          />

          {showBaseline && baseline && (
            <>
              <ReferenceLine
                y={baseline.baseline}
                stroke="hsl(var(--muted-foreground))"
                strokeDasharray="3 3"
                label={{
                  value: `Mean: ${baseline.baseline.toFixed(1)}`,
                  position: "insideTopRight",
                  fill: "hsl(var(--muted-foreground))",
                  fontSize: 11,
                }}
              />
              <ReferenceLine
                y={baseline.median}
                stroke="hsl(var(--muted-foreground) / 0.6)"
                strokeDasharray="6 3"
                label={{
                  value: `Median: ${baseline.median.toFixed(1)}`,
                  position: "insideBottomRight",
                  fill: "hsl(var(--muted-foreground) / 0.8)",
                  fontSize: 11,
                }}
              />
            </>
          )}

          <Bar
            dataKey="rawWeight"
            fill={config.color}
            radius={[4, 4, 0, 0]}
            name="rawWeight"
          />

          {renderTrendLines(showTrends)}

          {showTrends && (
            <Legend
              formatter={(value: string) => {
                if (value === "rawWeight") return "Weight";
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

WeightChart.displayName = "WeightChart";
