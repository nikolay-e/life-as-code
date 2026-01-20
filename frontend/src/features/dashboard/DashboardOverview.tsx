import { useState, useMemo } from "react";
import {
  useHealthDataRange,
  useSyncStatus,
  useAutoSync,
} from "../../hooks/useHealthData";
import { Card, CardContent } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { LoadingState } from "../../components/ui/loading-state";
import { ErrorCard } from "../../components/ui/error-card";
import { HRVChart } from "../../components/charts/HRVChart";
import { SleepChart } from "../../components/charts/SleepChart";
import { WeightChart } from "../../components/charts/WeightChart";
import { HeartRateChart } from "../../components/charts/HeartRateChart";
import { StepsChart } from "../../components/charts/StepsChart";
import { RecoveryChart } from "../../components/charts/RecoveryChart";
import { TrainingLoadChart } from "../../components/charts/TrainingLoadChart";
import { CaloriesChart } from "../../components/charts/CaloriesChart";
import { ChartCard } from "../../components/charts/ChartCard";
import { format, subDays, differenceInDays, parseISO } from "date-fns";
import {
  Activity,
  RefreshCw,
  Heart,
  Zap,
  Calendar,
  Moon,
  Scale,
  Footprints,
  Flame,
  type LucideIcon,
} from "lucide-react";
import {
  buildDashboardCards,
  TREND_MODES,
  MODE_ORDER,
  type MetricCardVM,
  type ViewMode,
} from "../../lib/metrics";
import { toTimeMs } from "../../lib/health";
import { calculateDynamicStepsFloor } from "../../lib/health-metrics";
import { getLatestSyncDate } from "../../lib/sync-utils";

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

