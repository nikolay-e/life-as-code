import { memo } from "react";
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
import type { TrendChartData, BaselineData } from "../../hooks/useTrendData";

interface TrendLineChartProps {
  chartData: TrendChartData[];
  hasData: boolean;
  baseline: BaselineData | null;
  config: {
    color: string;
    trendColor: string;
    longTermTrendColor: string;
    longerTermTrendColor: string;
  };
  emptyMessage: string;
  valueLabel: string;
  unit: string;
  shortTermLabel: string;
  longTermLabel: string;
  longerTermLabel: string;
  showTrends?: boolean;
  showBaseline?: boolean;
  height?: number | `${number}%`;
  yDomain?: [number | string, number | string];
  valueFormatter?: (value: number) => string;
}

export const TrendLineChart = memo(function TrendLineChart({
  chartData,
  hasData,
  baseline,
  config,
  emptyMessage,
  valueLabel,
  unit,
  shortTermLabel,
  longTermLabel,
  longerTermLabel,
  showTrends = false,
  showBaseline = false,
  height = 250,
  yDomain = ["dataMin - 5", "dataMax + 5"],
  valueFormatter = (v) => v.toFixed(0),
}: TrendLineChartProps) {
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
            if (v === undefined) return ["-", name];
            if (name === "value")
              return [`${valueFormatter(v)} ${unit}`, valueLabel];
            if (name === "shortTermTrend")
              return [`${valueFormatter(v)} ${unit}`, shortTermLabel];
            if (name === "longTermTrend")
              return [`${valueFormatter(v)} ${unit}`, longTermLabel];
            if (name === "longerTermTrend")
              return [`${valueFormatter(v)} ${unit}`, longerTermLabel];
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

        {showBaseline && baseline && (
          <>
            <ReferenceLine
              y={baseline.baseline}
              stroke="hsl(var(--muted-foreground))"
              strokeDasharray="3 3"
              label={{
                value: `Mean: ${valueFormatter(baseline.baseline)}`,
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
                value: `Median: ${valueFormatter(baseline.median)}`,
                position: "insideBottomRight",
                fill: "hsl(var(--muted-foreground) / 0.8)",
                fontSize: 11,
              }}
            />
          </>
        )}

        {showTrends && (
          <Legend
            formatter={(value) => {
              if (value === "value") return valueLabel;
              if (value === "shortTermTrend") return shortTermLabel;
              if (value === "longTermTrend") return longTermLabel;
              if (value === "longerTermTrend") return longerTermLabel;
              return value;
            }}
          />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
});
