import { memo } from "react";
import {
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Line,
  ComposedChart,
  Legend,
} from "recharts";
import { format, parseISO } from "date-fns";
import type { StepsData } from "../../types/api";
import { EmptyChartMessage } from "./shared";
import { chartTooltipStyle, TREND_CONFIGS } from "./chart-config";
import { STEP_GOAL_DEFAULT, STEP_FLOOR_DEFAULT } from "../../lib/constants";
import { useTrendData } from "../../hooks/useTrendData";

interface StepsChartProps {
  data: StepsData[];
  showTrends?: boolean;
  bandwidthShort?: number;
  bandwidthLong?: number;
}

export const StepsChart = memo(
  ({
    data,
    showTrends = false,
    bandwidthShort = 0.17,
    bandwidthLong = 0.33,
  }: StepsChartProps) => {
    const config = TREND_CONFIGS.steps;

    const normalizedData = data.map((d) => ({
      date: d.date,
      total_steps: d.total_steps,
      total_distance: d.total_distance ? d.total_distance / 1000 : null,
    }));

    const { chartData, hasData } = useTrendData(normalizedData, "total_steps", {
      method: "loess",
      bandwidthShort,
      bandwidthLong,
      showBaseline: false,
    });

    if (!hasData) {
      return <EmptyChartMessage message="No steps data available" />;
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
          <YAxis
            tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`}
            className="text-xs"
          />
          <Tooltip
            labelFormatter={(value) => format(parseISO(value as string), "PPP")}
            formatter={(value, name) => {
              const v = value as number | undefined;
              if (v === undefined) return ["-", name];
              if (name === "value") return [v.toLocaleString(), "Steps"];
              if (name === "trendShort") {
                return [`${(v / 1000).toFixed(1)}k`, "Short trend"];
              }
              if (name === "trendLong") {
                return [`${(v / 1000).toFixed(1)}k`, "Long trend"];
              }
              return [v, name];
            }}
            contentStyle={chartTooltipStyle}
          />

          <ReferenceLine
            y={STEP_GOAL_DEFAULT}
            stroke="hsl(var(--muted-foreground))"
            strokeDasharray="5 5"
            label={{
              value: "10k goal",
              position: "insideTopRight",
              fill: "hsl(var(--muted-foreground))",
              fontSize: 12,
            }}
          />

          <ReferenceLine
            y={STEP_FLOOR_DEFAULT}
            stroke="hsl(var(--destructive))"
            strokeDasharray="3 3"
            label={{
              value: "4k floor",
              position: "insideBottomRight",
              fill: "hsl(var(--destructive))",
              fontSize: 11,
            }}
          />

          <Bar dataKey="value" radius={[4, 4, 0, 0]} name="value">
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${String(index)}`}
                fill={
                  (entry.value ?? 0) >= STEP_FLOOR_DEFAULT
                    ? config.color
                    : "hsl(var(--destructive))"
                }
              />
            ))}
          </Bar>

          {showTrends && (
            <Line
              type="natural"
              dataKey="trendShort"
              stroke="hsl(var(--foreground) / 0.7)"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              dot={false}
              name="trendShort"
            />
          )}

          {showTrends && (
            <Line
              type="natural"
              dataKey="trendLong"
              stroke="hsl(var(--foreground) / 0.5)"
              strokeWidth={2.5}
              dot={false}
              name="trendLong"
            />
          )}

          {showTrends && <Legend />}
        </ComposedChart>
      </ResponsiveContainer>
    );
  },
);

StepsChart.displayName = "StepsChart";
