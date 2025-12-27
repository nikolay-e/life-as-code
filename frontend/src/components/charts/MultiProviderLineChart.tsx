import { memo } from "react";
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
}: MultiProviderLineChartProps) {
  const hasData = data.some(
    (d) => d.garminValue !== null || d.whoopValue !== null,
  );

  if (!hasData) {
    return <EmptyChartMessage message={emptyMessage} />;
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data}>
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
            return value;
          }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
});
