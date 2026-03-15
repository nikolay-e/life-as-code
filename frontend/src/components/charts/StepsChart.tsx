import { memo, useMemo } from "react";
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
import { format, parseISO, startOfDay } from "date-fns";
import type { StepsData } from "../../types/api";
import { EmptyChartMessage } from "./shared";
import { chartTooltipStyle, TREND_CONFIGS } from "./chart-config";
import { STEP_GOAL_DEFAULT, STEP_FLOOR_FALLBACK } from "../../lib/constants";
import { useTrendData } from "../../hooks/useTrendData";

function dateToTimestamp(dateStr: string): number {
  return startOfDay(parseISO(dateStr)).getTime();
}

interface StepsChartProps {
  readonly data: StepsData[];
  readonly showTrends?: boolean;
  readonly bandwidthShort?: number;
  readonly bandwidthLong?: number;
  height?: number;
  dateRange?: { start: string; end: string };
  stepsFloor?: number;
}

export const StepsChart = memo(
  ({
    data,
    showTrends = false,
    bandwidthShort = 0.17,
    bandwidthLong = 0.33,
    height = 250,
    dateRange,
    stepsFloor = STEP_FLOOR_FALLBACK,
  }: StepsChartProps) => {
    const config = TREND_CONFIGS.steps;

    const normalizedData = data.map((d) => ({
      date: d.date,
      total_steps: d.total_steps,
    }));

    const { chartData, hasData } = useTrendData(normalizedData, "total_steps", {
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
      return <EmptyChartMessage message="No steps data available" />;
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
            tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`}
            className="text-xs"
          />
          <Tooltip
            labelFormatter={(value) =>
              format(new Date(value as number), "MMM d")
            }
            formatter={(value, name) => {
              if (name === "trendShort" || name === "trendLong") return null;
              const v = value as number | undefined;
              if (v === undefined) return ["-", name];
              if (name === "value") return [v.toLocaleString(), "Steps"];
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
            y={stepsFloor}
            stroke="hsl(var(--destructive))"
            strokeDasharray="3 3"
            label={{
              value: `${(stepsFloor / 1000).toFixed(1)}k floor`,
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
                  (entry.value ?? 0) >= stepsFloor
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
