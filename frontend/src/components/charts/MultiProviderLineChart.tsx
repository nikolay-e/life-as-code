import { memo, useMemo } from "react";
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from "recharts";
import { format, parseISO } from "date-fns";
import { EmptyChartMessage } from "./shared";
import { chartTooltipStyle } from "./chart-config";
import { renderTrendLines } from "./TrendLines";
import type { MultiProviderDataPoint } from "../../lib/chart-utils";
import { loessSmooth } from "../../lib/statistics";

interface MultiProviderLineChartProps {
  data: MultiProviderDataPoint[];
  config: {
    garminColor: string;
    whoopColor: string;
  };
  emptyMessage: string;
  garminLabel: string;
  whoopLabel: string;
  unit: string;
  height?: number | `${number}%`;
  yDomain?: [number | string, number | string];
  valueFormatter?: (value: number) => string;
  baselineValue?: number | null;
  showTrends?: boolean;
  bandwidthShort?: number;
  bandwidthLong?: number;
}

export const MultiProviderLineChart = memo(
  ({
    data,
    config,
    emptyMessage,
    garminLabel,
    whoopLabel,
    unit,
    height = 250,
    yDomain = ["dataMin - 5", "dataMax + 5"],
    valueFormatter = (v) => v.toFixed(0),
    baselineValue,
    showTrends = false,
    bandwidthShort = 0.17,
    bandwidthLong = 0.33,
  }: MultiProviderLineChartProps) => {
    const hasData = data.some(
      (d) => d.garminValue !== null || d.whoopValue !== null,
    );

    const chartData = useMemo(() => {
      if (!showTrends || data.length === 0) return data;

      const withAvg = data.map((d) => ({
        ...d,
        avgValue:
          d.garminValue !== null && d.whoopValue !== null
            ? (d.garminValue + d.whoopValue) / 2
            : (d.garminValue ?? d.whoopValue),
      }));

      const loessShort = loessSmooth(withAvg, "avgValue", bandwidthShort);
      const loessLong = loessSmooth(withAvg, "avgValue", bandwidthLong);

      return withAvg.map((d, i) => ({
        ...d,
        trendShort: loessShort[i]?.loess ?? null,
        trendLong: loessLong[i]?.loess ?? null,
      }));
    }, [data, showTrends, bandwidthShort, bandwidthLong]);

    if (!hasData) {
      return <EmptyChartMessage message={emptyMessage} />;
    }

    return (
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis
            dataKey="date"
            tickFormatter={(value) => format(parseISO(value), "MMM d")}
            className="text-xs"
          />
          <YAxis domain={yDomain} className="text-xs" />
          <Tooltip
            labelFormatter={(value) => format(parseISO(value as string), "PPP")}
            formatter={(value, name) => {
              const v = value as number | undefined;
              if (v === undefined) {
                return ["-", name];
              }
              if (name === "garminValue") {
                return [`${valueFormatter(v)} ${unit}`, garminLabel];
              }
              if (name === "whoopValue") {
                return [`${valueFormatter(v)} ${unit}`, whoopLabel];
              }
              if (name === "trendShort") {
                return [`${valueFormatter(v)} ${unit}`, "Short trend"];
              }
              if (name === "trendLong") {
                return [`${valueFormatter(v)} ${unit}`, "Long trend"];
              }
              return [v, name];
            }}
            contentStyle={chartTooltipStyle}
          />

          <Line
            type="linear"
            dataKey="garminValue"
            stroke="transparent"
            strokeWidth={0}
            dot={{ fill: config.garminColor, r: 2, strokeWidth: 0 }}
            activeDot={{ fill: config.garminColor, r: 4, strokeWidth: 0 }}
            name="garminValue"
            isAnimationActive={false}
          />
          <Line
            type="linear"
            dataKey="whoopValue"
            stroke="transparent"
            strokeWidth={0}
            dot={{ fill: config.whoopColor, r: 2, strokeWidth: 0 }}
            activeDot={{ fill: config.whoopColor, r: 4, strokeWidth: 0 }}
            name="whoopValue"
            isAnimationActive={false}
          />

          {renderTrendLines(showTrends)}

          {baselineValue !== null && baselineValue !== undefined && (
            <ReferenceLine
              y={baselineValue}
              stroke="hsl(var(--muted-foreground))"
              strokeDasharray="3 3"
              label={{
                value: `Baseline: ${valueFormatter(baselineValue)}`,
                position: "insideTopRight",
                fill: "hsl(var(--muted-foreground))",
                fontSize: 11,
              }}
            />
          )}

          <Legend
            formatter={(value) => {
              if (value === "garminValue") {
                return garminLabel;
              }
              if (value === "whoopValue") {
                return whoopLabel;
              }
              if (value === "trendShort") {
                return "Short trend";
              }
              if (value === "trendLong") {
                return "Long trend";
              }
              return value;
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    );
  },
);

MultiProviderLineChart.displayName = "MultiProviderLineChart";
