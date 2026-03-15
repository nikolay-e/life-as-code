import { memo, useMemo } from "react";
import {
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ComposedChart,
  Line,
  ReferenceLine,
} from "recharts";
import { format, parseISO, startOfDay } from "date-fns";
import type { WhoopCycleData, GarminTrainingStatusData } from "../../types/api";
import { EmptyChartMessage } from "./shared";
import { chartTooltipStyle } from "./chart-config";
import { toLocalDayKey } from "../../lib/health/date";

function fuseStrainValues(
  whoopCycles: WhoopCycleData[],
  garminTraining: GarminTrainingStatusData[],
): { date: string; value: number | null }[] {
  const whoopByDay = new Map(
    whoopCycles
      .filter((d) => d.strain !== null)
      .map((d) => [toLocalDayKey(d.date), d.strain as number]),
  );

  const garminRaw = garminTraining
    .filter((d) => d.acute_training_load !== null)
    .map((d) => ({
      date: toLocalDayKey(d.date),
      value: d.acute_training_load as number,
    }));

  const overlapping = garminRaw.filter((g) => whoopByDay.has(g.date));
  const garminByDay = new Map<string, number>();

  if (overlapping.length >= 14) {
    const sortedGarmin = overlapping.map((g) => g.value).sort((a, b) => a - b);
    const sortedWhoop = overlapping
      .map((g) => whoopByDay.get(g.date))
      .filter((v): v is number => v !== undefined)
      .sort((a, b) => a - b);

    const normalize = (val: number): number => {
      const below = sortedGarmin.filter((v) => v < val).length;
      const equal = sortedGarmin.filter((v) => v === val).length;
      const p = (below + equal * 0.5) / sortedGarmin.length;
      const idx = p * (sortedWhoop.length - 1);
      const lo = Math.floor(idx);
      const hi = Math.ceil(idx);
      return lo === hi
        ? sortedWhoop[lo]
        : sortedWhoop[lo] * (1 - (idx - lo)) + sortedWhoop[hi] * (idx - lo);
    };

    for (const g of garminRaw) {
      garminByDay.set(g.date, normalize(g.value));
    }
  } else {
    for (const g of garminRaw) {
      garminByDay.set(g.date, g.value);
    }
  }

  const allDates = new Set([...whoopByDay.keys(), ...garminByDay.keys()]);
  return [...allDates]
    .map((date) => ({
      date,
      value: whoopByDay.get(date) ?? garminByDay.get(date) ?? null,
    }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

function dateToTimestamp(dateStr: string): number {
  return startOfDay(parseISO(dateStr)).getTime();
}

interface TrainingLoadPoint {
  timestamp: number;
  date: string;
  acuteLoad: number | null;
  chronicLoad: number | null;
  acwr: number | null;
  dailyStrain: number | null;
}

function calculateRollingMean(
  values: (number | null)[],
  index: number,
  windowSize: number,
): number | null {
  const startIdx = Math.max(0, index - windowSize + 1);
  const windowValues: number[] = [];

  for (let i = startIdx; i <= index; i++) {
    if (values[i] !== null) {
      windowValues.push(values[i] as number);
    }
  }

  if (windowValues.length < Math.min(3, windowSize)) {
    return null;
  }

  return windowValues.reduce((a, b) => a + b, 0) / windowValues.length;
}

function getAcwrZone(acwr: number): string {
  if (acwr < 0.8) return "Undertrained";
  if (acwr <= 1.3) return "Optimal";
  if (acwr <= 1.5) return "High Risk";
  return "Danger";
}

interface TrainingLoadChartProps {
  whoopData: WhoopCycleData[];
  garminData: GarminTrainingStatusData[];
  showTrends?: boolean;
  height?: number;
  dateRange?: { start: string; end: string };
}

export const TrainingLoadChart = memo(
  ({
    whoopData,
    garminData,
    height = 250,
    dateRange,
  }: TrainingLoadChartProps) => {
    const chartData = useMemo(() => {
      const fusedStrain = fuseStrainValues(whoopData, garminData);

      if (fusedStrain.length === 0) {
        return [];
      }

      const sortedData = [...fusedStrain].sort(
        (a, b) => dateToTimestamp(a.date) - dateToTimestamp(b.date),
      );

      const dailyStrainValues = sortedData.map((d) => d.value);

      const points: TrainingLoadPoint[] = sortedData.map((d, idx) => {
        const acuteLoad = calculateRollingMean(dailyStrainValues, idx, 7);
        const chronicLoad = calculateRollingMean(dailyStrainValues, idx, 30);

        let acwr: number | null = null;
        if (acuteLoad !== null && chronicLoad !== null && chronicLoad > 0.1) {
          acwr = acuteLoad / chronicLoad;
        }

        return {
          timestamp: dateToTimestamp(d.date),
          date: toLocalDayKey(d.date),
          acuteLoad,
          chronicLoad,
          acwr,
          dailyStrain: d.value,
        };
      });

      return points;
    }, [whoopData, garminData]);

    const xDomain = useMemo(() => {
      if (dateRange) {
        return [
          dateToTimestamp(dateRange.start),
          dateToTimestamp(dateRange.end),
        ];
      }
      return undefined;
    }, [dateRange]);

    const { yDomainLoad, yDomainAcwr } = useMemo(() => {
      const acuteValues = chartData
        .map((d) => d.acuteLoad)
        .filter((v): v is number => v !== null);
      const chronicValues = chartData
        .map((d) => d.chronicLoad)
        .filter((v): v is number => v !== null);
      const allLoads = [...acuteValues, ...chronicValues];

      const maxLoad = allLoads.length > 0 ? Math.max(...allLoads) : 21;
      const loadCeiling = Math.ceil(maxLoad * 1.1);

      return {
        yDomainLoad: [0, loadCeiling] as [number, number],
        yDomainAcwr: [0.4, 2.0] as [number, number],
      };
    }, [chartData]);

    const hasData = chartData.some(
      (d) => d.acuteLoad !== null || d.chronicLoad !== null,
    );

    if (!hasData) {
      return <EmptyChartMessage message="No training load data available" />;
    }

    return (
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={chartData} syncId="health-dashboard">
          <defs>
            <linearGradient id="acuteGradient" x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="5%"
                stopColor="hsl(var(--training-acute))"
                stopOpacity={0.6}
              />
              <stop
                offset="95%"
                stopColor="hsl(var(--training-acute))"
                stopOpacity={0.1}
              />
            </linearGradient>
            <linearGradient id="chronicGradient" x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="5%"
                stopColor="hsl(var(--training-chronic))"
                stopOpacity={0.4}
              />
              <stop
                offset="95%"
                stopColor="hsl(var(--training-chronic))"
                stopOpacity={0.05}
              />
            </linearGradient>
          </defs>

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
            yAxisId="load"
            domain={yDomainLoad}
            className="text-xs"
            tickFormatter={(v: number) => v.toFixed(0)}
          />

          <YAxis
            yAxisId="acwr"
            orientation="right"
            domain={yDomainAcwr}
            className="text-xs"
            tickFormatter={(v: number) => v.toFixed(1)}
            tick={{ fill: "hsl(var(--muted-foreground))" }}
          />

          <Tooltip
            labelFormatter={(value) =>
              format(new Date(value as number), "MMM d, yyyy")
            }
            formatter={(value, name) => {
              const v = value as number | null;
              if (v === null) return ["-", name];

              if (name === "acuteLoad") {
                return [v.toFixed(1), "Acute Load (7d)"];
              }
              if (name === "chronicLoad") {
                return [v.toFixed(1), "Chronic Load (30d)"];
              }
              if (name === "acwr") {
                const zone = getAcwrZone(v);
                return [`${v.toFixed(2)} (${zone})`, "ACWR"];
              }
              return [v.toFixed(1), String(name)];
            }}
            contentStyle={chartTooltipStyle}
          />

          <ReferenceLine
            yAxisId="acwr"
            y={0.8}
            stroke="hsl(var(--training-acute))"
            strokeDasharray="3 3"
            strokeOpacity={0.5}
          />
          <ReferenceLine
            yAxisId="acwr"
            y={1.3}
            stroke="hsl(var(--acwr-caution))"
            strokeDasharray="3 3"
            strokeOpacity={0.5}
          />
          <ReferenceLine
            yAxisId="acwr"
            y={1.5}
            stroke="hsl(var(--acwr-danger))"
            strokeDasharray="3 3"
            strokeOpacity={0.5}
          />

          <Area
            yAxisId="load"
            type="monotone"
            dataKey="chronicLoad"
            stroke="hsl(var(--training-chronic))"
            fill="url(#chronicGradient)"
            strokeWidth={1.5}
            name="chronicLoad"
            connectNulls={false}
          />

          <Area
            yAxisId="load"
            type="monotone"
            dataKey="acuteLoad"
            stroke="hsl(var(--training-acute))"
            fill="url(#acuteGradient)"
            strokeWidth={2}
            name="acuteLoad"
            connectNulls={false}
          />

          <Line
            yAxisId="acwr"
            type="monotone"
            dataKey="acwr"
            stroke="hsl(var(--acwr-optimal))"
            strokeWidth={2}
            dot={false}
            name="acwr"
            connectNulls={false}
          />

          <Legend
            formatter={(value: string) => {
              if (value === "acuteLoad") return "Acute (7d)";
              if (value === "chronicLoad") return "Chronic (30d)";
              if (value === "acwr") return "ACWR";
              return value;
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    );
  },
);

TrainingLoadChart.displayName = "TrainingLoadChart";
