import { memo, useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { format } from "date-fns";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import { LoadingState } from "../../../components/ui/loading-state";
import { ErrorCard } from "../../../components/ui/error-card";
import { chartTooltipStyle } from "../../../components/charts/chart-config";
import { useMLForecasts } from "../../../hooks/useMLForecasts";
import type { MLForecastMetric, MLForecastPoint } from "../../../types/api";
import { dateToTimestamp } from "../../../lib/chart-utils";
import { Sparkles } from "lucide-react";

const FORECAST_HORIZON_DAYS = 14;

const METRIC_COLOR_VARS: Record<string, string> = {
  hrv: "--hrv",
  rhr: "--heart",
  heart_rate: "--heart",
  resting_heart_rate: "--heart",
  sleep: "--sleep",
  sleep_duration: "--sleep",
  steps: "--steps",
  weight: "--weight",
  stress: "--stress",
};

const METRIC_LABELS: Record<string, string> = {
  hrv: "HRV",
  rhr: "Resting Heart Rate",
  heart_rate: "Heart Rate",
  resting_heart_rate: "Resting Heart Rate",
  sleep: "Sleep Duration",
  sleep_duration: "Sleep Duration",
  steps: "Steps",
  weight: "Weight",
  stress: "Stress",
};

function humanizeMetric(metric: string): string {
  const key = metric.toLowerCase().trim();
  if (METRIC_LABELS[key]) return METRIC_LABELS[key];
  return metric
    .split(/[_\s-]+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

function colorForMetric(metric: string): string {
  const key = metric.toLowerCase().trim();
  const cssVar = METRIC_COLOR_VARS[key] ?? "--primary";
  return `hsl(var(${cssVar}))`;
}

interface ForecastChartDatum {
  readonly timestamp: number;
  readonly p10: number | null;
  readonly p50: number | null;
  readonly p90: number | null;
  readonly band: [number | null, number | null];
}

function buildChartData(points: MLForecastPoint[]): ForecastChartDatum[] {
  return points
    .map((p) => ({
      timestamp: dateToTimestamp(p.target_date),
      p10: p.p10,
      p50: p.p50,
      p90: p.p90,
      band: [p.p10, p.p90] as [number | null, number | null],
    }))
    .sort((a, b) => a.timestamp - b.timestamp);
}

interface MLForecastCardProps {
  readonly forecast: MLForecastMetric;
}

const MLForecastCard = memo(({ forecast }: MLForecastCardProps) => {
  const color = colorForMetric(forecast.metric);
  const title = `${humanizeMetric(forecast.metric)} — Next ${String(FORECAST_HORIZON_DAYS)} days forecast`;

  const chartData = useMemo(
    () => buildChartData(forecast.forecasts),
    [forecast.forecasts],
  );

  const gradientId = `ml-forecast-band-${forecast.metric}`;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <div
              className="p-1.5 rounded-lg"
              style={{ backgroundColor: `${color}1f` }}
            >
              <Sparkles className="h-4 w-4" style={{ color }} />
            </div>
            <CardTitle className="text-base">{title}</CardTitle>
          </div>
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-muted text-muted-foreground border-muted-foreground/20">
            {FORECAST_HORIZON_DAYS}d horizon
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.35} />
                <stop offset="100%" stopColor={color} stopOpacity={0.1} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
            <XAxis
              dataKey="timestamp"
              type="number"
              scale="time"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(value: number) =>
                format(new Date(value), "MMM d")
              }
              tick={{ fontSize: 11 }}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              domain={["auto", "auto"]}
              tickFormatter={(v: number) =>
                Number.isFinite(v) ? v.toFixed(0) : ""
              }
            />
            <Tooltip
              contentStyle={chartTooltipStyle}
              labelFormatter={(ts: number) => new Date(ts).toLocaleDateString()}
              formatter={(value, name) => {
                if (Array.isArray(value)) {
                  const [low, high] = value as [number | null, number | null];
                  const lowStr = low == null ? "—" : low.toFixed(1);
                  const highStr = high == null ? "—" : high.toFixed(1);
                  return [`${lowStr} – ${highStr}`, "p10–p90 band"];
                }
                const num = typeof value === "number" ? value : Number(value);
                return [
                  Number.isFinite(num) ? num.toFixed(1) : "—",
                  String(name),
                ];
              }}
            />
            <Area
              type="monotone"
              dataKey="band"
              stroke="none"
              fill={`url(#${gradientId})`}
              isAnimationActive={false}
              name="p10–p90"
            />
            <Line
              type="monotone"
              dataKey="p50"
              stroke={color}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              name="p50 (median)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
});

MLForecastCard.displayName = "MLForecastCard";

export function MLForecastsSection() {
  const { data, isLoading, error } = useMLForecasts(
    undefined,
    FORECAST_HORIZON_DAYS,
  );

  if (error) {
    return (
      <div>
        <h2 className="text-xl font-semibold mb-4">ML Forecasts</h2>
        <ErrorCard message={`Failed to load ML forecasts: ${error.message}`} />
      </div>
    );
  }

  if (isLoading || !data) {
    return (
      <div>
        <h2 className="text-xl font-semibold mb-4">ML Forecasts</h2>
        <LoadingState message="Loading ML forecasts..." />
      </div>
    );
  }

  const renderable = data.forecasts.filter((f) => f.forecasts.length > 0);

  if (!data.has_active || renderable.length === 0) {
    return (
      <div>
        <h2 className="text-xl font-semibold mb-4">ML Forecasts</h2>
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No active ML forecasts yet
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">ML Forecasts</h2>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {renderable.map((forecast) => (
          <MLForecastCard key={forecast.metric} forecast={forecast} />
        ))}
      </div>
    </div>
  );
}
