import { useState, useMemo } from "react";
import { useHealthData } from "@/hooks/useHealthData";
import WeightChart from "@/components/charts/WeightChart";
import HeartRateHRVChart from "@/components/charts/HeartRateHRVChart";
import SleepChart from "@/components/charts/SleepChart";
import WorkoutChart from "@/components/charts/WorkoutChart";
import StressChart from "@/components/charts/StressChart";
import EnergyChart from "@/components/charts/EnergyChart";
import StepsChart from "@/components/charts/StepsChart";

function getDefaultDateRange() {
  const endDate = new Date();
  const startDate = new Date();
  startDate.setDate(startDate.getDate() - 90);
  return {
    startDate: startDate.toISOString().split("T")[0],
    endDate: endDate.toISOString().split("T")[0],
  };
}

export default function DashboardPage() {
  const defaultRange = useMemo(() => getDefaultDateRange(), []);
  const [dateRange, setDateRange] = useState(defaultRange);
  const { data, isLoading, error } = useHealthData(dateRange);

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg">
        Failed to load health data. Please try again.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Health Dashboard</h2>
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <label htmlFor="start-date" className="text-sm text-gray-600">
              From:
            </label>
            <input
              id="start-date"
              type="date"
              value={dateRange.startDate}
              onChange={(e) =>
                setDateRange((prev) => ({ ...prev, startDate: e.target.value }))
              }
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
            />
          </div>
          <div className="flex items-center space-x-2">
            <label htmlFor="end-date" className="text-sm text-gray-600">
              To:
            </label>
            <input
              id="end-date"
              type="date"
              value={dateRange.endDate}
              onChange={(e) =>
                setDateRange((prev) => ({ ...prev, endDate: e.target.value }))
              }
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
            />
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {[...Array(7)].map((_, i) => (
            <div
              key={i}
              className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 h-80 animate-pulse"
            >
              <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
              <div className="h-full bg-gray-100 rounded"></div>
            </div>
          ))}
        </div>
      ) : data ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <WeightChart data={data.weight} />
          <HeartRateHRVChart
            heartRateData={data.heart_rate}
            hrvData={data.hrv}
          />
          <SleepChart data={data.sleep} />
          <WorkoutChart data={data.workouts} />
          <StressChart data={data.stress} />
          <EnergyChart data={data.energy} />
          <StepsChart data={data.steps} />
        </div>
      ) : null}
    </div>
  );
}
