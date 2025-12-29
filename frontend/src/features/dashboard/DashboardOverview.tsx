import { useState, useMemo } from "react";
import {
  useHealthData,
  useSyncStatus,
  useAutoSync,
} from "../../hooks/useHealthData";
import { Card, CardContent } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { LoadingState } from "../../components/ui/loading-state";
import { ErrorCard } from "../../components/ui/error-card";
import { HRVChart } from "../../components/charts/HRVChart";
import { SleepChart } from "../../components/charts/SleepChart";
import { WeightChart } from "../../components/charts/WeightChart";
import { HeartRateChart } from "../../components/charts/HeartRateChart";
import { StepsChart } from "../../components/charts/StepsChart";
import { WhoopRecoveryChart } from "../../components/charts/WhoopRecoveryChart";
import { StressChart } from "../../components/charts/StressChart";
import { CaloriesChart } from "../../components/charts/CaloriesChart";
import { ChartCard } from "../../components/charts/ChartCard";
import { format } from "date-fns";
import {
  Activity,
  RefreshCw,
  Heart,
  Brain,
  Calendar,
  Moon,
  Scale,
  Footprints,
  Flame,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { buildDashboardCards, type MetricCardVM } from "../../lib/metrics";
import { toTimeMs } from "../../lib/health";

function getLatestSyncDate(
  syncs: Array<{ last_sync_date: string | null }> | undefined,
): string | null {
  if (!syncs) return null;
  const withDates = syncs.filter((s) => s.last_sync_date);
  if (withDates.length === 0) return null;
  const latest = withDates.sort(
    (a, b) =>
      new Date(b.last_sync_date!).getTime() -
      new Date(a.last_sync_date!).getTime(),
  )[0];
  return latest.last_sync_date;
}

interface MetricCardProps {
  title: string;
  value: string;
  subtitle: string;
  icon: LucideIcon;
  colorClass: string;
  bgClass: string;
}

function MetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
  colorClass,
  bgClass,
}: MetricCardProps) {
  return (
    <Card className="overflow-hidden">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="text-3xl font-bold tracking-tight">{value}</p>
            <p className="text-xs text-muted-foreground">{subtitle}</p>
          </div>
          <div className={`p-2.5 rounded-xl ${bgClass}`}>
            <Icon className={`h-5 w-5 ${colorClass}`} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

const TIME_RANGES = [
  { label: "Today", days: 1, description: "Latest" },
  { label: "Week", days: 7, description: "7 days" },
  { label: "Month", days: 30, description: "30 days" },
  { label: "Quarter", days: 90, description: "90 days" },
  { label: "Year", days: 365, description: "12 months" },
  { label: "All", days: 3650, description: "Full history" },
];

export function DashboardOverview() {
  const [selectedDays, setSelectedDays] = useState(90);
  const isToday = selectedDays === 1;
  const { data, isLoading, error } = useHealthData(selectedDays, !isToday);
  const { data: syncStatus } = useSyncStatus();
  const { isSyncing } = useAutoSync();

  const metricCards: MetricCardVM[] = useMemo(
    () => buildDashboardCards(data ?? null, selectedDays, new Date()),
    [data, selectedDays],
  );

  if (isLoading) {
    return <LoadingState message="Loading health data..." />;
  }

  if (error) {
    return (
      <ErrorCard message={`Failed to load health data: ${error.message}`} />
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              Health Dashboard
            </h1>
            <p className="text-muted-foreground mt-1">
              Track your daily health metrics
            </p>
          </div>
          <div className="flex items-center gap-1.5 p-1 bg-muted/50 rounded-lg">
            <Calendar className="h-4 w-4 text-muted-foreground ml-2" />
            {TIME_RANGES.map((range) => (
              <Button
                key={range.days}
                variant={selectedDays === range.days ? "default" : "ghost"}
                size="sm"
                onClick={() => setSelectedDays(range.days)}
                className="min-w-[70px] flex flex-col h-auto py-1.5"
              >
                <span className="font-medium">{range.label}</span>
                <span className="text-[10px] opacity-70">
                  {range.description}
                </span>
              </Button>
            ))}
          </div>
        </div>
        {(() => {
          const lastSync = getLatestSyncDate(syncStatus);
          if (isSyncing) {
            return (
              <div className="flex items-center gap-2 text-sm text-primary">
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                <span>Syncing data...</span>
              </div>
            );
          }
          return lastSync ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <RefreshCw className="h-3.5 w-3.5" />
              <span>
                Last sync: {format(new Date(toTimeMs(lastSync)), "PPp")}
              </span>
            </div>
          ) : null;
        })()}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {metricCards.map((vm) => (
          <MetricCard
            key={vm.key}
            title={vm.title}
            value={vm.value}
            subtitle={vm.subtitle}
            icon={vm.icon}
            colorClass={vm.colorClass}
            bgClass={vm.bgClass}
          />
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard
          title="HRV (Garmin + Whoop)"
          icon={Activity}
          iconColorClass="text-hrv"
          iconBgClass="bg-hrv-muted"
        >
          <HRVChart
            garminData={data?.hrv ?? []}
            whoopData={data?.whoop_recovery ?? []}
          />
        </ChartCard>

        <ChartCard
          title="Sleep (Garmin + Whoop)"
          icon={Moon}
          iconColorClass="text-sleep"
          iconBgClass="bg-sleep-muted"
        >
          <SleepChart
            garminData={data?.sleep ?? []}
            whoopData={data?.whoop_sleep ?? []}
          />
        </ChartCard>

        <ChartCard
          title="Weight Trend"
          icon={Scale}
          iconColorClass="text-weight"
          iconBgClass="bg-weight-muted"
        >
          <WeightChart data={data?.weight ?? []} />
        </ChartCard>

        <ChartCard
          title="Resting HR (Garmin + Whoop)"
          icon={Activity}
          iconColorClass="text-heart"
          iconBgClass="bg-heart-muted"
        >
          <HeartRateChart
            garminData={data?.heart_rate ?? []}
            whoopData={data?.whoop_recovery ?? []}
          />
        </ChartCard>
      </div>

      <ChartCard
        title="Daily Steps"
        icon={Footprints}
        iconColorClass="text-steps"
        iconBgClass="bg-steps-muted"
      >
        <StepsChart data={data?.steps ?? []} />
      </ChartCard>

      <ChartCard
        title="Whoop Recovery"
        icon={Heart}
        iconColorClass="text-whoop"
        iconBgClass="bg-whoop-muted"
      >
        <WhoopRecoveryChart data={data?.whoop_recovery ?? []} />
      </ChartCard>

      <ChartCard
        title="Stress Levels"
        icon={Brain}
        iconColorClass="text-stress"
        iconBgClass="bg-stress-muted"
      >
        <StressChart data={data?.stress ?? []} showTrends />
      </ChartCard>

      <ChartCard
        title="Daily Calories (Garmin + Whoop)"
        icon={Flame}
        iconColorClass="text-calories"
        iconBgClass="bg-calories-muted"
      >
        <CaloriesChart
          garminData={data?.garmin_training_status ?? []}
          whoopData={data?.whoop_cycle ?? []}
        />
      </ChartCard>
    </div>
  );
}
