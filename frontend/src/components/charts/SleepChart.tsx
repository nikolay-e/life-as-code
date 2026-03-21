import { memo, useMemo } from "react";
import {
  Bar,
  BarChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ComposedChart,
  Line,
} from "recharts";
import { format } from "date-fns";
import type { SleepData, WhoopSleepData } from "../../types/api";
import { EmptyChartMessage } from "./shared";
import { chartTooltipStyle, MULTI_PROVIDER_CONFIGS } from "./chart-config";
import { loessSmooth } from "../../lib/statistics";
import { dateToTimestamp } from "../../lib/chart-utils";
import {
  LOESS_BANDWIDTH_SHORT,
  LOESS_BANDWIDTH_LONG,
} from "../../lib/constants";

interface SleepChartProps {
  readonly garminData: SleepData[];
  readonly whoopData?: WhoopSleepData[];
  readonly showBreakdown?: boolean;
  readonly showTrends?: boolean;
  readonly bandwidthShort?: number;
  readonly bandwidthLong?: number;
  readonly height?: number;
  readonly dateRange?: { start: string; end: string };
}

const SLEEP_STAGE_COLORS = {
  deep: "hsl(240 60% 35%)",
  light: "hsl(var(--sleep))",
  rem: "hsl(280 60% 55%)",
  awake: "hsl(var(--stress))",
};

