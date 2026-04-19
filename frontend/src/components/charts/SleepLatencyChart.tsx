import { memo, useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import type { EightSleepSessionData } from "../../types/api";
import { chartTooltipStyle } from "./chart-config";
import { EmptyChartMessage } from "./shared";
import { dateToTimestamp, formatDateTick } from "../../lib/chart-utils";

interface SleepLatencyChartProps {
  readonly data: EightSleepSessionData[];
  readonly height?: number;
  readonly dateRange?: { start: string; end: string };
}

export const SleepLatencyChart = memo(
  ({ data, height = 200, dateRange }: SleepLatencyChartProps) => {
    const chartData = useMemo(() => {
      const filtered = dateRange
        ? data.filter(
            (d) => d.date >= dateRange.start && d.date <= dateRange.end,
          )
        : data;

      return filtered
        .filter((d) => d.latency_asleep_seconds !== null)
        .map((d) => ({
          timestamp: dateToTimestamp(d.date),
          latencyMinutes: Math.round((d.latency_asleep_seconds ?? 0) / 60),
        }))
        .sort((a, b) => a.timestamp - b.timestamp);
    }, [data, dateRange]);

    if (chartData.length === 0) {
      return <EmptyChartMessage message="No sleep latency data available" />;
    }

    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
          <XAxis
            dataKey="timestamp"
            type="number"
            scale="time"
            domain={["dataMin", "dataMax"]}
            tickFormatter={formatDateTick}
            tick={{ fontSize: 11 }}
          />
          <YAxis
            tick={{ fontSize: 11 }}
            tickFormatter={(v: number) => `${String(v)}m`}
          />
          <Tooltip
            contentStyle={chartTooltipStyle}
            labelFormatter={(ts: number) => new Date(ts).toLocaleDateString()}
            formatter={(value: number) => [
              `${String(value)} min`,
              "Time to Sleep",
            ]}
          />
          <ReferenceLine
            y={20}
            stroke="hsl(var(--sleep))"
            strokeDasharray="5 5"
            strokeOpacity={0.6}
            label={{ value: "20 min", position: "right", fontSize: 10 }}
          />
          <Bar
            dataKey="latencyMinutes"
            fill="hsl(var(--sleep))"
            opacity={0.7}
            radius={[2, 2, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    );
  },
);

SleepLatencyChart.displayName = "SleepLatencyChart";
