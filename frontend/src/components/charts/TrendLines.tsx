import { Line } from "recharts";

interface TrendLineConfig {
  dataKey: string;
  strokeWidth: number;
  strokeDasharray?: string;
}

const TREND_LINE_CONFIGS: TrendLineConfig[] = [
  { dataKey: "shortTermTrend", strokeWidth: 1.5, strokeDasharray: "4 4" },
  { dataKey: "longTermTrend", strokeWidth: 2, strokeDasharray: "8 4" },
  { dataKey: "longerTermTrend", strokeWidth: 2.5 },
];

const WEIGHT_TREND_CONFIGS: TrendLineConfig[] = [
  { dataKey: "trend7", strokeWidth: 1.5, strokeDasharray: "4 4" },
  { dataKey: "trend21", strokeWidth: 2, strokeDasharray: "8 4" },
  { dataKey: "trend60", strokeWidth: 2.5 },
];

export function renderTrendLines(
  show: boolean,
  variant: "standard" | "weight" = "standard",
): React.ReactNode[] | null {
  if (!show) return null;

  const configs =
    variant === "weight" ? WEIGHT_TREND_CONFIGS : TREND_LINE_CONFIGS;

  return configs.map((config) => (
    <Line
      key={config.dataKey}
      type="natural"
      dataKey={config.dataKey}
      stroke="hsl(var(--foreground))"
      strokeWidth={config.strokeWidth}
      strokeDasharray={config.strokeDasharray}
      dot={false}
      name={config.dataKey}
      connectNulls={false}
    />
  ));
}
