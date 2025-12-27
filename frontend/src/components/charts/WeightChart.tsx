import { memo, useMemo } from "react";
import {
  ComposedChart,
  Line,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { format, parseISO } from "date-fns";
import type { WeightData } from "../../types/api";
import { EmptyChartMessage } from "./shared";
import { chartTooltipStyle, TREND_CONFIGS } from "./chart-config";
import {
  calculateBiologicalWeightSmoothing,
  calculateBaseline,
} from "../../lib/statistics";

interface WeightChartProps {
  data: WeightData[];
  showTrends?: boolean;
  showBaseline?: boolean;
}

export const WeightChart = memo(function WeightChart({
  data,
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

      return {
        chartData: smoothedData,
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
            if (name === "rawWeight") return [`${v.toFixed(1)} kg`, "Measured"];
            if (name === "smoothedWeight")
              return [`${v.toFixed(1)} kg`, "True Weight"];
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
          type="monotone"
          dataKey="smoothedWeight"
          stroke={config.color}
          strokeWidth={2.5}
          dot={false}
          activeDot={false}
          name="smoothedWeight"
          connectNulls
        />

        <Scatter
          dataKey="rawWeight"
          fill={config.color}
          fillOpacity={0.5}
          name="rawWeight"
          r={4}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
});
