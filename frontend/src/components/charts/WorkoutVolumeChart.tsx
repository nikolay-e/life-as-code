import { memo, useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { format, parseISO, endOfWeek, eachWeekOfInterval } from "date-fns";
import type { WorkoutData } from "../../types/api";
import { EmptyChartMessage } from "./shared";
import { chartTooltipStyle } from "./chart-config";
import { sortByDateAsc } from "../../lib/chart-utils";

interface WorkoutVolumeChartProps {
  data: WorkoutData[];
}

export const WorkoutVolumeChart = memo(function WorkoutVolumeChart({
  data,
}: WorkoutVolumeChartProps) {
  const weeklyVolume = useMemo(() => {
    if (data.length === 0) return [];

    const sortedData = sortByDateAsc(data);
    const startDate = parseISO(sortedData[0].date);
    const endDate = parseISO(sortedData[sortedData.length - 1].date);
    const weeks = eachWeekOfInterval({ start: startDate, end: endDate });

    return weeks.map((weekStart) => {
      const weekEnd = endOfWeek(weekStart);
      const weekWorkouts = data.filter((w) => {
        const workoutDate = parseISO(w.date);
        return workoutDate >= weekStart && workoutDate <= weekEnd;
      });

      const totalVolume = weekWorkouts.reduce((sum, w) => {
        return sum + (w.total_volume || 0);
      }, 0);

      const totalSets = weekWorkouts.reduce((sum, w) => {
        return sum + (w.total_sets || 0);
      }, 0);

      return {
        week: format(weekStart, "MMM d"),
        volume: Math.round(totalVolume),
        sets: totalSets,
      };
    });
  }, [data]);

  if (weeklyVolume.length === 0) {
    return <EmptyChartMessage message="No workout data available" />;
  }

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={weeklyVolume}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis dataKey="week" className="text-xs" />
        <YAxis
          tickFormatter={(value) =>
            value >= 1000 ? `${(value / 1000).toFixed(0)}k` : value.toString()
          }
          className="text-xs"
        />
        <Tooltip
          formatter={(value, name) => [
            name === "volume"
              ? `${Number(value).toLocaleString()} kg`
              : `${value} sets`,
            name === "volume" ? "Total Volume" : "Sets",
          ]}
          contentStyle={chartTooltipStyle}
        />
        <Bar
          dataKey="volume"
          fill="hsl(var(--primary))"
          radius={[4, 4, 0, 0]}
        />
      </BarChart>
    </ResponsiveContainer>
  );
});