export function DashboardOverview() {
  const today = new Date();
  const [selectedRange, setSelectedRange] = useState<ViewMode>("recent");
  const [customStartDate, setCustomStartDate] = useState(
    format(subDays(today, 90), "yyyy-MM-dd"),
  );
  const [customEndDate, setCustomEndDate] = useState(
    format(today, "yyyy-MM-dd"),
  );

  const isToday = selectedRange === "today";
  const isCustom = selectedRange === "custom";
  const modeConfig =
    selectedRange !== "today" && selectedRange !== "custom"
      ? TREND_MODES[selectedRange]
      : null;
  const rangeDays = modeConfig?.rangeDays ?? 42;
  const bandwidthShort = modeConfig?.bandwidthShort ?? 0.17;
  const bandwidthLong = modeConfig?.bandwidthLong ?? 0.33;

  const startDate = (() => {
    if (isCustom) return customStartDate;
    if (isToday) return format(today, "yyyy-MM-dd");
    return format(subDays(today, rangeDays), "yyyy-MM-dd");
  })();
  const endDate = (() => {
    if (isCustom) return customEndDate;
    if (isToday) return format(today, "yyyy-MM-dd");
    return format(subDays(today, 1), "yyyy-MM-dd");
  })();

  const selectedDays = Math.max(
    1,
    differenceInDays(parseISO(endDate), parseISO(startDate)) + 1,
  );

  const dateRange = useMemo(
    () => ({ start: startDate, end: endDate }),
    [startDate, endDate],
  );

  const { data, isLoading, error } = useHealthDataRange(startDate, endDate);
  const { data: syncStatus } = useSyncStatus();
  const { isSyncing } = useAutoSync();

  const metricCards: MetricCardVM[] = useMemo(
    () => buildDashboardCards(data ?? null, selectedDays, new Date()),
    [data, selectedDays],
  );

  const stepsFloor = useMemo(() => {
    const steps = data?.steps;
    if (!steps || steps.length === 0) return undefined;
    const stepsDataPoints = steps.map((s) => ({
      date: s.date,
      value: s.total_steps ?? null,
    }));
    return calculateDynamicStepsFloor(stepsDataPoints, rangeDays);
  }, [data, rangeDays]);

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
          <div className="flex items-center gap-1.5 p-1 bg-muted/50 rounded-lg flex-wrap">
            <Calendar className="h-4 w-4 text-muted-foreground ml-2" />
            <Button
              variant={selectedRange === "today" ? "default" : "ghost"}
              size="sm"
              onClick={() => {
                setSelectedRange("today");
              }}
              className="min-w-[60px] flex flex-col h-auto py-1.5"
            >
              <span className="font-medium">Today</span>
              <span className="text-[10px] opacity-70">Latest</span>
            </Button>
            {MODE_ORDER.map((m) => {
              const cfg = TREND_MODES[m];
              return (
                <Button
                  key={m}
                  variant={selectedRange === m ? "default" : "ghost"}
                  size="sm"
                  onClick={() => {
                    setSelectedRange(m);
                  }}
                  className="min-w-[60px] flex flex-col h-auto py-1.5"
                >
                  <span className="font-medium">{cfg.label}</span>
                  <span className="text-[10px] opacity-70">
                    {cfg.description}
                  </span>
                </Button>
              );
            })}
            <Button
              variant={selectedRange === "custom" ? "default" : "ghost"}
              size="sm"
              onClick={() => {
                setSelectedRange("custom");
              }}
              className="min-w-[60px] flex flex-col h-auto py-1.5"
            >
              <span className="font-medium">Custom</span>
              <span className="text-[10px] opacity-70">Range</span>
            </Button>
          </div>
          {isCustom && (
            <div className="flex items-center gap-2 mt-2">
              <Input
                type="date"
                value={customStartDate}
                onChange={(e) => {
                  setCustomStartDate(e.target.value);
                }}
                className="w-36"
              />
              <span className="text-muted-foreground">—</span>
              <Input
                type="date"
                value={customEndDate}
                onChange={(e) => {
                  setCustomEndDate(e.target.value);
                }}
                className="w-36"
              />
              <span className="text-sm text-muted-foreground">
                ({selectedDays} days)
              </span>
            </div>
          )}
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
          title="HRV"
          icon={Activity}
          iconColorClass="text-hrv"
          iconBgClass="bg-hrv-muted"
        >
          <HRVChart
            garminData={data?.hrv ?? []}
            whoopData={data?.whoop_recovery ?? []}
            showTrends
            bandwidthShort={bandwidthShort}
            bandwidthLong={bandwidthLong}
            dateRange={dateRange}
          />
        </ChartCard>

        <ChartCard
          title="Sleep"
          icon={Moon}
          iconColorClass="text-sleep"
          iconBgClass="bg-sleep-muted"
        >
          <SleepChart
            garminData={data?.sleep ?? []}
            whoopData={data?.whoop_sleep ?? []}
            showTrends
            bandwidthShort={bandwidthShort}
            bandwidthLong={bandwidthLong}
            dateRange={dateRange}
          />
        </ChartCard>

        <ChartCard
          title="Weight Trend"
          icon={Scale}
          iconColorClass="text-weight"
          iconBgClass="bg-weight-muted"
        >
          <WeightChart
            data={data?.weight ?? []}
            showTrends
            bandwidthShort={bandwidthShort}
            bandwidthLong={bandwidthLong}
            dateRange={dateRange}
          />
        </ChartCard>

        <ChartCard
          title="Resting HR"
          icon={Activity}
          iconColorClass="text-heart"
          iconBgClass="bg-heart-muted"
        >
          <HeartRateChart
            garminData={data?.heart_rate ?? []}
            whoopData={data?.whoop_recovery ?? []}
            showTrends
            bandwidthShort={bandwidthShort}
            bandwidthLong={bandwidthLong}
            dateRange={dateRange}
          />
        </ChartCard>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard
          title="Daily Steps"
          icon={Footprints}
          iconColorClass="text-steps"
          iconBgClass="bg-steps-muted"
        >
          <StepsChart
            data={data?.steps ?? []}
            showTrends
            bandwidthShort={bandwidthShort}
            bandwidthLong={bandwidthLong}
            dateRange={dateRange}
            stepsFloor={stepsFloor}
          />
        </ChartCard>

        <ChartCard
          title="Recovery / Training Readiness"
          icon={Heart}
          iconColorClass="text-whoop"
          iconBgClass="bg-whoop-muted"
        >
          <RecoveryChart
            whoopData={data?.whoop_recovery ?? []}
            garminData={data?.garmin_training_status ?? []}
            showTrends
            bandwidthShort={bandwidthShort}
            bandwidthLong={bandwidthLong}
            dateRange={dateRange}
          />
        </ChartCard>

        <ChartCard
          title="Training Load"
          icon={Zap}
          iconColorClass="text-training"
          iconBgClass="bg-training-muted"
        >
          <TrainingLoadChart
            whoopData={data?.whoop_cycle ?? []}
            garminData={data?.garmin_training_status ?? []}
            dateRange={dateRange}
          />
        </ChartCard>

        <ChartCard
          title="Daily Calories"
          icon={Flame}
          iconColorClass="text-calories"
          iconBgClass="bg-calories-muted"
        >
          <CaloriesChart
            garminData={data?.garmin_training_status ?? []}
            whoopData={data?.whoop_cycle ?? []}
            energyData={data?.energy ?? []}
            showTrends
            bandwidthShort={bandwidthShort}
            bandwidthLong={bandwidthLong}
            dateRange={dateRange}
          />
        </ChartCard>
      </div>
    </div>
  );
}
