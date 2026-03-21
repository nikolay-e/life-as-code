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
import { format, parseISO, startOfDay } from "date-fns";
import { EmptyChartMessage } from "./shared";
import { chartTooltipStyle } from "./chart-config";
import { renderTrendLines } from "./TrendLines";
import type { MultiProviderDataPoint } from "../../lib/chart-utils";
import { loessSmooth } from "../../lib/statistics";

function dateToTimestamp(dateStr: string): number {
  return startOfDay(parseISO(dateStr)).getTime();
}

interface MultiProviderLineChartProps {
  readonly data: MultiProviderDataPoint[];
  readonly config: {
    garminColor: string;
    whoopColor: string;
  };
  readonly emptyMessage: string;
  readonly garminLabel: string;
  readonly whoopLabel: string;
  readonly unit: string;
  readonly height?: number | `${number}%`;
  readonly yDomain?: [number | string, number | string];
  readonly valueFormatter?: (value: number) => string;
  readonly baselineValue?: number | null;
  readonly showTrends?: boolean;
  readonly bandwidthShort?: number;
  readonly bandwidthLong?: number;
  dateRange?: { start: string; end: string };
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
    dateRange,
  }: MultiProviderLineChartProps) => {
    const hasData = data.some(
      (d) => d.garminValue !== null || d.whoopValue !== null,
    );

    const chartData = useMemo(() => {
      const baseData = data.map((d) => ({
        ...d,
        timestamp: dateToTimestamp(d.date),
      }));

      if (!showTrends || baseData.length === 0) return baseData;

      const withAvg = baseData.map((d) => ({
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
      return <EmptyChartMessage message={emptyMessage} />;
    }

    return (
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart
          data={chartData}
          barGap={0}
          barCategoryGap="20%"
          syncId="health-dashboard"
        >
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
            domain={yDomain}
            className="text-xs"
            allowDecimals={false}
            tickFormatter={(v: number) => Math.round(v).toString()}
          />
          <Tooltip
            labelFormatter={(value) =>
              format(new Date(value as number), "MMM d")
            }
            formatter={(value, name) => {
              if (name === "trendShort" || name === "trendLong") return null;
              const v = value as number | undefined;
              if (v === undefined) return ["-", name];
              if (name === "garminValue") {
                return [`${valueFormatter(v)}${unit}`, garminLabel];
              }
              if (name === "whoopValue") {
                return [`${valueFormatter(v)}${unit}`, whoopLabel];
              }
              return [v, name];
            }}
            contentStyle={chartTooltipStyle}
          />

          <Bar
            dataKey="garminValue"
            fill={config.garminColor}
            radius={[4, 4, 0, 0]}
            name="garminValue"
          />
          <Bar
            dataKey="whoopValue"
            fill={config.whoopColor}
            radius={[4, 4, 0, 0]}
            name="whoopValue"
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

          {showTrends && (
            <Legend
              formatter={(value: string) => {
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
          )}
        </ComposedChart>
      </ResponsiveContainer>
    );
  },
);

MultiProviderLineChart.displayName = "MultiProviderLineChart";
