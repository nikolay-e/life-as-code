import { memo, useMemo } from "react";
import {
  ComposedChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from "recharts";
import { format, parseISO } from "date-fns";
import type { WeightData } from "../../types/api";
import { EmptyChartMessage } from "./shared";
import { chartTooltipStyle, TREND_CONFIGS } from "./chart-config";
import { renderTrendLines } from "./TrendLines";
import {
  calculateBiologicalWeightSmoothing,
  calculateBaseline,
  calculateEMA,
} from "../../lib/statistics";

interface WeightChartProps {
  data: WeightData[];
  showTrends?: boolean;
  showBaseline?: boolean;
}

export const WeightChart = memo(function WeightChart({
  data,
  showTrends = false,
  showBaseline = false,
}: WeightChartProps) {
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

      const dataForEMA = smoothedData as unknown as Record<string, unknown>[];
      const ema7 = calculateEMA(dataForEMA, 7, "rawWeight");
      const ema21 = calculateEMA(dataForEMA, 21, "rawWeight");
      const ema60 = calculateEMA(dataForEMA, 60, "rawWeight");

      const withTrends = smoothedData.map((d, i) => ({
        ...d,
        trend7: ema7[i]?.ema ?? null,
        trend21: ema21[i]?.ema ?? null,
        trend60: ema60[i]?.ema ?? null,
      }));

      return {
        chartData: withTrends,
        baseline: baselineData,
        minWeight: min,
        maxWeight: max,
        padding: pad,
        hasData: true,
      };
    }, [data]);

  if (!hasData) {
    return <EmptyChartMessage message="No weight data available" />;
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
          domain={[minWeight - padding, maxWeight + padding]}
          className="text-xs"
          tickFormatter={(v) => v.toFixed(1)}
        />
        <Tooltip
          labelFormatter={(value) => format(parseISO(value as string), "PPP")}
          formatter={(value, name) => {
            const v = value as number | null;
            if (v === null || v === undefined) return ["-", name];
            if (name === "rawWeight") return [`${v.toFixed(1)} kg`, "Weight"];
            if (name === "trend7") return [`${v.toFixed(1)} kg`, "7d avg"];
            if (name === "trend21") return [`${v.toFixed(1)} kg`, "21d avg"];
            if (name === "trend60") return [`${v.toFixed(1)} kg`, "60d avg"];
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

        {/* Data points as scatter */}
        <Scatter
          dataKey="rawWeight"
          fill={config.color}
          name="rawWeight"
          r={2}
        />

        {/* Trend lines */}
        {renderTrendLines(showTrends, "weight")}

        {showTrends && (
          <Legend
            formatter={(value) => {
              if (value === "rawWeight") return "Weight";
              if (value === "trend7") return "7d avg";
              if (value === "trend21") return "21d avg";
              if (value === "trend60") return "60d avg";
              return value;
            }}
          />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
});
