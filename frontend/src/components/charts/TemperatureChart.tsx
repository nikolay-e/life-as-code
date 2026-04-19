import { memo, useMemo } from "react";
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import type { EightSleepSessionData } from "../../types/api";
import { chartTooltipStyle } from "./chart-config";
import { EmptyChartMessage } from "./shared";
import { dateToTimestamp, formatDateTick } from "../../lib/chart-utils";

interface TemperatureChartProps {
  readonly data: EightSleepSessionData[];
  readonly height?: number;
  readonly dateRange?: { start: string; end: string };
}

export const TemperatureChart = memo(
  ({ data, height = 250, dateRange }: TemperatureChartProps) => {
    const chartData = useMemo(() => {
      const filtered = dateRange
        ? data.filter(
            (d) => d.date >= dateRange.start && d.date <= dateRange.end,
          )
        : data;

      return filtered
        .filter(
          (d) => d.bed_temp_celsius !== null || d.room_temp_celsius !== null,
        )
        .map((d) => ({
          timestamp: dateToTimestamp(d.date),
          bedTemp: d.bed_temp_celsius,
          roomTemp: d.room_temp_celsius,
        }))
        .sort((a, b) => a.timestamp - b.timestamp);
    }, [data, dateRange]);

    if (chartData.length === 0) {
      return <EmptyChartMessage message="No temperature data available" />;
    }

    return (
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={chartData}>
          <defs>
            <linearGradient id="bedTempFill" x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="0%"
                stopColor="hsl(25, 90%, 55%)"
                stopOpacity={0.3}
              />
              <stop
                offset="100%"
                stopColor="hsl(25, 90%, 55%)"
                stopOpacity={0.05}
              />
            </linearGradient>
          </defs>
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
            domain={["auto", "auto"]}
            tickFormatter={(v: number) => `${String(v)}°`}
          />
          <Tooltip
            contentStyle={chartTooltipStyle}
            labelFormatter={(ts: number) => new Date(ts).toLocaleDateString()}
            formatter={(value: number, name: string) => [
              `${value.toFixed(1)}°C`,
              name === "bedTemp" ? "Bed" : "Room",
            ]}
          />
          <Area
            type="monotone"
            dataKey="bedTemp"
            stroke="hsl(25, 90%, 55%)"
            fill="url(#bedTempFill)"
            strokeWidth={2}
            dot={false}
            name="bedTemp"
          />
          <Line
            type="monotone"
            dataKey="roomTemp"
            stroke="hsl(220, 70%, 55%)"
            strokeWidth={1.5}
            dot={false}
            name="roomTemp"
          />
        </ComposedChart>
      </ResponsiveContainer>
    );
  },
);

TemperatureChart.displayName = "TemperatureChart";
