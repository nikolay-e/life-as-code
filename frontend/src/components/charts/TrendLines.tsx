import { Line } from "recharts";

interface TrendLineConfig {
  dataKey: string;
  strokeWidth: number;
  strokeDasharray?: string;
  opacity: number;
}

const TREND_LINE_CONFIGS: TrendLineConfig[] = [
  {
    dataKey: "trendShort",
    strokeWidth: 1.5,
    strokeDasharray: "4 4",
    opacity: 0.7,
  },
  { dataKey: "trendLong", strokeWidth: 2.5, opacity: 0.5 },
];

export function renderTrendLines(show: boolean): React.ReactNode[] | null {
  if (!show) return null;

  return TREND_LINE_CONFIGS.map((config) => (
    <Line
      key={config.dataKey}
      type="natural"
      dataKey={config.dataKey}
      stroke={`hsl(var(--foreground) / ${String(config.opacity)})`}
      strokeWidth={config.strokeWidth}
      strokeDasharray={config.strokeDasharray}
      dot={false}
      name={config.dataKey}
      connectNulls={false}
    />
  ));
}
