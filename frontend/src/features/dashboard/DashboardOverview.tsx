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
import { useProfile } from "../../hooks/useProfile";
import {
  useInterventions,
  useHealthEvents,
  useProtocols,
} from "../../hooks/useHealthLog";
import {
  interventionsToAnnotations,
  healthEventsToAnnotations,
  protocolsToAnnotations,
} from "../../components/charts/annotations";
import { useToday } from "../../hooks/useToday";
import {
  LOESS_BANDWIDTH_SHORT,
  LOESS_BANDWIDTH_LONG,
} from "../../lib/constants";

const DASHBOARD_KEYS = new Set<string>(DASHBOARD_METRIC_KEYS);

function pickLatestNonNull<T, K extends keyof T>(
  arr: ReadonlyArray<T>,
  key: K,
): T[K] | null {
  for (let i = arr.length - 1; i >= 0; i--) {
    const v = arr[i][key];
    if (v != null) return v;
  }
  return null;
}

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
  const { data: healthEvents = [] } = useHealthEvents(90);
  const { data: protocols = [] } = useProtocols();
  const annotations = useMemo(
    () => [
      ...healthEventsToAnnotations(healthEvents),
      ...protocolsToAnnotations(protocols),
      ...interventionsToAnnotations(interventionsData),
    ],
    [healthEvents, protocols, interventionsData],
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

  const garminInsights = useMemo(() => {
    const list = data?.garmin_training_status ?? [];
    return {
      fitness_age: pickLatestNonNull(list, "fitness_age"),
      training_status: pickLatestNonNull(list, "training_status"),
      training_status_description: pickLatestNonNull(
        list,
        "training_status_description",
      ),
      training_readiness_score: pickLatestNonNull(
        list,
        "training_readiness_score",
      ),
      endurance_score: pickLatestNonNull(list, "endurance_score"),
      primary_training_effect: pickLatestNonNull(
        list,
        "primary_training_effect",
      ),
      anaerobic_training_effect: pickLatestNonNull(
        list,
        "anaerobic_training_effect",
      ),
      vo2_max_precise: pickLatestNonNull(list, "vo2_max_precise"),
      training_load_7_day: pickLatestNonNull(list, "training_load_7_day"),
      active_kilocalories: pickLatestNonNull(list, "active_kilocalories"),
    };
  }, [data]);

  const recoverySensors = useMemo(() => {
    const sleep = data?.sleep ?? [];
    const hr = data?.heart_rate ?? [];
    return {
      sleep_spo2_avg: pickLatestNonNull(sleep, "spo2_avg"),
      sleep_spo2_min: pickLatestNonNull(sleep, "spo2_min"),
      day_spo2_avg: pickLatestNonNull(hr, "spo2_avg"),
      waking_respiratory_rate: pickLatestNonNull(hr, "waking_respiratory_rate"),
      lowest_respiratory_rate: pickLatestNonNull(hr, "lowest_respiratory_rate"),
      highest_respiratory_rate: pickLatestNonNull(
        hr,
        "highest_respiratory_rate",
      ),
      max_hr: pickLatestNonNull(hr, "max_hr"),
      avg_hr: pickLatestNonNull(hr, "avg_hr"),
    };
  }, [data]);

  const whoopRecoveryDetails = useMemo(() => {
    const recovery = data?.whoop_recovery ?? [];
    let calibratingLatest: boolean = false;
    for (let i = recovery.length - 1; i >= 0; i--) {
      const v = recovery[i].user_calibrating;
      if (v != null) {
        calibratingLatest = Boolean(v);
        break;
      }
    }
    return {
      skin_temp_celsius: pickLatestNonNull(recovery, "skin_temp_celsius"),
      spo2_percentage: pickLatestNonNull(recovery, "spo2_percentage"),
      hrv_rmssd: pickLatestNonNull(recovery, "hrv_rmssd"),
      resting_heart_rate: pickLatestNonNull(recovery, "resting_heart_rate"),
      user_calibrating: calibratingLatest,
    };
  }, [data]);

  const whoopCycleInsights = useMemo(() => {
    const cycles = data?.whoop_cycle ?? [];
    return {
      avg_heart_rate: pickLatestNonNull(cycles, "avg_heart_rate"),
      max_heart_rate: pickLatestNonNull(cycles, "max_heart_rate"),
    };
  }, [data]);

  const stepsInsights = useMemo(() => {
    const steps = data?.steps ?? [];
    return {
      total_distance: pickLatestNonNull(steps, "total_distance"),
      step_goal: pickLatestNonNull(steps, "step_goal"),
      active_minutes: pickLatestNonNull(steps, "active_minutes"),
      floors_climbed: pickLatestNonNull(steps, "floors_climbed"),
    };
  }, [data]);

  const { data: profile } = useProfile();

  const bodyComposition = useMemo(() => {
    const list = data?.weight ?? [];
    for (let i = list.length - 1; i >= 0; i--) {
      const entry = list[i];
      if (
        entry.bmi !== null ||
        entry.body_fat_pct !== null ||
        entry.muscle_mass_kg !== null ||
        entry.bone_mass_kg !== null ||
        entry.water_pct !== null
      ) {
        return entry;
      }
    }
    return null;
  }, [data]);

  const hasBodyComposition: boolean =
    bodyComposition != null &&
    (bodyComposition.bmi !== null ||
      bodyComposition.body_fat_pct !== null ||
      bodyComposition.muscle_mass_kg !== null ||
      bodyComposition.bone_mass_kg !== null ||
      bodyComposition.water_pct !== null);

  const bmiClassification = (
    bmi: number,
  ): { label: string; className: string } => {
    if (bmi < 18.5) {
      return { label: "Underweight", className: "bg-warning/15 text-warning" };
    }
    if (bmi < 25) {
      return { label: "Normal", className: "bg-success/15 text-success" };
    }
    if (bmi < 30) {
      return {
        label: "Overweight",
        className: "bg-orange-500/15 text-orange-500",
      };
    }
    return { label: "Obese", className: "bg-destructive/15 text-destructive" };
  };

  const bodyFatClassification = (
    pct: number,
    gender: string | null,
  ): { label: string; className: string } | null => {
    const g = (gender ?? "").toLowerCase();
    if (g !== "male" && g !== "female") return null;
    const offset = g === "female" ? 5 : 0;
    if (pct < 10 + offset) {
      return { label: "Athletic", className: "bg-info/15 text-info" };
    }
    if (pct < 20 + offset) {
      return { label: "Fit", className: "bg-success/15 text-success" };
    }
    if (pct < 25 + offset) {
      return { label: "Average", className: "bg-warning/15 text-warning" };
    }
    return { label: "High", className: "bg-destructive/15 text-destructive" };
  };

  const trainingStatusColor = (status: string | null): string => {
    const s = (status ?? "").toLowerCase();
    if (s.includes("productive")) return "bg-success/15 text-success";
    if (s.includes("maintaining")) return "bg-info/15 text-info";
    if (s.includes("unproductive")) return "bg-warning/15 text-warning";
    if (s.includes("overreaching")) return "bg-destructive/15 text-destructive";
    return "bg-muted text-muted-foreground";
  };

  const readinessColor = (score: number | null): string => {
    if (score === null) return "text-foreground";
    if (score > 75) return "text-success";
    if (score >= 50) return "text-warning";
    return "text-destructive";
  };

  const hasGarminInsights =
    garminInsights.fitness_age !== null ||
    garminInsights.training_status !== null ||
    garminInsights.training_readiness_score !== null ||
    garminInsights.endurance_score !== null ||
    garminInsights.primary_training_effect !== null ||
    garminInsights.anaerobic_training_effect !== null ||
    garminInsights.vo2_max_precise !== null ||
    garminInsights.training_load_7_day !== null;

  const hasRecoverySensors =
    recoverySensors.sleep_spo2_avg !== null ||
    recoverySensors.sleep_spo2_min !== null ||
    recoverySensors.day_spo2_avg !== null ||
    recoverySensors.waking_respiratory_rate !== null ||
    recoverySensors.lowest_respiratory_rate !== null ||
    recoverySensors.highest_respiratory_rate !== null ||
    recoverySensors.max_hr !== null ||
    recoverySensors.avg_hr !== null;

  const hasWhoopRecoveryDetails =
    whoopRecoveryDetails.skin_temp_celsius !== null ||
    whoopRecoveryDetails.spo2_percentage !== null ||
    whoopRecoveryDetails.hrv_rmssd !== null ||
    whoopRecoveryDetails.resting_heart_rate !== null;

  const whoopSpo2ColorClass = (v: number | null): string => {
    if (v === null) return "text-foreground";
    if (v >= 95) return "text-success";
    if (v >= 90) return "text-warning";
    return "text-destructive";
  };

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

      {hasGarminInsights && (
        <section className="space-y-3">
          <h2 className="text-xl font-semibold tracking-tight">
            Garmin Insights
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {garminInsights.fitness_age !== null && (
              <Card>
                <CardContent className="p-5 space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">
                    Fitness Age
                  </p>
                  <p className="text-3xl font-bold tracking-tight">
                    {garminInsights.fitness_age} yrs
                  </p>
                  <p className="text-xs text-muted-foreground">
                    vs your chronological age
                  </p>
                </CardContent>
              </Card>
            )}
            {garminInsights.training_status !== null && (
              <Card>
                <CardContent className="p-5 space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">
                    Training Status
                  </p>
                  <span
                    className={`inline-flex px-2.5 py-1 rounded-md text-sm font-semibold capitalize ${trainingStatusColor(
                      garminInsights.training_status,
                    )}`}
                  >
                    {garminInsights.training_status}
                  </span>
                  {garminInsights.training_status_description && (
                    <p className="text-xs text-muted-foreground">
                      {garminInsights.training_status_description}
                    </p>
                  )}
                </CardContent>
              </Card>
            )}
            {garminInsights.training_readiness_score !== null && (
              <Card>
                <CardContent className="p-5 space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">
                    Training Readiness
                  </p>
                  <p
                    className={`text-3xl font-bold tracking-tight ${readinessColor(
                      garminInsights.training_readiness_score,
                    )}`}
                  >
                    {garminInsights.training_readiness_score}
                    <span className="text-base font-medium text-muted-foreground">
                      /100
                    </span>
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Ready to train
                  </p>
                </CardContent>
              </Card>
            )}
            {garminInsights.endurance_score !== null && (
              <Card>
                <CardContent className="p-5 space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">
                    Endurance Score
                  </p>
                  <p className="text-3xl font-bold tracking-tight">
                    {garminInsights.endurance_score}
                    <span className="text-base font-medium text-muted-foreground">
                      /100
                    </span>
                  </p>
                </CardContent>
              </Card>
            )}
            {garminInsights.primary_training_effect !== null && (
              <Card>
                <CardContent className="p-5 space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">
                    Aerobic TE today
                  </p>
                  <p className="text-3xl font-bold tracking-tight">
                    {garminInsights.primary_training_effect.toFixed(1)}
                    <span className="text-base font-medium text-muted-foreground">
                      /5
                    </span>
                  </p>
                  <div className="h-1.5 w-full bg-muted rounded">
                    <div
                      className="h-1.5 bg-primary rounded"
                      style={{
                        width: `${String(Math.min(100, (garminInsights.primary_training_effect / 5) * 100))}%`,
                      }}
                    />
                  </div>
                </CardContent>
              </Card>
            )}
            {garminInsights.anaerobic_training_effect !== null && (
              <Card>
                <CardContent className="p-5 space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">
                    Anaerobic TE today
                  </p>
                  <p className="text-3xl font-bold tracking-tight">
                    {garminInsights.anaerobic_training_effect.toFixed(1)}
                    <span className="text-base font-medium text-muted-foreground">
                      /5
                    </span>
                  </p>
                  <div className="h-1.5 w-full bg-muted rounded">
                    <div
                      className="h-1.5 bg-primary rounded"
                      style={{
                        width: `${String(Math.min(100, (garminInsights.anaerobic_training_effect / 5) * 100))}%`,
                      }}
                    />
                  </div>
                </CardContent>
              </Card>
            )}
            {garminInsights.vo2_max_precise !== null && (
              <Card>
                <CardContent className="p-5 space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">
                    VO2 Max (precise)
                  </p>
                  <p className="text-3xl font-bold tracking-tight">
                    {garminInsights.vo2_max_precise.toFixed(1)}
                    <span className="text-base font-medium text-muted-foreground">
                      {" "}
                      ml/kg/min
                    </span>
                  </p>
                </CardContent>
              </Card>
            )}
            {garminInsights.training_load_7_day !== null && (
              <Card>
                <CardContent className="p-5 space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">
                    Training Load (7-day)
                  </p>
                  <p className="text-3xl font-bold tracking-tight">
                    {Math.round(garminInsights.training_load_7_day)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Weekly accumulation
                  </p>
                </CardContent>
              </Card>
            )}
            {garminInsights.active_kilocalories !== null && (
              <Card>
                <CardContent className="p-5 space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">
                    Active Calories
                  </p>
                  <p className="text-3xl font-bold tracking-tight">
                    {Math.round(garminInsights.active_kilocalories)}
                    <span className="text-base font-medium text-muted-foreground">
                      {" "}
                      kcal
                    </span>
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </section>
      )}

      {hasRecoverySensors && (
        <section className="space-y-3">
          <h2 className="text-xl font-semibold tracking-tight">
            Recovery Sensors
          </h2>
          <Card>
            <CardContent className="p-5">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {recoverySensors.sleep_spo2_avg !== null && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      SpO2 Avg (Sleep)
                    </p>
                    <p className="text-2xl font-bold tracking-tight">
                      {recoverySensors.sleep_spo2_avg.toFixed(0)}
                      <span className="text-sm font-medium text-muted-foreground">
                        %
                      </span>
                    </p>
                  </div>
                )}
                {recoverySensors.sleep_spo2_min !== null && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      SpO2 Min (Sleep)
                    </p>
                    <p className="text-2xl font-bold tracking-tight">
                      {recoverySensors.sleep_spo2_min.toFixed(0)}
                      <span className="text-sm font-medium text-muted-foreground">
                        %
                      </span>
                    </p>
                  </div>
                )}
                {recoverySensors.day_spo2_avg !== null && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      SpO2 Avg (Day)
                    </p>
                    <p className="text-2xl font-bold tracking-tight">
                      {recoverySensors.day_spo2_avg.toFixed(0)}
                      <span className="text-sm font-medium text-muted-foreground">
                        %
                      </span>
                    </p>
                  </div>
                )}
                {recoverySensors.waking_respiratory_rate !== null && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      Resp. Rate (Wake)
                    </p>
                    <p className="text-2xl font-bold tracking-tight">
                      {recoverySensors.waking_respiratory_rate.toFixed(1)}
                      <span className="text-sm font-medium text-muted-foreground">
                        {" "}
                        br/min
                      </span>
                    </p>
                  </div>
                )}
                {(recoverySensors.lowest_respiratory_rate !== null ||
                  recoverySensors.highest_respiratory_rate !== null) && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      Resp. Rate Range
                    </p>
                    <p className="text-2xl font-bold tracking-tight">
                      {recoverySensors.lowest_respiratory_rate === null
                        ? "—"
                        : recoverySensors.lowest_respiratory_rate.toFixed(1)}
                      <span className="text-sm font-medium text-muted-foreground">
                        {" "}
                        to{" "}
                      </span>
                      {recoverySensors.highest_respiratory_rate === null
                        ? "—"
                        : recoverySensors.highest_respiratory_rate.toFixed(1)}
                    </p>
                  </div>
                )}
                {recoverySensors.max_hr !== null && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      Max HR
                    </p>
                    <p className="text-2xl font-bold tracking-tight">
                      {recoverySensors.max_hr}
                      <span className="text-sm font-medium text-muted-foreground">
                        {" "}
                        bpm
                      </span>
                    </p>
                  </div>
                )}
                {recoverySensors.avg_hr !== null && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      Avg HR
                    </p>
                    <p className="text-2xl font-bold tracking-tight">
                      {recoverySensors.avg_hr}
                      <span className="text-sm font-medium text-muted-foreground">
                        {" "}
                        bpm
                      </span>
                    </p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </section>
      )}

      {hasBodyComposition && bodyComposition != null && (
        <section className="space-y-3">
          <h2 className="text-xl font-semibold tracking-tight">
            Body Composition
          </h2>
          <Card>
            <CardContent className="p-5">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {bodyComposition.bmi !== null &&
                  (() => {
                    const cls = bmiClassification(bodyComposition.bmi);
                    return (
                      <div className="space-y-1">
                        <p className="text-xs font-medium text-muted-foreground">
                          BMI
                        </p>
                        <p className="text-2xl font-bold tracking-tight">
                          {bodyComposition.bmi.toFixed(1)}
                        </p>
                        <span
                          className={`inline-flex px-2 py-0.5 rounded-md text-xs font-semibold ${cls.className}`}
                        >
                          {cls.label}
                        </span>
                      </div>
                    );
                  })()}
                {bodyComposition.body_fat_pct !== null &&
                  (() => {
                    const cls = bodyFatClassification(
                      bodyComposition.body_fat_pct,
                      profile?.gender ?? null,
                    );
                    return (
                      <div className="space-y-1">
                        <p className="text-xs font-medium text-muted-foreground">
                          Body Fat
                        </p>
                        <p className="text-2xl font-bold tracking-tight">
                          {bodyComposition.body_fat_pct.toFixed(1)}
                          <span className="text-sm font-medium text-muted-foreground">
                            %
                          </span>
                        </p>
                        {cls && (
                          <span
                            className={`inline-flex px-2 py-0.5 rounded-md text-xs font-semibold ${cls.className}`}
                          >
                            {cls.label}
                          </span>
                        )}
                      </div>
                    );
                  })()}
                {bodyComposition.muscle_mass_kg !== null && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      Muscle Mass
                    </p>
                    <p className="text-2xl font-bold tracking-tight">
                      {bodyComposition.muscle_mass_kg.toFixed(1)}
                      <span className="text-sm font-medium text-muted-foreground">
                        {" "}
                        kg
                      </span>
                    </p>
                  </div>
                )}
                {bodyComposition.bone_mass_kg !== null && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      Bone Mass
                    </p>
                    <p className="text-2xl font-bold tracking-tight">
                      {bodyComposition.bone_mass_kg.toFixed(2)}
                      <span className="text-sm font-medium text-muted-foreground">
                        {" "}
                        kg
                      </span>
                    </p>
                  </div>
                )}
                {bodyComposition.water_pct !== null && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      Body Water
                    </p>
                    <p className="text-2xl font-bold tracking-tight">
                      {bodyComposition.water_pct.toFixed(1)}
                      <span className="text-sm font-medium text-muted-foreground">
                        %
                      </span>
                    </p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </section>
      )}

      {hasWhoopRecoveryDetails && (
        <section className="space-y-3">
          <h2 className="text-xl font-semibold tracking-tight">
            Whoop Recovery Details
          </h2>
          <Card>
            <CardContent className="p-5 space-y-4">
              {whoopRecoveryDetails.user_calibrating && (
                <div className="rounded-md bg-warning/10 text-warning px-3 py-2 text-xs font-medium">
                  Calibrating — Whoop accuracy improves over the first 2-3 weeks
                  of use
                </div>
              )}
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {whoopRecoveryDetails.skin_temp_celsius !== null && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      Skin Temperature
                    </p>
                    <p className="text-2xl font-bold tracking-tight">
                      {whoopRecoveryDetails.skin_temp_celsius.toFixed(1)}
                      <span className="text-sm font-medium text-muted-foreground">
                        {" "}
                        °C
                      </span>
                    </p>
                  </div>
                )}
                {whoopRecoveryDetails.spo2_percentage !== null && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      SpO2 (Whoop)
                    </p>
                    <p
                      className={`text-2xl font-bold tracking-tight ${whoopSpo2ColorClass(whoopRecoveryDetails.spo2_percentage)}`}
                    >
                      {whoopRecoveryDetails.spo2_percentage.toFixed(1)}
                      <span className="text-sm font-medium text-muted-foreground">
                        %
                      </span>
                    </p>
                  </div>
                )}
                {whoopRecoveryDetails.hrv_rmssd !== null && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      HRV RMSSD
                    </p>
                    <p className="text-2xl font-bold tracking-tight">
                      {whoopRecoveryDetails.hrv_rmssd.toFixed(0)}
                      <span className="text-sm font-medium text-muted-foreground">
                        {" "}
                        ms
                      </span>
                    </p>
                  </div>
                )}
                {whoopRecoveryDetails.resting_heart_rate !== null && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      Resting HR
                    </p>
                    <p className="text-2xl font-bold tracking-tight">
                      {whoopRecoveryDetails.resting_heart_rate.toFixed(0)}
                      <span className="text-sm font-medium text-muted-foreground">
                        {" "}
                        bpm
                      </span>
                    </p>
                  </div>
                )}
                {whoopCycleInsights.avg_heart_rate !== null && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      Daily Avg HR (Cycle)
                    </p>
                    <p className="text-2xl font-bold tracking-tight">
                      {Math.round(whoopCycleInsights.avg_heart_rate)}
                      <span className="text-sm font-medium text-muted-foreground">
                        {" "}
                        bpm
                      </span>
                    </p>
                  </div>
                )}
                {whoopCycleInsights.max_heart_rate !== null && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      Daily Max HR (Cycle)
                    </p>
                    <p className="text-2xl font-bold tracking-tight">
                      {Math.round(whoopCycleInsights.max_heart_rate)}
                      <span className="text-sm font-medium text-muted-foreground">
                        {" "}
                        bpm
                      </span>
                    </p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </section>
      )}

      {(stepsInsights.total_distance !== null ||
        stepsInsights.active_minutes !== null ||
        stepsInsights.floors_climbed !== null ||
        stepsInsights.step_goal !== null) && (
        <section className="space-y-3">
          <h2 className="text-xl font-semibold tracking-tight">
            Activity Details
          </h2>
          <Card>
            <CardContent className="p-5">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {stepsInsights.total_distance !== null && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      Distance
                    </p>
                    <p className="text-2xl font-bold tracking-tight">
                      {(stepsInsights.total_distance / 1000).toFixed(2)}
                      <span className="text-sm font-medium text-muted-foreground">
                        {" "}
                        km
                      </span>
                    </p>
                  </div>
                )}
                {stepsInsights.step_goal !== null && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      Step Goal
                    </p>
                    <p className="text-2xl font-bold tracking-tight">
                      {stepsInsights.step_goal.toLocaleString()}
                    </p>
                  </div>
                )}
                {stepsInsights.active_minutes !== null && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      Active Minutes
                    </p>
                    <p className="text-2xl font-bold tracking-tight">
                      {Math.round(stepsInsights.active_minutes)}
                      <span className="text-sm font-medium text-muted-foreground">
                        {" "}
                        min
                      </span>
                    </p>
                  </div>
                )}
                {stepsInsights.floors_climbed !== null &&
                  stepsInsights.floors_climbed > 0 && (
                    <div className="space-y-1">
                      <p className="text-xs font-medium text-muted-foreground">
                        Floors Climbed
                      </p>
                      <p className="text-2xl font-bold tracking-tight">
                        {Math.round(stepsInsights.floors_climbed)}
                      </p>
                    </div>
                  )}
              </div>
            </CardContent>
          </Card>
        </section>
      )}

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

      <StressBreakdownCard stress={data?.stress ?? []} />
    </div>
  );
}

