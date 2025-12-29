import { memo, useMemo } from "react";
import {
  LineChart,
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
  showDots?: boolean;
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
  showDots = false,
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

    return withAvg.map((d, i) => ({
      ...d,
      trend7: ema7[i]?.ema ?? null,
      trend21: ema21[i]?.ema ?? null,
    }));
  }, [data, showTrends]);

  if (!hasData) {
    return <EmptyChartMessage message={emptyMessage} />;
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData}>
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
              return [`${valueFormatter(v)} ${unit}`, "7-day avg"];
            if (name === "trend21")
              return [`${valueFormatter(v)} ${unit}`, "21-day avg"];
            return [v, name];
          }}
          contentStyle={chartTooltipStyle}
        />

        <Line
          type="monotone"
          dataKey="garminValue"
          stroke={config.garminColor}
          strokeWidth={2}
          dot={showDots ? { r: 3 } : false}
          activeDot={{ r: showDots ? 5 : 4 }}
          name="garminValue"
          connectNulls
        />

        <Line
          type="monotone"
          dataKey="whoopValue"
          stroke={config.whoopColor}
          strokeWidth={2}
          dot={showDots ? { r: 3 } : false}
          activeDot={{ r: showDots ? 5 : 4 }}
          name="whoopValue"
          connectNulls
        />

        {showTrends && (
          <Line
            type="monotone"
            dataKey="trend7"
            stroke="hsl(var(--foreground) / 0.7)"
            strokeWidth={2.5}
            strokeDasharray="6 4"
            dot={false}
            name="trend7"
            connectNulls
          />
        )}

        {showTrends && (
          <Line
            type="monotone"
            dataKey="trend21"
            stroke="hsl(var(--foreground) / 0.5)"
            strokeWidth={2}
            strokeDasharray="10 5"
            dot={false}
            name="trend21"
            connectNulls
          />
        )}

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
            if (value === "trend7") return "7-day avg";
            if (value === "trend21") return "21-day avg";
            return value;
          }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
});
