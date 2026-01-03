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
import type { WeightData } from "../../types/api";
import { EmptyChartMessage } from "./shared";
import { chartTooltipStyle, TREND_CONFIGS } from "./chart-config";
import { renderTrendLines } from "./TrendLines";
import {
  calculateBiologicalWeightSmoothing,
  calculateBaseline,
  loessSmooth,
} from "../../lib/statistics";

function dateToTimestamp(dateStr: string): number {
  return startOfDay(parseISO(dateStr)).getTime();
}

interface WeightChartProps {
  data: WeightData[];
  showTrends?: boolean;
  showBaseline?: boolean;
  bandwidthShort?: number;
  bandwidthLong?: number;
  dateRange?: { start: string; end: string };
}

export const WeightChart = memo(
  ({
    data,
    showTrends = false,
    showBaseline = false,
    bandwidthShort = 0.17,
    bandwidthLong = 0.33,
    dateRange,
  }: WeightChartProps) => {
    const config = TREND_CONFIGS.weight;

    const { chartData, baseline, minWeight, maxWeight, padding, hasData } =
      useMemo(() => {
        const normalizedData = data.map((d) => ({
          date: d.date,
          weight_kg: d.weight_kg,
        }));

        const smoothedData = calculateBiologicalWeightSmoothing(
          normalizedData,
          "weight_kg",
          {
            smoothingDays: 10,
            maxDailyChangeKg: 0.14,
          },
        );

        const validWeights = smoothedData
          .filter((d) => d.rawWeight !== null)
          .map((d) => d.rawWeight!);

        if (validWeights.length === 0) {
          return {
            chartData: [],
            baseline: null,
            minWeight: 0,
            maxWeight: 100,
            padding: 5,
            hasData: false,
          };
        }

        const min = Math.min(...validWeights);
        const max = Math.max(...validWeights);
        const pad = (max - min) * 0.15 || 2;

        const baselineData = calculateBaseline(normalizedData, 14, "weight_kg");

        const dataForLoess = smoothedData as unknown as ({
          date: string;
        } & Record<string, unknown>)[];
        const loessShort = loessSmooth(
          dataForLoess,
          "rawWeight",
          bandwidthShort,
        );
        const loessLong = loessSmooth(dataForLoess, "rawWeight", bandwidthLong);

        const withTrends = smoothedData.map((d, i) => ({
          ...d,
          timestamp: dateToTimestamp(d.date),
          trendShort: loessShort[i]?.loess ?? null,
          trendLong: loessLong[i]?.loess ?? null,
        }));

        return {
          chartData: withTrends,
          baseline: baselineData,
          minWeight: min,
          maxWeight: max,
          padding: pad,
          hasData: true,
        };
      }, [data, bandwidthShort, bandwidthLong]);

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
      <ResponsiveContainer width="100%" height={250}>
        <ComposedChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis
            dataKey="timestamp"
            tickFormatter={(value) => format(new Date(value), "MMM d")}
            className="text-xs"
            type="number"
            scale="time"
            domain={xDomain ?? ["dataMin", "dataMax"]}
          />
          <YAxis
            domain={[minWeight - padding, maxWeight + padding]}
            className="text-xs"
            tickFormatter={(v) => v.toFixed(1)}
          />
          <Tooltip
            labelFormatter={(value) => format(new Date(value as number), "PPP")}
            formatter={(value, name) => {
              const v = value as number | null;
              if (v === null) return ["-", name];
              if (name === "rawWeight") return [`${v.toFixed(1)} kg`, "Weight"];
              if (name === "trendShort") {
                return [`${v.toFixed(1)} kg`, "Short trend"];
              }
              if (name === "trendLong") {
                return [`${v.toFixed(1)} kg`, "Long trend"];
              }
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

          <Line
            type="linear"
            dataKey="rawWeight"
            stroke="transparent"
            strokeWidth={0}
            dot={{ fill: config.color, r: 2, strokeWidth: 0 }}
            activeDot={{ fill: config.color, r: 4, strokeWidth: 0 }}
            name="rawWeight"
            isAnimationActive={false}
          />

          {renderTrendLines(showTrends)}

          {showTrends && (
            <Legend
              formatter={(value) => {
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