interface StressBreakdownCardProps {
  readonly stress: ReadonlyArray<{
    readonly date: string;
    readonly avg_stress: number | null;
    readonly max_stress: number | null;
    readonly stress_level: string | null;
    readonly rest_stress: number | null;
    readonly activity_stress: number | null;
  }>;
}

function getStressColorClass(value: number | null): string {
  if (value === null) return "text-muted-foreground";
  if (value < 30) return "text-success";
  if (value <= 60) return "text-warning";
  return "text-destructive";
}

function getStressLevelBadgeClass(level: string | null): string {
  const normalized = (level ?? "").toLowerCase();
  if (normalized === "low") return "bg-success/10 text-success";
  if (normalized === "medium") return "bg-warning/10 text-warning";
  if (normalized === "high") return "bg-destructive/10 text-destructive";
  return "bg-muted text-muted-foreground";
}

function StressBreakdownCard({ stress }: StressBreakdownCardProps) {
  const latest = useMemo(() => {
    for (let i = stress.length - 1; i >= 0; i--) {
      const entry = stress[i];
      if (
        entry.avg_stress !== null ||
        entry.max_stress !== null ||
        entry.rest_stress !== null ||
        entry.activity_stress !== null ||
        entry.stress_level !== null
      ) {
        return entry;
      }
    }
    return null;
  }, [stress]);

  if (!latest) return null;

  const formatNum = (v: number | null): string =>
    v === null ? "—" : String(Math.round(v));

  return (
    <Card>
      <CardContent className="p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold tracking-tight">
            Stress Breakdown
          </h3>
          <span className="text-xs text-muted-foreground">{latest.date}</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">
              Avg Stress
            </p>
            <p
              className={`text-2xl font-bold tracking-tight ${getStressColorClass(latest.avg_stress)}`}
            >
              {formatNum(latest.avg_stress)}
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">
              Max Stress
            </p>
            <p
              className={`text-2xl font-bold tracking-tight ${getStressColorClass(latest.max_stress)}`}
            >
              {formatNum(latest.max_stress)}
            </p>
          </div>
          {latest.rest_stress !== null && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">
                Rest Stress
              </p>
              <p
                className={`text-2xl font-bold tracking-tight ${getStressColorClass(latest.rest_stress)}`}
              >
                {formatNum(latest.rest_stress)}
              </p>
            </div>
          )}
          {latest.activity_stress !== null && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">
                Activity Stress
              </p>
              <p
                className={`text-2xl font-bold tracking-tight ${getStressColorClass(latest.activity_stress)}`}
              >
                {formatNum(latest.activity_stress)}
              </p>
            </div>
          )}
        </div>
        {latest.stress_level !== null && (
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-muted-foreground">
              Stress Level:
            </span>
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${getStressLevelBadgeClass(latest.stress_level)}`}
            >
              {latest.stress_level}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
