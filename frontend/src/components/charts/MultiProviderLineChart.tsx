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
import { calculateEMA } from "../../lib/statistics";

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
}

export const MultiProviderLineChart = memo(function MultiProviderLineChart({
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
}: MultiProviderLineChartProps) {
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

    const ema7 = calculateEMA(withAvg, 7, "avgValue");
    const ema21 = calculateEMA(withAvg, 21, "avgValue");
    const ema60 = calculateEMA(withAvg, 60, "avgValue");

    return withAvg.map((d, i) => ({
      ...d,
      trend7: ema7[i]?.ema ?? null,
      trend21: ema21[i]?.ema ?? null,
      trend60: ema60[i]?.ema ?? null,
    }));
  }, [data, showTrends]);

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
            if (v === undefined || v === null) return ["-", name];
            if (name === "garminValue")
              return [`${valueFormatter(v)} ${unit}`, garminLabel];
            if (name === "whoopValue")
              return [`${valueFormatter(v)} ${unit}`, whoopLabel];
            if (name === "trend7")
              return [`${valueFormatter(v)} ${unit}`, "7d avg"];
            if (name === "trend21")
              return [`${valueFormatter(v)} ${unit}`, "21d avg"];
            if (name === "trend60")
              return [`${valueFormatter(v)} ${unit}`, "60d avg"];
            return [v, name];
          }}
          contentStyle={chartTooltipStyle}
        />

        {/* Trend lines first (rendered below) */}
        {renderTrendLines(showTrends, "weight")}

        {/* Data points on top */}
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
            if (value === "garminValue") return garminLabel;
            if (value === "whoopValue") return whoopLabel;
            if (value === "trend7") return "7d avg";
            if (value === "trend21") return "21d avg";
            if (value === "trend60") return "60d avg";
            return value;
          }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
});