export const SleepChart = memo(
  ({
    garminData,
    whoopData = [],
    showBreakdown = false,
    showTrends = false,
    bandwidthShort = LOESS_BANDWIDTH_SHORT,
    bandwidthLong = LOESS_BANDWIDTH_LONG,
    height = 250,
    dateRange,
  }: SleepChartProps) => {
    const config = MULTI_PROVIDER_CONFIGS.sleep;

    const garminMap = useMemo(
      () => new Map(garminData.map((d) => [d.date, d])),
      [garminData],
    );

    const whoopMap = useMemo(
      () => new Map(whoopData.map((d) => [d.date, d])),
      [whoopData],
    );

    const allDates = useMemo(() => {
      const dates = new Set([...garminMap.keys(), ...whoopMap.keys()]);
      return Array.from(dates).sort(
        (a, b) => new Date(a).getTime() - new Date(b).getTime(),
      );
    }, [garminMap, whoopMap]);

    const chartData = useMemo(
      () =>
        allDates.map((date) => {
          const garmin = garminMap.get(date);
          const whoop = whoopMap.get(date);
          return {
            date,
            timestamp: dateToTimestamp(date),
            garminTotal: garmin?.total_sleep_minutes
              ? garmin.total_sleep_minutes / 60
              : null,
            whoopTotal: whoop?.total_sleep_duration_minutes
              ? whoop.total_sleep_duration_minutes / 60
              : null,
            deep: garmin?.deep_minutes ? garmin.deep_minutes / 60 : 0,
            light: garmin?.light_minutes ? garmin.light_minutes / 60 : 0,
            rem: garmin?.rem_minutes ? garmin.rem_minutes / 60 : 0,
            awake: garmin?.awake_minutes ? garmin.awake_minutes / 60 : 0,
          };
        }),
      [allDates, garminMap, whoopMap],
    );

    const xDomain = useMemo(() => {
      if (dateRange) {
        return [
          dateToTimestamp(dateRange.start),
          dateToTimestamp(dateRange.end),
        ];
      }
      return undefined;
    }, [dateRange]);

    const hasData = chartData.some(
      (d) => d.garminTotal !== null || d.whoopTotal !== null,
    );

    const chartDataWithTrends = useMemo(() => {
      if (!showTrends || chartData.length === 0) return chartData;

      const withAvg = chartData.map((d) => ({
        ...d,
        avgValue:
          d.garminTotal !== null && d.whoopTotal !== null
            ? (d.garminTotal + d.whoopTotal) / 2
            : (d.garminTotal ?? d.whoopTotal),
      }));

      const loessShort = loessSmooth(withAvg, "avgValue", bandwidthShort);
      const loessLong = loessSmooth(withAvg, "avgValue", bandwidthLong);

      return withAvg
        .map((d, i) => ({
          ...d,
          trendShort: loessShort[i]?.loess ?? null,
          trendLong: loessLong[i]?.loess ?? null,
        }))
        .sort((a, b) => a.timestamp - b.timestamp);
    }, [chartData, showTrends, bandwidthShort, bandwidthLong]);

    if (!hasData) {
      return <EmptyChartMessage message="No sleep data available" />;
    }

    const formatHours = (value: number) => `${value.toFixed(1)}h`;

    if (showBreakdown) {
      return (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} syncId="health-dashboard">
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="timestamp"
              tickFormatter={(value: number) =>
                format(new Date(value), "MMM d")
              }
              className="text-xs"
              type="number"
              scale="time"
              domain={xDomain ?? ["dataMin", "dataMax"]}
            />
            <YAxis tickFormatter={formatHours} className="text-xs" />
            <Tooltip
              labelFormatter={(value) =>
                format(new Date(value as number), "MMM d")
              }
              formatter={(value, name) => [
                formatHours(Number(value)),
                String(name).charAt(0).toUpperCase() + String(name).slice(1),
              ]}
              contentStyle={chartTooltipStyle}
            />
            <Legend />
            <Bar
              dataKey="deep"
              stackId="a"
              fill={SLEEP_STAGE_COLORS.deep}
              name="Deep"
              radius={[0, 0, 0, 0]}
            />
            <Bar
              dataKey="light"
              stackId="a"
              fill={SLEEP_STAGE_COLORS.light}
              name="Light"
              radius={[0, 0, 0, 0]}
            />
            <Bar
              dataKey="rem"
              stackId="a"
              fill={SLEEP_STAGE_COLORS.rem}
              name="REM"
              radius={[0, 0, 0, 0]}
            />
            <Bar
              dataKey="awake"
              stackId="a"
              fill={SLEEP_STAGE_COLORS.awake}
              name="Awake"
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      );
    }

    return (
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart
          data={chartDataWithTrends}
          barGap={0}
          barCategoryGap="20%"
          syncId="health-dashboard"
        >
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
            tickFormatter={formatHours}
            className="text-xs"
            domain={[0, 12]}
          />
          <Tooltip
            labelFormatter={(value) =>
              format(new Date(value as number), "MMM d")
            }
            formatter={(value, name) => {
              if (name === "trendShort" || name === "trendLong") return null;
              if (name === "garminTotal") {
                return [formatHours(Number(value)), "Garmin"];
              }
              if (name === "whoopTotal") {
                return [formatHours(Number(value)), "Whoop"];
              }
              return [formatHours(Number(value)), name];
            }}
            contentStyle={chartTooltipStyle}
          />
          {showTrends && (
            <Legend
              formatter={(value: string) => {
                if (value === "garminTotal") return "Garmin";
                if (value === "whoopTotal") return "Whoop";
                if (value === "trendShort") return "Short trend";
                if (value === "trendLong") return "Long trend";
                return value;
              }}
            />
          )}
          <Bar
            dataKey="garminTotal"
            fill={config.garminColor}
            radius={[4, 4, 0, 0]}
            name="garminTotal"
          />
          <Bar
            dataKey="whoopTotal"
            fill={config.whoopColor}
            radius={[4, 4, 0, 0]}
            name="whoopTotal"
          />
          {showTrends && (
            <Line
              type="natural"
              dataKey="trendShort"
              stroke="hsl(var(--foreground) / 0.7)"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              dot={false}
              name="trendShort"
              connectNulls={false}
            />
          )}
          {showTrends && (
            <Line
              type="natural"
              dataKey="trendLong"
              stroke="hsl(var(--foreground) / 0.5)"
              strokeWidth={2.5}
              dot={false}
              name="trendLong"
              connectNulls={false}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    );
  },
);

SleepChart.displayName = "SleepChart";
