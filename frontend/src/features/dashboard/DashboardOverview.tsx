import { useState, useMemo } from "react";
import {
  useHealthDataRange,
  useSyncStatus,
  useAutoSync,
} from "../../hooks/useHealthData";
import { Card, CardContent } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { DateRangePicker } from "../../components/ui/date-range-picker";
import { LoadingState } from "../../components/ui/loading-state";
import { ErrorCard } from "../../components/ui/error-card";
import { InterventionQuickAdd } from "./InterventionQuickAdd";
import { HRVChart } from "../../components/charts/HRVChart";
import { SleepChart } from "../../components/charts/SleepChart";
import { WeightChart } from "../../components/charts/WeightChart";
import { HeartRateChart } from "../../components/charts/HeartRateChart";
import { StepsChart } from "../../components/charts/StepsChart";
import { RecoveryChart } from "../../components/charts/RecoveryChart";
import { TrainingLoadChart } from "../../components/charts/TrainingLoadChart";
import { CaloriesChart } from "../../components/charts/CaloriesChart";
import { ChartCard } from "../../components/charts/ChartCard";
import { ChartErrorBoundary } from "../../components/charts/ChartErrorBoundary";
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
  Loader2,
  type LucideIcon,
} from "lucide-react";
import {
  METRIC_REGISTRY,
  TREND_MODES,
  MODE_ORDER,
  type ViewMode,
} from "../../lib/metrics";
import { DASHBOARD_METRIC_KEYS } from "../../lib/metrics/keys";
import { toTimeMs } from "../../lib/health";
import { getLatestSyncDate } from "../../lib/sync-utils";
import { useAnalytics } from "../../hooks/useAnalytics";
import { useInterventions } from "../../hooks/useHealthLog";
import { interventionsToAnnotations } from "../../components/charts/annotations";
import { useToday } from "../../hooks/useToday";
import {
  LOESS_BANDWIDTH_SHORT,
  LOESS_BANDWIDTH_LONG,
} from "../../lib/constants";

const DASHBOARD_KEYS = new Set<string>(DASHBOARD_METRIC_KEYS);

interface MetricCardProps {
  readonly title: string;
  readonly value: string;
  readonly subtitle: string;
  readonly icon: LucideIcon;
  readonly colorClass: string;
  readonly bgClass: string;
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
  const today = useToday();
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
  const bandwidthShort = modeConfig?.bandwidthShort ?? LOESS_BANDWIDTH_SHORT;
  const bandwidthLong = modeConfig?.bandwidthLong ?? LOESS_BANDWIDTH_LONG;

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

  const { data, isLoading, isFetching, error } = useHealthDataRange(
    startDate,
    endDate,
  );
  const { data: syncStatus } = useSyncStatus();
  const { isSyncing } = useAutoSync();
  const analyticsMode =
    selectedRange === "today" || selectedRange === "custom"
      ? "recent"
      : selectedRange;
  const { data: analyticsData } = useAnalytics(analyticsMode);
  const { data: interventionsData } = useInterventions();
  const annotations = useMemo(
    () => interventionsToAnnotations(interventionsData),
    [interventionsData],
  );
  const hrvBaseline = analyticsData?.metric_baselines.hrv;
  const rhrBaseline = analyticsData?.metric_baselines.rhr;

