import { memo, useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { format, parseISO } from "date-fns";
import type { SleepData, WhoopSleepData } from "../../types/api";
import { EmptyChartMessage } from "./shared";
import { chartTooltipStyle, MULTI_PROVIDER_CONFIGS } from "./chart-config";
import { sortByDateAsc } from "../../lib/chart-utils";

interface SleepChartProps {
  garminData: SleepData[];
  whoopData?: WhoopSleepData[];
  showBreakdown?: boolean;
}

const SLEEP_STAGE_COLORS = {
  deep: "hsl(240 60% 35%)",
  light: "hsl(var(--sleep))",
  rem: "hsl(280 60% 55%)",
  awake: "hsl(var(--stress))",
};

export const SleepChart = memo(function SleepChart({
  garminData,
  whoopData = [],
  showBreakdown = false,
}: SleepChartProps) {
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

  const hasData = chartData.some(
    (d) => d.garminTotal !== null || d.whoopTotal !== null,
  );

  if (!hasData) {
    return <EmptyChartMessage message="No sleep data available" />;
  }

  const formatHours = (value: number) => `${value.toFixed(1)}h`;

  if (showBreakdown) {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={sortByDateAsc(chartData)}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis
            dataKey="date"
            tickFormatter={(value) => format(parseISO(value), "MMM d")}
            className="text-xs"
          />
          <YAxis tickFormatter={formatHours} className="text-xs" />
          <Tooltip
            labelFormatter={(value) => format(parseISO(value as string), "PPP")}
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
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={chartData} barGap={0} barCategoryGap="20%">
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis
          dataKey="date"
          tickFormatter={(value) => format(parseISO(value), "MMM d")}
          className="text-xs"
        />
        <YAxis
          tickFormatter={formatHours}
          className="text-xs"
          domain={[0, 12]}
        />
        <Tooltip
          labelFormatter={(value) => format(parseISO(value as string), "PPP")}
          formatter={(value, name) => {
            if (value === null) return ["-", name];
            const label = name === "garminTotal" ? "Garmin" : "Whoop";
            return [formatHours(Number(value)), label];
          }}
          contentStyle={chartTooltipStyle}
        />
        <Legend
          formatter={(value) => (value === "garminTotal" ? "Garmin" : "Whoop")}
        />
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
      </BarChart>
    </ResponsiveContainer>
  );
});
