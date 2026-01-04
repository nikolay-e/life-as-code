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
import { format, parseISO, startOfDay } from "date-fns";
import { EmptyChartMessage } from "./shared";
import { chartTooltipStyle } from "./chart-config";
import { renderTrendLines } from "./TrendLines";
import type { TrendChartData, BaselineData } from "../../hooks/useTrendData";

function dateToTimestamp(dateStr: string): number {
  return startOfDay(parseISO(dateStr)).getTime();
}

interface TrendLineChartProps {
  chartData: TrendChartData[];
  hasData: boolean;
  baseline: BaselineData | null;
  config: {
    color: string;
  };
  emptyMessage: string;
  valueLabel: string;
  unit: string;
  shortTermLabel?: string;
  longTermLabel?: string;
  showTrends?: boolean;
  showBaseline?: boolean;
  height?: number | `${number}%`;
  yDomain?: [number | string, number | string];
  valueFormatter?: (value: number) => string;
  dateRange?: { start: string; end: string };
}

function TrendLineChartComponent({
  chartData,
  hasData,
  baseline,
  config,
  emptyMessage,
  valueLabel,
  unit,
  shortTermLabel = "Short trend",
  longTermLabel = "Long trend",
  showTrends = false,
  showBaseline = false,
  height = 250,
  yDomain = ["dataMin - 5", "dataMax + 5"],
  valueFormatter = (v: number): string => v.toFixed(0),
  dateRange,
}: TrendLineChartProps): React.ReactElement | null {
  const xDomain = useMemo(() => {
    if (dateRange) {
      return [dateToTimestamp(dateRange.start), dateToTimestamp(dateRange.end)];
    }
    return undefined;
  }, [dateRange]);

  if (!hasData) {
    return <EmptyChartMessage message={emptyMessage} />;
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis
          dataKey="timestamp"
          tickFormatter={(value: number) => format(new Date(value), "MMM d")}
          className="text-xs"
          type="number"
          scale="time"
          domain={xDomain ?? ["dataMin", "dataMax"]}
        />
        <YAxis domain={yDomain} className="text-xs" />
        <Tooltip
          labelFormatter={(value) => format(new Date(value as number), "PPP")}
          formatter={(value, name) => {
            const v = value as number | undefined;
            if (v === undefined) return ["-", name];
            if (name === "value") {
              return [`${valueFormatter(v)} ${unit}`, valueLabel];
            }
            if (name === "trendShort") {
              return [`${valueFormatter(v)} ${unit}`, shortTermLabel];
            }
            if (name === "trendLong") {
              return [`${valueFormatter(v)} ${unit}`, longTermLabel];
            }
            return [String(v), name];
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
            formatter={(value: string) => {
              if (value === "value") return valueLabel;
              if (value === "trendShort") return shortTermLabel;
              if (value === "trendLong") return longTermLabel;
              return value;
            }}
          />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export const TrendLineChart = memo(TrendLineChartComponent);

TrendLineChart.displayName = "TrendLineChart";