  const stepsFloor = useMemo(() => {
    const steps = data?.steps;
    if (!steps || steps.length === 0) return undefined;
    const window = Math.min(rangeDays, 90);
    const vals = steps
      .slice(-window)
      .map((s) => s.total_steps)
      .filter((v): v is number => v !== null);
    if (vals.length < 14) return undefined;
    const sorted = [...vals].sort((a, b) => a - b);
    const idx = Math.floor(sorted.length * 0.1);
    return Math.round(sorted[Math.min(idx, sorted.length - 1)]);
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
          <div className="flex flex-col gap-2 sm:items-end">
            <div className="flex items-center gap-1 p-1 bg-muted/50 rounded-lg overflow-x-auto sm:flex-wrap sm:overflow-visible -mx-1 px-1">
              <Calendar className="h-4 w-4 text-muted-foreground ml-2 shrink-0" />
              <Button
                variant={selectedRange === "today" ? "default" : "ghost"}
                size="sm"
                onClick={() => {
                  setSelectedRange("today");
                }}
                className="min-w-[60px] flex flex-col h-auto py-1.5 shrink-0"
              >
                <span className="font-medium">Today</span>
                <span className="text-[10px]">Latest</span>
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
                    className="min-w-[60px] flex flex-col h-auto py-1.5 shrink-0"
                  >
                    <span className="font-medium">{cfg.label}</span>
                    <span className="text-[10px]">{cfg.description}</span>
                  </Button>
                );
              })}
              <Button
                variant={selectedRange === "custom" ? "default" : "ghost"}
                size="sm"
                onClick={() => {
                  setSelectedRange("custom");
                }}
                className="min-w-[60px] flex flex-col h-auto py-1.5 shrink-0"
              >
                <span className="font-medium">Custom</span>
                <span className="text-[10px]">Range</span>
              </Button>
            </div>
            {isCustom && (
              <div className="flex flex-wrap items-center gap-2">
                <DateRangePicker
                  start={customStartDate}
                  end={customEndDate}
                  onChange={({ start, end }) => {
                    setCustomStartDate(start);
                    setCustomEndDate(end);
                  }}
                  disabled={{ after: today }}
                />
                <span className="text-xs text-muted-foreground">
                  ({selectedDays} days)
                </span>
              </div>
            )}
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
          return (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              {isFetching ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
              ) : (
                lastSync && <RefreshCw className="h-3.5 w-3.5" />
              )}
              {lastSync && (
                <span>
                  Last sync: {format(new Date(toTimeMs(lastSync)), "PPp")}
                </span>
              )}
            </div>
          );
        })()}
      </div>

      <InterventionQuickAdd />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {METRIC_REGISTRY.filter((def) => DASHBOARD_KEYS.has(def.key)).map(
          (def) => {
            const baseline = analyticsData?.metric_baselines[def.key];
            const currentVal = baseline?.current_value ?? null;
            const shortAvg = baseline?.short_term_mean ?? null;
            const longAvg = baseline?.mean ?? null;
            const latencyDays = baseline?.latency_days ?? null;
            const staleThreshold = def.key === "weight" ? 3 : 2;
            const isStale =
              latencyDays !== null && latencyDays > staleThreshold;
            const showCurrent =
              selectedRange === "today" || selectedRange === "custom";
            const displayValue = showCurrent
              ? currentVal
              : (shortAvg ?? currentVal);
            const shortLabel = modeConfig
              ? `${String(modeConfig.shortTerm)}d avg`
              : "7d avg";
            const baselineLabel = modeConfig
              ? `${String(modeConfig.baseline)}d baseline`
              : null;
            const freshSubtitle = (() => {
              if (showCurrent) {
                return shortAvg === null
                  ? "Current"
                  : `7d avg: ${def.format(shortAvg)}`;
              }
              if (longAvg !== null) {
                return `${shortLabel} · ${baselineLabel ?? "baseline"}: ${def.format(longAvg)}`;
              }
              return shortLabel;
            })();
            const subtitle = isStale
              ? `${String(latencyDays)}d ago`
              : freshSubtitle;
            return (
              <MetricCard
                key={def.key}
                title={def.title}
                value={def.format(displayValue)}
                subtitle={subtitle}
                icon={def.icon}
                colorClass={isStale ? "text-warning" : def.iconColorClass}
                bgClass={isStale ? "bg-warning/10" : def.iconBgClass}
              />
            );
          },
        )}
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <ChartCard
          title="HRV"
          icon={Activity}
          iconColorClass="text-hrv"
          iconBgClass="bg-hrv-muted"
        >
          <ChartErrorBoundary resetKeys={[startDate, endDate]}>
            <HRVChart
              data={data?.hrv ?? []}
              showTrends
              bandwidthShort={bandwidthShort}
              bandwidthLong={bandwidthLong}
              dateRange={dateRange}
              annotations={annotations}
              baselineMean={hrvBaseline?.mean}
              baselineStd={hrvBaseline?.std}
            />
          </ChartErrorBoundary>
        </ChartCard>

        <ChartCard
          title="Sleep"
          icon={Moon}
          iconColorClass="text-sleep"
          iconBgClass="bg-sleep-muted"
        >
          <ChartErrorBoundary resetKeys={[startDate, endDate]}>
            <SleepChart
              data={data?.sleep ?? []}
              showTrends
              bandwidthShort={bandwidthShort}
              bandwidthLong={bandwidthLong}
              dateRange={dateRange}
            />
          </ChartErrorBoundary>
        </ChartCard>

        <ChartCard
          title="Weight Trend"
          icon={Scale}
          iconColorClass="text-weight"
          iconBgClass="bg-weight-muted"
        >
          <ChartErrorBoundary resetKeys={[startDate, endDate]}>
            <WeightChart
              data={data?.weight ?? []}
              showTrends
              bandwidthShort={bandwidthShort}
              bandwidthLong={bandwidthLong}
              dateRange={dateRange}
            />
          </ChartErrorBoundary>
        </ChartCard>

        <ChartCard
          title="Resting HR"
          icon={Activity}
          iconColorClass="text-heart"
          iconBgClass="bg-heart-muted"
        >
          <ChartErrorBoundary resetKeys={[startDate, endDate]}>
            <HeartRateChart
              data={data?.heart_rate ?? []}
              showTrends
              bandwidthShort={bandwidthShort}
              bandwidthLong={bandwidthLong}
              dateRange={dateRange}
              annotations={annotations}
              baselineMean={rhrBaseline?.mean}
              baselineStd={rhrBaseline?.std}
            />
          </ChartErrorBoundary>
        </ChartCard>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <ChartCard
          title="Daily Steps"
          icon={Footprints}
          iconColorClass="text-steps"
          iconBgClass="bg-steps-muted"
        >
          <ChartErrorBoundary resetKeys={[startDate, endDate]}>
            <StepsChart
              data={data?.steps ?? []}
              showTrends
              bandwidthShort={bandwidthShort}
              bandwidthLong={bandwidthLong}
              dateRange={dateRange}
              stepsFloor={stepsFloor}
            />
          </ChartErrorBoundary>
        </ChartCard>

        <ChartCard
          title="Recovery / Training Readiness"
          icon={Heart}
          iconColorClass="text-whoop"
          iconBgClass="bg-whoop-muted"
        >
          <ChartErrorBoundary resetKeys={[startDate, endDate]}>
            <RecoveryChart
              whoopData={data?.whoop_recovery ?? []}
              garminData={data?.garmin_training_status ?? []}
              showTrends
              bandwidthShort={bandwidthShort}
              bandwidthLong={bandwidthLong}
              dateRange={dateRange}
            />
          </ChartErrorBoundary>
        </ChartCard>

        <ChartCard
          title="Training Load"
          icon={Zap}
          iconColorClass="text-training"
          iconBgClass="bg-training-muted"
        >
          <ChartErrorBoundary resetKeys={[startDate, endDate]}>
            <TrainingLoadChart
              whoopData={data?.whoop_cycle ?? []}
              garminData={data?.garmin_training_status ?? []}
              dateRange={dateRange}
            />
          </ChartErrorBoundary>
        </ChartCard>

        <ChartCard
          title="Calories Burned"
          icon={Flame}
          iconColorClass="text-calories"
          iconBgClass="bg-calories-muted"
        >
          <ChartErrorBoundary resetKeys={[startDate, endDate]}>
            <CaloriesChart
              garminData={data?.garmin_training_status ?? []}
              whoopData={data?.whoop_cycle ?? []}
              energyData={data?.energy ?? []}
              showTrends
              bandwidthShort={bandwidthShort}
              bandwidthLong={bandwidthLong}
              dateRange={dateRange}
            />
          </ChartErrorBoundary>
        </ChartCard>
      </div>
    </div>
  );
}
