import { useState, useMemo } from "react";
import { useHealthData } from "../../hooks/useHealthData";
import { useAnalytics } from "../../hooks/useAnalytics";
import { Button } from "../../components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../../components/ui/card";
import { LoadingState } from "../../components/ui/loading-state";
import { ErrorCard } from "../../components/ui/error-card";
import {
  formatZScore,
  getZScoreColor,
  getHealthScoreLabel,
  getHealthScoreColor,
  calculateClinicalAlerts,
  calculateOverreachingMetrics,
  calculateCorrelationMetrics,
  detectAnomalies,
  calculateVelocityMetrics,
  calculateRecoveryCapacity,
  calculateIllnessRiskSignal,
  calculateDecorrelationAlert,
  type DataQuality,
  type BaselineMetrics,
} from "../../lib/health-metrics";
import { toLocalDayDate } from "../../lib/health/date";
import { PROVIDER_CONFIGS } from "../../lib/providers";
import {
  METRIC_REGISTRY,
  formatSleepMinutes,
  TREND_MODES,
  MODE_ORDER,
  MAX_BASELINE_DAYS,
  computeAllMetrics,
  getBaselineOptions,
  computeHealthAnalysis,
  type TrendMode,
} from "../../lib/metrics";
import {
  Moon,
  Activity,
  Calendar,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  CheckCircle,
  Clock,
  Gauge,
  Heart,
  Zap,
  Footprints,
  Scale,
  Brain,
  ShieldAlert,
  Flame,
  GitBranch,
  Radar,
  ArrowUpRight,
  ArrowDownRight,
  RefreshCw,
  Thermometer,
  Unlink,
  Dumbbell,
  Beaker,
  BarChart3,
  Loader2,
  type LucideIcon,
} from "lucide-react";
import { cn } from "../../lib/utils";

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.8) return "text-green-500";
  if (confidence >= 0.6) return "text-yellow-500";
  return "text-red-500";
}

function getHrvRhrColor(value: number | null): string {
  if (value === null) return "text-muted-foreground";
  if (value > 1) return "text-red-500";
  if (value < -1) return "text-green-500";
  return "text-blue-500";
}

function getHrvRhrLabel(value: number | null): string {
  if (value === null) return "Insufficient data";
  if (value > 1) return "Body under strain";
  if (value < -1) return "Well recovered";
  return "Balanced";
}

function getSleepDebtColor(value: number): string {
  if (value > 120) return "text-red-500";
  if (value > 60) return "text-yellow-500";
  return "text-green-500";
}

function getAcwrColor(value: number | null): string {
  if (value === null) return "text-muted-foreground";
  if (value > 1.5) return "text-red-500";
  if (value < 0.8) return "text-yellow-500";
  return "text-green-500";
}

function getAcwrLabel(value: number | null): string {
  if (value === null) return "Insufficient strain data";
  if (value > 1.5) return "Injury risk - reduce load";
  if (value < 0.8) return "Detraining risk";
  return "Sweet spot";
}

function getStepsChangeColor(value: number | null): string {
  if (value === null) return "text-muted-foreground";
  if (value < -1000) return "text-red-500";
  if (value > 1000) return "text-green-500";
  return "text-blue-500";
}

function getWeightChangeColor(value: number | null): string {
  if (value === null) return "";
  if (value > 0.5) return "text-red-500";
  if (value < -0.5) return "text-green-500";
  return "text-blue-500";
}

function getStressTrendColor(value: number | null): string {
  if (value === null) return "";
  if (value > 5) return "text-red-500";
  if (value < -5) return "text-green-500";
  return "text-blue-500";
}

function getCorrelationColor(value: number | null): string {
  if (value === null) return "text-muted-foreground";
  if (value < -0.3) return "text-green-500";
  if (value > 0) return "text-red-500";
  return "text-muted-foreground";
}

function getHrvSdColor(value: number | null): string {
  if (value === null) return "";
  if (value < 0.1) return "text-green-500";
  if (value > 0.15) return "text-red-500";
  return "";
}

function getTsbColor(value: number | null): string {
  if (value === null) return "";
  if (value > 0) return "text-green-500";
  if (value < -10) return "text-red-500";
  return "";
}

function getAllostaticScoreColor(value: number | null): string {
  if (value === null) return "text-yellow-500";
  if (value < 20) return "text-green-500";
  if (value > 40) return "text-red-500";
  return "text-yellow-500";
}

function getDysregulationRateColor(rate: number): string {
  if (rate > 0.3) return "text-red-500";
  if (rate > 0.15) return "text-yellow-500";
  return "text-green-500";
}

function getCrossCorrelationColor(value: number | null): string {
  if (value === null) return "";
  if (value > 0.3) return "text-green-500";
  if (value < -0.3) return "text-red-500";
  return "";
}

interface DataQualityBadgeProps {
  quality: DataQuality;
}

function DataQualityBadge({ quality }: DataQualityBadgeProps) {
  const coveragePercent = Math.round(quality.coverage * 100);
  const confidencePercent = Math.round(quality.confidence * 100);
  let color = "text-green-600 dark:text-green-400";
  let Icon = CheckCircle;

  if (quality.confidence < 0.6) {
    color = "text-red-600 dark:text-red-400";
    Icon = AlertTriangle;
  } else if (quality.confidence < 0.8) {
    color = "text-yellow-600 dark:text-yellow-400";
    Icon = Clock;
  }

  return (
    <div className="flex items-center gap-1.5 text-xs">
      <Icon className={cn("h-3 w-3", color)} />
      <span className={color}>{confidencePercent}% conf</span>
      <span className="text-muted-foreground">({coveragePercent}% cov)</span>
      {quality.latencyDays !== null && quality.latencyDays > 1 && (
        <span className="text-muted-foreground">
          · {quality.latencyDays}d ago
        </span>
      )}
    </div>
  );
}

interface MetricCardProps {
  title: string;
  icon: LucideIcon;
  iconColorClass: string;
  iconBgClass: string;
  baseline: BaselineMetrics;
  quality: DataQuality;
  format: (value: number | null) => string;
  invertZScore?: boolean;
  shortTermDays: number;
  baselineDays: number;
  trendWindow: number;
  useShiftedZScore: boolean;
}

function formatDaysLabel(days: number): string {
  if (days >= 365) {
    const years = Math.round(days / 365);
    return `${String(years)}Y`;
  } else if (days >= 30) {
    const months = Math.round(days / 30);
    return `${String(months)}M`;
  }
  return `${String(days)}d`;
}

function MetricCard({
  title,
  icon: Icon,
  iconColorClass,
  iconBgClass,
  baseline,
  quality,
  format: formatValue,
  invertZScore = false,
  shortTermDays,
  baselineDays,
  trendWindow,
  useShiftedZScore,
}: MetricCardProps) {
  const rawZScore = useShiftedZScore ? baseline.shiftedZScore : baseline.zScore;
  const displayZScore =
    invertZScore && rawZScore !== null ? -rawZScore : rawZScore;

  const zScoreLabel = useShiftedZScore ? "period z" : "z-score";

  const trendIcon = (() => {
    if (baseline.trendSlope === null) {
      return <Minus className="h-4 w-4 text-muted-foreground" />;
    }
    if (baseline.trendSlope > 0) {
      return <TrendingUp className="h-4 w-4 text-green-500" />;
    }
    return <TrendingDown className="h-4 w-4 text-red-500" />;
  })();

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={cn("p-1.5 rounded-lg", iconBgClass)}>
              <Icon className={cn("h-4 w-4", iconColorClass)} />
            </div>
            <CardTitle className="text-base">{title}</CardTitle>
          </div>
          <DataQualityBadge quality={quality} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {quality.validPoints === 0 ? (
          <p className="text-sm text-muted-foreground">No data available</p>
        ) : (
          <>
            <div className="flex items-baseline justify-between">
              <div>
                <span className="text-2xl font-bold">
                  {formatValue(baseline.currentValue)}
                </span>
                <span className="text-sm text-muted-foreground ml-2">
                  current
                </span>
              </div>
              <div className="text-right">
                <div
                  className={cn(
                    "text-lg font-semibold",
                    getZScoreColor(displayZScore),
                  )}
                >
                  {formatZScore(displayZScore)}
                </div>
                <p className="text-[10px] text-muted-foreground">
                  {zScoreLabel}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">
                  {formatDaysLabel(shortTermDays)} avg
                </p>
                <p className="font-medium">
                  {formatValue(baseline.shortTermMean)}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  {formatDaysLabel(baselineDays)} avg
                </p>
                <p className="font-medium">
                  {formatValue(baseline.longTermMean)}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  trend ({formatDaysLabel(trendWindow)})
                </p>
                <div className="flex items-center gap-1">
                  {trendIcon}
                  <span className="font-medium">
                    {baseline.trendSlope !== null
                      ? `${baseline.trendSlope > 0 ? "+" : ""}${baseline.trendSlope.toFixed(2)}/d`
                      : "—"}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t">
              <span>CV: {(baseline.cv * 100).toFixed(1)}%</span>
              <span>Outliers: {(quality.outlierRate * 100).toFixed(1)}%</span>
              <span>{quality.validPoints} pts</span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function ModeSelector({
  mode,
  setMode,
}: {
  mode: TrendMode;
  setMode: (m: TrendMode) => void;
}) {
  return (
    <div className="flex items-center gap-2 p-1 bg-muted/50 rounded-lg">
      <Calendar className="h-4 w-4 text-muted-foreground ml-2" />
      {MODE_ORDER.map((m) => {
        const cfg = TREND_MODES[m];
        return (
          <Button
            key={m}
            variant={mode === m ? "default" : "ghost"}
            size="sm"
            onClick={() => {
              setMode(m);
            }}
            className="min-w-[90px] flex flex-col h-auto py-1.5"
          >
            <span className="font-medium">{cfg.label}</span>
            <span className="text-[10px] opacity-70">{cfg.description}</span>
          </Button>
        );
      })}
    </div>
  );
}

export function StatisticsPage() {
  const [mode, setMode] = useState<TrendMode>("recent");
  const modeConfig = TREND_MODES[mode];
  const {
    baseline: baselineDays,
    shortTerm: shortTermDays,
    trendWindow,
    useShiftedZScore,
  } = modeConfig;
  const { data, isLoading, isFetching, error } = useHealthData(
    MAX_BASELINE_DAYS,
    true,
  );
  const {
    data: analyticsData,
    isLoading: analyticsLoading,
    isFetching: analyticsFetching,
    error: analyticsError,
  } = useAnalytics(mode);
  const advancedInsights = analyticsData?.advanced_insights;

  const baselineOptions = useMemo(
    () => getBaselineOptions(mode, modeConfig),
    [mode, modeConfig],
  );

  const computedMetrics = useMemo(
    () =>
      data
        ? computeAllMetrics(
            data,
            baselineDays,
            shortTermDays,
            trendWindow,
            baselineOptions,
          )
        : null,
    [data, baselineDays, shortTermDays, trendWindow, baselineOptions],
  );

  const healthAnalysis = useMemo(
    () =>
      data && computedMetrics
        ? computeHealthAnalysis(
            data,
            computedMetrics,
            modeConfig,
            baselineOptions,
          )
        : null,
    [data, computedMetrics, modeConfig, baselineOptions],
  );

  const hrvData = computedMetrics?.hrv.raw;
  const rhrData = computedMetrics?.rhr.raw;
  const sleepDataRaw = computedMetrics?.sleep.raw;
  const strainData = computedMetrics?.strain.raw;
  const weightDataRaw = computedMetrics?.weight.raw;
  const stressData = computedMetrics?.stress.raw;

  const clinicalAlerts = useMemo(
    () =>
      rhrData && hrvData && weightDataRaw && strainData
        ? calculateClinicalAlerts(
            rhrData,
            hrvData,
            weightDataRaw,
            strainData,
            baselineDays,
          )
        : null,
    [rhrData, hrvData, weightDataRaw, strainData, baselineDays],
  );

  const overreachingMetrics = useMemo(
    () =>
      hrvData && rhrData && sleepDataRaw && strainData
        ? calculateOverreachingMetrics(
            hrvData,
            rhrData,
            sleepDataRaw,
            strainData,
            baselineDays,
            shortTermDays,
          )
        : null,
    [hrvData, rhrData, sleepDataRaw, strainData, baselineDays, shortTermDays],
  );

  const correlationMetrics = useMemo(
    () =>
      hrvData && rhrData && sleepDataRaw && strainData
        ? calculateCorrelationMetrics(
            hrvData,
            rhrData,
            sleepDataRaw,
            strainData,
            baselineDays,
          )
        : null,
    [hrvData, rhrData, sleepDataRaw, strainData, baselineDays],
  );

  const anomalyMetrics = useMemo(
    () =>
      hrvData && rhrData && sleepDataRaw && stressData
        ? detectAnomalies(
            hrvData,
            rhrData,
            sleepDataRaw,
            stressData,
            baselineDays,
            shortTermDays,
          )
        : null,
    [hrvData, rhrData, sleepDataRaw, stressData, baselineDays, shortTermDays],
  );

  const velocityMetrics = useMemo(
    () =>
      hrvData && rhrData && weightDataRaw && sleepDataRaw
        ? calculateVelocityMetrics(
            hrvData,
            rhrData,
            weightDataRaw,
            sleepDataRaw,
            shortTermDays,
          )
        : null,
    [hrvData, rhrData, weightDataRaw, sleepDataRaw, shortTermDays],
  );

  const recoveryCapacity = useMemo(
    () =>
      hrvData && strainData
        ? calculateRecoveryCapacity(hrvData, strainData, baselineDays)
        : null,
    [hrvData, strainData, baselineDays],
  );

  const illnessRisk = useMemo(
    () =>
      hrvData && rhrData && sleepDataRaw
        ? calculateIllnessRiskSignal(
            hrvData,
            rhrData,
            sleepDataRaw,
            baselineDays,
            3,
          )
        : null,
    [hrvData, rhrData, sleepDataRaw, baselineDays],
  );

  const decorrelationAlert = useMemo(
    () =>
      hrvData && rhrData
        ? calculateDecorrelationAlert(hrvData, rhrData, 14, baselineDays)
        : null,
    [hrvData, rhrData, baselineDays],
  );

  if (error) {
    return (
      <ErrorCard message={`Failed to load health data: ${error.message}`} />
    );
  }

  if (isLoading || !data || !healthAnalysis || !computedMetrics) {
    return (
      <div className="space-y-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              Health Analytics
            </h1>
            <p className="text-muted-foreground mt-1">
              Personal baseline deviations and trends
            </p>
          </div>
          <ModeSelector mode={mode} setMode={setMode} />
        </div>
        <LoadingState message="Analyzing health data..." />
      </div>
    );
  }

  const {
    healthScore,
    recoveryMetrics,
    sleepMetrics,
    activityMetrics,
    weightMetrics,
    dayCompleteness,
    dataSourceSummary,
  } = healthAnalysis;

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Health Analytics
          </h1>
          <p className="text-muted-foreground mt-1">
            Personal baseline deviations and trends
          </p>
        </div>
        <div className="flex items-center gap-3">
          {(isFetching || analyticsFetching) && (
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
          )}
          <ModeSelector mode={mode} setMode={setMode} />
        </div>
      </div>

      <Card className="border-2">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-primary/10">
              <Gauge className="h-6 w-6 text-primary" />
            </div>
            <div>
              <CardTitle>Health Status Score</CardTitle>
              <CardDescription>
                Composite: recovery core (60%) + training load (20%) + behavior
                (20%)
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            <div className="text-center">
              <p className="text-sm text-muted-foreground mb-1">Overall</p>
              <p
                className={cn(
                  "text-4xl font-bold",
                  getHealthScoreColor(healthScore.overall),
                )}
              >
                {healthScore.overall !== null
                  ? healthScore.overall.toFixed(2)
                  : "—"}
              </p>
              <p
                className={cn(
                  "text-sm font-medium mt-1",
                  getHealthScoreColor(healthScore.overall),
                )}
              >
                {getHealthScoreLabel(healthScore.overall)}
              </p>
            </div>
            <div className="text-center">
              <p className="text-sm text-muted-foreground mb-1">
                Recovery Core
              </p>
              <p
                className={cn(
                  "text-3xl font-bold",
                  getHealthScoreColor(healthScore.recoveryCore),
                )}
              >
                {healthScore.recoveryCore !== null
                  ? healthScore.recoveryCore.toFixed(2)
                  : "—"}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                HRV + RHR + Sleep + Stress
              </p>
            </div>
            <div className="text-center">
              <p className="text-sm text-muted-foreground mb-1">
                Training Load
              </p>
              <p
                className={cn(
                  "text-3xl font-bold",
                  healthScore.trainingLoad !== null
                    ? getHealthScoreColor(healthScore.trainingLoad)
                    : "text-muted-foreground",
                )}
              >
                {healthScore.trainingLoad !== null
                  ? healthScore.trainingLoad.toFixed(2)
                  : "—"}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Strain optimality
              </p>
            </div>
            <div className="text-center">
              <p className="text-sm text-muted-foreground mb-1">
                Behavior Support
              </p>
              <p
                className={cn(
                  "text-3xl font-bold",
                  getHealthScoreColor(healthScore.behaviorSupport),
                )}
              >
                {healthScore.behaviorSupport !== null
                  ? healthScore.behaviorSupport.toFixed(2)
                  : "—"}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Steps + Calories + Weight
              </p>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-medium">Contributors</p>
              <p className="text-xs text-muted-foreground">
                Day {Math.round(dayCompleteness * 100)}% complete
                {!healthScore.stepsStatus.useToday && (
                  <span className="text-yellow-500 ml-1">
                    · Steps using yesterday
                  </span>
                )}
              </p>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              {healthScore.contributors.map((c) => (
                <div
                  key={c.name}
                  className={cn(
                    "text-center p-2 rounded-lg",
                    c.isGated
                      ? "bg-muted/30 border border-dashed border-muted-foreground/30"
                      : "bg-muted/50",
                  )}
                >
                  <p className="text-xs text-muted-foreground">{c.name}</p>
                  <p
                    className={cn(
                      "text-sm font-semibold",
                      c.isGated
                        ? "text-muted-foreground line-through"
                        : getZScoreColor(c.goodnessZScore),
                    )}
                  >
                    {formatZScore(c.goodnessZScore)}
                  </p>
                  <p className="text-[10px] text-muted-foreground/70">
                    raw: {formatZScore(c.rawZScore)}
                  </p>
                  <p
                    className={cn(
                      "text-[10px]",
                      getConfidenceColor(c.confidence),
                    )}
                  >
                    conf: {(c.confidence * 100).toFixed(0)}%
                  </p>
                  {c.longTermPercentile !== null && (
                    <p className="text-[10px] text-muted-foreground/50">
                      P{c.longTermPercentile.toFixed(0)} all-time
                    </p>
                  )}
                  {c.isGated && (
                    <p className="text-[10px] text-red-400">{c.gateReason}</p>
                  )}
                  {!c.isGated && c.gateReason && (
                    <p className="text-[10px] text-muted-foreground/60">
                      {c.gateReason}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {dataSourceSummary.length > 0 && (
            <div className="mt-4 pt-4 border-t">
              <p className="text-sm font-medium mb-3">Smart Data Fusion</p>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-xs">
                {dataSourceSummary.map((s) => (
                  <div key={s.metric} className="p-2 rounded-lg bg-muted/30">
                    <p className="font-medium">{s.metric}</p>
                    <p className="text-muted-foreground">
                      <span className={PROVIDER_CONFIGS.garmin.colorClass}>
                        {s.garminOnly}
                        {PROVIDER_CONFIGS.garmin.shortName}
                      </span>{" "}
                      /{" "}
                      <span className={PROVIDER_CONFIGS.whoop.colorClass}>
                        {s.whoopOnly}
                        {PROVIDER_CONFIGS.whoop.shortName}
                      </span>
                      {s.blended > 0 && (
                        <span
                          className={`${PROVIDER_CONFIGS.blended.colorClass} ml-1`}
                        >
                          ({s.blended}🔗)
                        </span>
                      )}
                    </p>
                    <p className="text-muted-foreground/70">
                      conf: {(s.avgConfidence * 100).toFixed(0)}%
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 mb-2">
              <Heart className="h-4 w-4 text-red-500" />
              <span className="text-sm font-medium">HRV-RHR Imbalance</span>
            </div>
            <p
              className={cn(
                "text-2xl font-bold",
                getHrvRhrColor(recoveryMetrics.hrvRhrImbalance),
              )}
            >
              {recoveryMetrics.hrvRhrImbalance !== null
                ? recoveryMetrics.hrvRhrImbalance.toFixed(2)
                : "—"}
            </p>
            <p className="text-xs text-muted-foreground">
              {getHrvRhrLabel(recoveryMetrics.hrvRhrImbalance)}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 mb-2">
              <Moon className="h-4 w-4 text-indigo-500" />
              <span className="text-sm font-medium">
                Sleep Debt ({formatDaysLabel(shortTermDays)})
              </span>
            </div>
            <p
              className={cn(
                "text-2xl font-bold",
                getSleepDebtColor(sleepMetrics.sleepDebtShort),
              )}
            >
              {formatSleepMinutes(sleepMetrics.sleepDebtShort)}
            </p>
            <p className="text-xs text-muted-foreground">
              vs target {formatSleepMinutes(sleepMetrics.targetSleep)}/night
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 mb-2">
              <Zap className="h-4 w-4 text-orange-500" />
              <span className="text-sm font-medium">Acute:Chronic Ratio</span>
            </div>
            <p
              className={cn(
                "text-2xl font-bold",
                getAcwrColor(activityMetrics.acwr),
              )}
            >
              {activityMetrics.acwr !== null
                ? activityMetrics.acwr.toFixed(2)
                : "—"}
            </p>
            <p className="text-xs text-muted-foreground">
              {getAcwrLabel(activityMetrics.acwr)}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 mb-2">
              <Footprints className="h-4 w-4 text-emerald-500" />
              <span className="text-sm font-medium">Steps Trend</span>
            </div>
            <p
              className={cn(
                "text-2xl font-bold",
                getStepsChangeColor(activityMetrics.stepsChange),
              )}
            >
              {activityMetrics.stepsChange !== null
                ? `${activityMetrics.stepsChange > 0 ? "+" : ""}${Math.round(activityMetrics.stepsChange).toLocaleString()}`
                : "—"}
            </p>
            <p className="text-xs text-muted-foreground">
              {formatDaysLabel(trendWindow)} vs prev{" "}
              {formatDaysLabel(trendWindow)}
            </p>
          </CardContent>
        </Card>
      </div>

      <div>
        <h2 className="text-xl font-semibold mb-4">Individual Metrics</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {METRIC_REGISTRY.map((def) => {
            const computed = computedMetrics[def.key];
            return (
              <MetricCard
                key={def.key}
                title={def.title}
                icon={def.icon}
                iconColorClass={def.iconColorClass}
                iconBgClass={def.iconBgClass}
                baseline={computed.baseline}
                quality={computed.quality}
                format={(value) => def.format(value)}
                invertZScore={def.invertZScore}
                shortTermDays={shortTermDays}
                baselineDays={baselineDays}
                trendWindow={trendWindow}
                useShiftedZScore={useShiftedZScore}
              />
            );
          })}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Moon className="h-4 w-4" />
              Sleep Analysis
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-muted-foreground">Target</p>
                <p className="font-medium">
                  {formatSleepMinutes(sleepMetrics.targetSleep)}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  Consistency (CV)
                </p>
                <p className="font-medium">
                  {(sleepMetrics.sleepCV * 100).toFixed(1)}%
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  {formatDaysLabel(shortTermDays)} Average
                </p>
                <p className="font-medium">
                  {sleepMetrics.avgSleepShort !== null
                    ? formatSleepMinutes(sleepMetrics.avgSleepShort)
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  {formatDaysLabel(baselineDays)} Average
                </p>
                <p className="font-medium">
                  {sleepMetrics.avgSleepLong !== null
                    ? formatSleepMinutes(sleepMetrics.avgSleepLong)
                    : "—"}
                </p>
              </div>
            </div>
            <div className="pt-2 border-t">
              <div className="flex justify-between text-sm">
                <span>
                  Debt:{" "}
                  <span className="font-medium text-red-500">
                    {formatSleepMinutes(sleepMetrics.sleepDebtShort)}
                  </span>
                </span>
                <span>
                  Surplus:{" "}
                  <span className="font-medium text-green-500">
                    {formatSleepMinutes(sleepMetrics.sleepSurplusShort)}
                  </span>
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Activity className="h-4 w-4" />
              Activity Analysis
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-muted-foreground">
                  Steps {formatDaysLabel(shortTermDays)} avg
                </p>
                <p className="font-medium">
                  {activityMetrics.stepsAvgShort !== null
                    ? Math.round(activityMetrics.stepsAvgShort).toLocaleString()
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  Steps {formatDaysLabel(baselineDays)} avg
                </p>
                <p className="font-medium">
                  {activityMetrics.stepsAvgLong !== null
                    ? Math.round(activityMetrics.stepsAvgLong).toLocaleString()
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Acute Load</p>
                <p className="font-medium">
                  {activityMetrics.acuteLoad?.toFixed(1) ?? "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Chronic Load</p>
                <p className="font-medium">
                  {activityMetrics.chronicLoad?.toFixed(1) ?? "—"}
                </p>
              </div>
            </div>
            <div className="pt-2 border-t">
              <div className="flex justify-between text-sm">
                <span>
                  ACWR:{" "}
                  <span className="font-medium">
                    {activityMetrics.acwr?.toFixed(2) ?? "—"}
                  </span>
                </span>
                <span>
                  Steps CV:{" "}
                  <span className="font-medium">
                    {(activityMetrics.stepsCV * 100).toFixed(0)}%
                  </span>
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Scale className="h-4 w-4" />
              Weight Analysis
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-muted-foreground">
                  EMA {formatDaysLabel(shortTermDays)}
                </p>
                <p className="font-medium">
                  {weightMetrics.emaShort !== null
                    ? `${weightMetrics.emaShort.toFixed(1)} kg`
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  EMA {formatDaysLabel(baselineDays)}
                </p>
                <p className="font-medium">
                  {weightMetrics.emaLong !== null
                    ? `${weightMetrics.emaLong.toFixed(1)} kg`
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  {formatDaysLabel(shortTermDays)} change
                </p>
                <p
                  className={cn(
                    "font-medium",
                    getWeightChangeColor(weightMetrics.periodChange),
                  )}
                >
                  {weightMetrics.periodChange !== null
                    ? `${weightMetrics.periodChange > 0 ? "+" : ""}${weightMetrics.periodChange.toFixed(2)} kg`
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  Volatility {formatDaysLabel(shortTermDays)}
                </p>
                <p className="font-medium">
                  ±{weightMetrics.volatilityShort.toFixed(2)} kg
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Brain className="h-4 w-4" />
              Stress Analysis
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-muted-foreground">
                  {formatDaysLabel(shortTermDays)} load
                </p>
                <p className="font-medium">
                  {recoveryMetrics.stressLoadShort !== null
                    ? Math.round(recoveryMetrics.stressLoadShort)
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  {formatDaysLabel(baselineDays)} load
                </p>
                <p className="font-medium">
                  {recoveryMetrics.stressLoadLong !== null
                    ? Math.round(recoveryMetrics.stressLoadLong)
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Trend</p>
                <p
                  className={cn(
                    "font-medium",
                    getStressTrendColor(recoveryMetrics.stressTrend),
                  )}
                >
                  {recoveryMetrics.stressTrend !== null
                    ? `${recoveryMetrics.stressTrend > 0 ? "+" : ""}${recoveryMetrics.stressTrend.toFixed(1)}`
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Recovery CV</p>
                <p className="font-medium">
                  {(recoveryMetrics.recoveryCV * 100).toFixed(1)}%
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Clinical Alerts Section */}
      {clinicalAlerts?.anyAlert && (
        <Card className="border-red-500/50 bg-red-500/5">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-red-500/20">
                <ShieldAlert className="h-6 w-6 text-red-500" />
              </div>
              <div>
                <CardTitle className="text-red-600 dark:text-red-400">
                  Clinical Alerts
                </CardTitle>
                <CardDescription>
                  Potential health concerns detected
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
              {clinicalAlerts.persistentTachycardia && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <div className="flex items-center gap-2 mb-1">
                    <Heart className="h-4 w-4 text-red-500" />
                    <span className="text-sm font-medium text-red-600 dark:text-red-400">
                      Elevated RHR
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {clinicalAlerts.tachycardiaDays} consecutive days above
                    baseline +2σ
                  </p>
                </div>
              )}
              {clinicalAlerts.acuteHRVDrop && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <div className="flex items-center gap-2 mb-1">
                    <TrendingDown className="h-4 w-4 text-red-500" />
                    <span className="text-sm font-medium text-red-600 dark:text-red-400">
                      Acute HRV Drop
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {clinicalAlerts.hrvDropPercent !== null
                      ? `${(clinicalAlerts.hrvDropPercent * 100).toFixed(0)}%`
                      : "—"}{" "}
                    drop from previous day
                  </p>
                </div>
              )}
              {clinicalAlerts.progressiveWeightLoss && (
                <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
                  <div className="flex items-center gap-2 mb-1">
                    <Scale className="h-4 w-4 text-yellow-500" />
                    <span className="text-sm font-medium text-yellow-600 dark:text-yellow-400">
                      Weight Loss
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {clinicalAlerts.weightLossPercent !== null
                      ? `${(clinicalAlerts.weightLossPercent * 100).toFixed(1)}%`
                      : "—"}{" "}
                    loss over 30 days
                  </p>
                </div>
              )}
              {clinicalAlerts.severeOvertraining && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <div className="flex items-center gap-2 mb-1">
                    <Flame className="h-4 w-4 text-red-500" />
                    <span className="text-sm font-medium text-red-600 dark:text-red-400">
                      Overtraining Risk
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    High ACWR + suppressed HRV detected
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Advanced Metrics Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Overreaching Score */}
        {overreachingMetrics && (
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <Flame className="h-4 w-4 text-orange-500" />
                <CardTitle className="text-base">Overreaching Score</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-2 mb-3">
                <span
                  className={cn(
                    "text-3xl font-bold",
                    overreachingMetrics.riskLevel === "low" && "text-green-500",
                    overreachingMetrics.riskLevel === "moderate" &&
                      "text-yellow-500",
                    overreachingMetrics.riskLevel === "high" &&
                      "text-orange-500",
                    overreachingMetrics.riskLevel === "critical" &&
                      "text-red-500",
                  )}
                >
                  {overreachingMetrics.score !== null
                    ? overreachingMetrics.score.toFixed(2)
                    : "—"}
                </span>
                {overreachingMetrics.riskLevel && (
                  <span
                    className={cn(
                      "text-sm font-medium px-2 py-0.5 rounded-full",
                      overreachingMetrics.riskLevel === "low" &&
                        "bg-green-500/10 text-green-600",
                      overreachingMetrics.riskLevel === "moderate" &&
                        "bg-yellow-500/10 text-yellow-600",
                      overreachingMetrics.riskLevel === "high" &&
                        "bg-orange-500/10 text-orange-600",
                      overreachingMetrics.riskLevel === "critical" &&
                        "bg-red-500/10 text-red-600",
                    )}
                  >
                    {overreachingMetrics.riskLevel}
                  </span>
                )}
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <p className="text-xs text-muted-foreground">
                    Low HRV streak
                  </p>
                  <p className="font-medium">
                    {overreachingMetrics.consecutiveLowRecoveryDays} days
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Components</p>
                  <div className="text-xs space-x-1">
                    {overreachingMetrics.components.strainComponent !==
                      null && (
                      <span className="text-orange-500">
                        S:
                        {overreachingMetrics.components.strainComponent.toFixed(
                          1,
                        )}
                      </span>
                    )}
                    {overreachingMetrics.components.hrvComponent !== null && (
                      <span className="text-red-500">
                        H:
                        {overreachingMetrics.components.hrvComponent.toFixed(1)}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Correlations */}
        {correlationMetrics && (
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <GitBranch className="h-4 w-4 text-purple-500" />
                <CardTitle className="text-base">Correlations</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">
                    HRV ↔ RHR
                  </span>
                  <span
                    className={cn(
                      "font-mono text-sm",
                      getCorrelationColor(correlationMetrics.hrvRhrCorrelation),
                    )}
                  >
                    {correlationMetrics.hrvRhrCorrelation !== null
                      ? correlationMetrics.hrvRhrCorrelation.toFixed(2)
                      : "—"}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">
                    Sleep → HRV
                  </span>
                  <span
                    className={cn(
                      "font-mono text-sm",
                      correlationMetrics.sleepHrvLagCorrelation !== null &&
                        correlationMetrics.sleepHrvLagCorrelation > 0.3
                        ? "text-green-500"
                        : "text-muted-foreground",
                    )}
                  >
                    {correlationMetrics.sleepHrvLagCorrelation !== null
                      ? correlationMetrics.sleepHrvLagCorrelation.toFixed(2)
                      : "—"}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">
                    Strain → Recovery
                  </span>
                  <span
                    className={cn(
                      "font-mono text-sm",
                      correlationMetrics.strainRecoveryCorrelation !== null &&
                        correlationMetrics.strainRecoveryCorrelation < -0.2
                        ? "text-green-500"
                        : "text-muted-foreground",
                    )}
                  >
                    {correlationMetrics.strainRecoveryCorrelation !== null
                      ? correlationMetrics.strainRecoveryCorrelation.toFixed(2)
                      : "—"}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground pt-1 border-t">
                  Sample size: {correlationMetrics.sampleSize} days
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Velocity / Rate of Change */}
        {velocityMetrics && (
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-blue-500" />
                <CardTitle className="text-base">Trends (Velocity)</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {[
                  {
                    label: "HRV",
                    value: velocityMetrics.hrvVelocity,
                    unit: "ms/d",
                    status: velocityMetrics.interpretation.hrv,
                  },
                  {
                    label: "RHR",
                    value: velocityMetrics.rhrVelocity,
                    unit: "bpm/d",
                    status: velocityMetrics.interpretation.rhr,
                  },
                  {
                    label: "Weight",
                    value: velocityMetrics.weightVelocity,
                    unit: "kg/d",
                    status: velocityMetrics.interpretation.weight,
                  },
                  {
                    label: "Sleep",
                    value: velocityMetrics.sleepVelocity,
                    unit: "min/d",
                    status: velocityMetrics.interpretation.sleep,
                  },
                ].map(({ label, value, unit, status }) => (
                  <div
                    key={label}
                    className="flex justify-between items-center"
                  >
                    <span className="text-sm text-muted-foreground">
                      {label}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm">
                        {value !== null
                          ? `${value > 0 ? "+" : ""}${value.toFixed(2)} ${unit}`
                          : "—"}
                      </span>
                      {status && (
                        <span
                          className={cn(
                            "text-xs",
                            status === "improving" && "text-green-500",
                            status === "declining" && "text-red-500",
                            status === "stable" && "text-muted-foreground",
                            status === "gaining" && "text-yellow-500",
                            status === "losing" && "text-blue-500",
                          )}
                        >
                          {status === "improving" && (
                            <ArrowUpRight className="h-3 w-3" />
                          )}
                          {status === "declining" && (
                            <ArrowDownRight className="h-3 w-3" />
                          )}
                          {status === "stable" && <Minus className="h-3 w-3" />}
                          {status === "gaining" && (
                            <ArrowUpRight className="h-3 w-3" />
                          )}
                          {status === "losing" && (
                            <ArrowDownRight className="h-3 w-3" />
                          )}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Anomaly Detection */}
      {anomalyMetrics !== null && anomalyMetrics.anomalyCount > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Radar className="h-4 w-4 text-amber-500" />
                <CardTitle className="text-base">
                  Anomalies Detected ({anomalyMetrics.anomalyCount})
                </CardTitle>
              </div>
              {anomalyMetrics.hasRecentAnomaly && (
                <span className="text-xs px-2 py-1 rounded-full bg-amber-500/10 text-amber-600">
                  Recent
                </span>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-4">
              {anomalyMetrics.anomalies.slice(0, 8).map((anomaly, i) => (
                <div
                  key={`${anomaly.date}-${anomaly.metric}-${String(i)}`}
                  className={cn(
                    "p-2 rounded-lg border text-sm",
                    anomaly.severity === "critical" &&
                      "bg-red-500/10 border-red-500/30",
                    anomaly.severity === "alert" &&
                      "bg-orange-500/10 border-orange-500/30",
                    anomaly.severity === "warning" &&
                      "bg-yellow-500/10 border-yellow-500/30",
                  )}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium">{anomaly.metric}</span>
                    <span
                      className={cn(
                        "text-xs px-1.5 py-0.5 rounded",
                        anomaly.severity === "critical" &&
                          "bg-red-500/20 text-red-600",
                        anomaly.severity === "alert" &&
                          "bg-orange-500/20 text-orange-600",
                        anomaly.severity === "warning" &&
                          "bg-yellow-500/20 text-yellow-600",
                      )}
                    >
                      {anomaly.severity}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    z={anomaly.zScore.toFixed(1)} on{" "}
                    {new Date(anomaly.date).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                    })}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recovery Capacity */}
      {recoveryCapacity && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <RefreshCw className="h-4 w-4 text-green-500" />
              <CardTitle className="text-base">Recovery Capacity</CardTitle>
            </div>
            <CardDescription>
              How quickly HRV returns to baseline after high strain
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-muted-foreground">
                  Avg Recovery Days
                </p>
                <p className="text-lg font-semibold">
                  {recoveryCapacity.avgRecoveryDays !== null
                    ? `${recoveryCapacity.avgRecoveryDays.toFixed(1)} days`
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  Recovery Efficiency
                </p>
                <p className="text-lg font-semibold">
                  {recoveryCapacity.recoveryEfficiency !== null
                    ? recoveryCapacity.recoveryEfficiency.toFixed(2)
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  High Strain Events
                </p>
                <p className="text-lg font-semibold">
                  {recoveryCapacity.highStrainEvents}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  Recovered Events
                </p>
                <p className="text-lg font-semibold">
                  {recoveryCapacity.recoveredEvents}
                </p>
              </div>
            </div>
            {recoveryCapacity.highStrainEvents > 0 && (
              <p className="text-xs text-muted-foreground mt-2">
                Recovery rate:{" "}
                {Math.round(
                  (recoveryCapacity.recoveredEvents /
                    recoveryCapacity.highStrainEvents) *
                    100,
                )}
                %
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Pre-Illness Risk Signal */}
      {illnessRisk && (
        <Card
          className={cn(
            illnessRisk.riskLevel === "high" && "border-red-500/50",
            illnessRisk.riskLevel === "moderate" && "border-yellow-500/50",
          )}
        >
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <Thermometer
                className={cn(
                  "h-4 w-4",
                  illnessRisk.riskLevel === "high" && "text-red-500",
                  illnessRisk.riskLevel === "moderate" && "text-yellow-500",
                  illnessRisk.riskLevel === "low" && "text-green-500",
                  illnessRisk.riskLevel === null && "text-muted-foreground",
                )}
              />
              <CardTitle className="text-base">Pre-Illness Risk</CardTitle>
              {illnessRisk.riskLevel && (
                <span
                  className={cn(
                    "text-xs px-1.5 py-0.5 rounded ml-auto",
                    illnessRisk.riskLevel === "high" &&
                      "bg-red-500/20 text-red-600",
                    illnessRisk.riskLevel === "moderate" &&
                      "bg-yellow-500/20 text-yellow-600",
                    illnessRisk.riskLevel === "low" &&
                      "bg-green-500/20 text-green-600",
                  )}
                >
                  {illnessRisk.riskLevel}
                </span>
              )}
            </div>
            <CardDescription>
              Combined HRV drop, RHR rise, and sleep deficit signal
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">
                  Combined Deviation
                </span>
                <span className="font-mono text-sm">
                  {illnessRisk.combinedDeviation !== null
                    ? illnessRisk.combinedDeviation.toFixed(2)
                    : "—"}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">
                  Consecutive Days
                </span>
                <span className="font-mono text-sm">
                  {illnessRisk.consecutiveDaysElevated}
                </span>
              </div>
              <div className="text-xs text-muted-foreground pt-2 border-t">
                <span className="block">
                  HRV Drop: {illnessRisk.components.hrvDrop?.toFixed(2) ?? "—"}σ
                </span>
                <span className="block">
                  RHR Rise: {illnessRisk.components.rhrRise?.toFixed(2) ?? "—"}σ
                </span>
                <span className="block">
                  Sleep Drop:{" "}
                  {illnessRisk.components.sleepDrop?.toFixed(2) ?? "—"}σ
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* HRV-RHR Decorrelation */}
      {decorrelationAlert?.currentCorrelation !== null &&
        decorrelationAlert && (
          <Card
            className={
              decorrelationAlert.isDecorrelated ? "border-orange-500/50" : ""
            }
          >
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <Unlink
                  className={cn(
                    "h-4 w-4",
                    decorrelationAlert.isDecorrelated
                      ? "text-orange-500"
                      : "text-muted-foreground",
                  )}
                />
                <CardTitle className="text-base">HRV-RHR Correlation</CardTitle>
                {decorrelationAlert.isDecorrelated && (
                  <span className="text-xs px-1.5 py-0.5 rounded ml-auto bg-orange-500/20 text-orange-600">
                    decorrelated
                  </span>
                )}
              </div>
              <CardDescription>
                Normally negative correlation; decorrelation may signal stress
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">
                    Current (14d)
                  </span>
                  <span className="font-mono text-sm">
                    r = {decorrelationAlert.currentCorrelation.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">
                    Baseline ({baselineDays}d)
                  </span>
                  <span className="font-mono text-sm">
                    r ={" "}
                    {decorrelationAlert.baselineCorrelation?.toFixed(2) ?? "—"}
                  </span>
                </div>
                {decorrelationAlert.correlationDelta !== null && (
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-muted-foreground">Delta</span>
                    <span
                      className={cn(
                        "font-mono text-sm",
                        decorrelationAlert.correlationDelta > 0.1 &&
                          "text-orange-500",
                      )}
                    >
                      {decorrelationAlert.correlationDelta > 0 ? "+" : ""}
                      {decorrelationAlert.correlationDelta.toFixed(2)}
                    </span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )}

      {/* Advanced Insights (from backend analytics) */}
      {analyticsError && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">
              Failed to load advanced insights:{" "}
              {analyticsError instanceof Error
                ? analyticsError.message
                : "Unknown error"}
            </p>
          </CardContent>
        </Card>
      )}
      {analyticsLoading && !advancedInsights && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">
              Loading advanced insights...
            </p>
          </CardContent>
        </Card>
      )}
      {advancedInsights && (
        <>
          <div>
            <h2 className="text-xl font-semibold mb-4">Advanced Insights</h2>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {/* HRV Advanced */}
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <Heart className="h-4 w-4 text-rose-500" />
                    <CardTitle className="text-base">HRV Advanced</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">
                        lnRMSSD
                      </span>
                      <span className="font-mono text-sm font-semibold">
                        {advancedInsights.hrv_advanced.ln_rmssd_current?.toFixed(
                          2,
                        ) ?? "—"}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">
                        7d Mean
                      </span>
                      <span className="font-mono text-sm">
                        {advancedInsights.hrv_advanced.ln_rmssd_mean_7d?.toFixed(
                          2,
                        ) ?? "—"}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">
                        SD (7d)
                      </span>
                      <span
                        className={cn(
                          "font-mono text-sm",
                          getHrvSdColor(
                            advancedInsights.hrv_advanced.ln_rmssd_sd_7d,
                          ),
                        )}
                      >
                        {advancedInsights.hrv_advanced.ln_rmssd_sd_7d?.toFixed(
                          3,
                        ) ?? "—"}
                      </span>
                    </div>
                    <div className="pt-2 border-t text-xs text-muted-foreground">
                      <div className="flex justify-between">
                        <span>HRV-RHR r(14d)</span>
                        <span className="font-mono">
                          {advancedInsights.hrv_advanced.hrv_rhr_rolling_r_14d?.toFixed(
                            2,
                          ) ?? "—"}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>HRV-RHR r(60d)</span>
                        <span className="font-mono">
                          {advancedInsights.hrv_advanced.hrv_rhr_rolling_r_60d?.toFixed(
                            2,
                          ) ?? "—"}
                        </span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Sleep Quality */}
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <Moon className="h-4 w-4 text-indigo-500" />
                    <CardTitle className="text-base">Sleep Quality</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">
                        Efficiency
                      </span>
                      <span className="font-mono text-sm">
                        {advancedInsights.sleep_quality.efficiency?.toFixed(
                          1,
                        ) ?? "—"}
                        %
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">
                        Deep Sleep
                      </span>
                      <span
                        className={cn(
                          "font-mono text-sm",
                          advancedInsights.sleep_quality.deep_sleep_pct !==
                            null &&
                            advancedInsights.sleep_quality.deep_sleep_pct >= 15
                            ? "text-green-500"
                            : "text-yellow-500",
                        )}
                      >
                        {advancedInsights.sleep_quality.deep_sleep_pct?.toFixed(
                          1,
                        ) ?? "—"}
                        %
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">
                        REM Sleep
                      </span>
                      <span
                        className={cn(
                          "font-mono text-sm",
                          advancedInsights.sleep_quality.rem_sleep_pct !==
                            null &&
                            advancedInsights.sleep_quality.rem_sleep_pct >= 20
                            ? "text-green-500"
                            : "text-yellow-500",
                        )}
                      >
                        {advancedInsights.sleep_quality.rem_sleep_pct?.toFixed(
                          1,
                        ) ?? "—"}
                        %
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">
                        Consistency
                      </span>
                      <span className="font-mono text-sm">
                        {advancedInsights.sleep_quality.consistency_score?.toFixed(
                          0,
                        ) ?? "—"}
                        /100
                      </span>
                    </div>
                    <div className="pt-2 border-t text-xs text-muted-foreground">
                      <div className="flex justify-between">
                        <span>Sleep→HRV</span>
                        <span className="font-mono">
                          r={" "}
                          {advancedInsights.sleep_quality.sleep_hrv_responsiveness?.toFixed(
                            2,
                          ) ?? "—"}
                          {advancedInsights.sleep_quality.sleep_hrv_p_value !==
                            null &&
                            advancedInsights.sleep_quality.sleep_hrv_p_value <
                              0.05 && (
                              <span className="text-green-500 ml-1">*</span>
                            )}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>Fragmentation</span>
                        <span className="font-mono">
                          {advancedInsights.sleep_quality.fragmentation_index?.toFixed(
                            1,
                          ) ?? "—"}
                          /hr
                        </span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Fitness & Training Load */}
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <Dumbbell className="h-4 w-4 text-blue-500" />
                    <CardTitle className="text-base">
                      Fitness & Training
                    </CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">
                        Last Workout
                      </span>
                      <span
                        className={cn(
                          "font-mono text-sm",
                          advancedInsights.fitness.days_since_last_workout !==
                            null &&
                            advancedInsights.fitness.days_since_last_workout > 7
                            ? "text-red-500"
                            : "text-green-500",
                        )}
                      >
                        {advancedInsights.fitness.days_since_last_workout !==
                        null
                          ? `${String(advancedInsights.fitness.days_since_last_workout)}d ago`
                          : "—"}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">
                        Frequency
                      </span>
                      <span className="font-mono text-sm">
                        {advancedInsights.fitness.training_frequency_7d}/w ·{" "}
                        {advancedInsights.fitness.training_frequency_30d}/mo
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">
                        CTL / ATL / TSB
                      </span>
                      <span className="font-mono text-sm">
                        {advancedInsights.fitness.ctl?.toFixed(1) ?? "—"} /{" "}
                        {advancedInsights.fitness.atl?.toFixed(1) ?? "—"} /{" "}
                        <span
                          className={cn(
                            getTsbColor(advancedInsights.fitness.tsb),
                          )}
                        >
                          {advancedInsights.fitness.tsb?.toFixed(1) ?? "—"}
                        </span>
                      </span>
                    </div>
                    {advancedInsights.fitness.vo2_max_current !== null && (
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-muted-foreground">
                          VO2max
                        </span>
                        <span className="font-mono text-sm">
                          {advancedInsights.fitness.vo2_max_current.toFixed(1)}
                        </span>
                      </div>
                    )}
                    <div className="pt-2 border-t text-xs text-muted-foreground">
                      <div className="flex justify-between">
                        <span>Monotony</span>
                        <span className="font-mono">
                          {advancedInsights.fitness.monotony?.toFixed(2) ?? "—"}
                        </span>
                      </div>
                      {advancedInsights.fitness.detraining_score !== null && (
                        <div className="flex justify-between">
                          <span>Detraining</span>
                          <span
                            className={cn(
                              "font-mono",
                              advancedInsights.fitness.detraining_score > 0.5
                                ? "text-red-500"
                                : "",
                            )}
                          >
                            {(
                              advancedInsights.fitness.detraining_score * 100
                            ).toFixed(0)}
                            %
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Allostatic Load */}
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <Beaker className="h-4 w-4 text-amber-500" />
                    <CardTitle className="text-base">Allostatic Load</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex items-baseline gap-2 mb-2">
                      <span
                        className={cn(
                          "text-2xl font-bold",
                          getAllostaticScoreColor(
                            advancedInsights.allostatic_load.composite_score,
                          ),
                        )}
                      >
                        {advancedInsights.allostatic_load.composite_score?.toFixed(
                          0,
                        ) ?? "—"}
                      </span>
                      <span className="text-sm text-muted-foreground">
                        / 100
                      </span>
                    </div>
                    {Object.entries(
                      advancedInsights.allostatic_load.breach_rates,
                    ).map(([metric, rate]) => (
                      <div
                        key={metric}
                        className="flex justify-between items-center text-sm"
                      >
                        <span className="text-muted-foreground capitalize">
                          {metric}
                        </span>
                        <span
                          className={cn(
                            "font-mono",
                            getDysregulationRateColor(rate),
                          )}
                        >
                          {(rate * 100).toFixed(0)}%
                        </span>
                      </div>
                    ))}
                    {advancedInsights.allostatic_load.trend !== null && (
                      <div className="pt-2 border-t text-xs text-muted-foreground">
                        <div className="flex justify-between">
                          <span>Trend</span>
                          <span
                            className={cn(
                              "font-mono",
                              advancedInsights.allostatic_load.trend > 0
                                ? "text-red-500"
                                : "text-green-500",
                            )}
                          >
                            {advancedInsights.allostatic_load.trend > 0
                              ? "+"
                              : ""}
                            {advancedInsights.allostatic_load.trend.toFixed(1)}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Recovery Enhanced */}
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <RefreshCw className="h-4 w-4 text-emerald-500" />
                    <CardTitle className="text-base">
                      Recovery Advanced
                    </CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">
                        Recovery Debt (30d)
                      </span>
                      <span
                        className={cn(
                          "font-mono text-sm",
                          advancedInsights.recovery_enhanced.recovery_debt !==
                            null &&
                            advancedInsights.recovery_enhanced.recovery_debt >
                              300
                            ? "text-red-500"
                            : "",
                        )}
                      >
                        {advancedInsights.recovery_enhanced.recovery_debt?.toFixed(
                          0,
                        ) ?? "—"}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">
                        Strain:Recovery Mismatch
                      </span>
                      <span className="font-mono text-sm">
                        {advancedInsights.recovery_enhanced.strain_recovery_mismatch_7d?.toFixed(
                          1,
                        ) ?? "—"}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">
                        Recovery Half-Life
                      </span>
                      <span className="font-mono text-sm">
                        {advancedInsights.recovery_enhanced.recovery_half_life_days?.toFixed(
                          1,
                        ) ?? "—"}
                        d
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* HRV Residual Model */}
              {advancedInsights.cross_domain.hrv_residual.r_squared !==
                null && (
                <Card>
                  <CardHeader className="pb-2">
                    <div className="flex items-center gap-2">
                      <BarChart3 className="h-4 w-4 text-cyan-500" />
                      <CardTitle className="text-base">
                        HRV Predicted vs Actual
                      </CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-muted-foreground">
                          Predicted
                        </span>
                        <span className="font-mono text-sm">
                          {advancedInsights.cross_domain.hrv_residual.predicted?.toFixed(
                            1,
                          ) ?? "—"}
                        </span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-muted-foreground">
                          Actual
                          {advancedInsights.cross_domain.hrv_residual
                            .actual_date && (
                            <span className="text-[10px] ml-1 text-muted-foreground/60">
                              (
                              {toLocalDayDate(
                                advancedInsights.cross_domain.hrv_residual
                                  .actual_date,
                              ).toLocaleDateString("en-US", {
                                month: "short",
                                day: "numeric",
                              })}
                              )
                            </span>
                          )}
                        </span>
                        <span className="font-mono text-sm">
                          {advancedInsights.cross_domain.hrv_residual.actual?.toFixed(
                            1,
                          ) ?? "—"}
                        </span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-muted-foreground">
                          Residual
                        </span>
                        <span
                          className={cn(
                            "font-mono text-sm font-semibold",
                            advancedInsights.cross_domain.hrv_residual
                              .residual !== null &&
                              advancedInsights.cross_domain.hrv_residual
                                .residual > 0
                              ? "text-green-500"
                              : "text-red-500",
                          )}
                        >
                          {advancedInsights.cross_domain.hrv_residual
                            .residual !== null
                            ? `${advancedInsights.cross_domain.hrv_residual.residual > 0 ? "+" : ""}${advancedInsights.cross_domain.hrv_residual.residual.toFixed(1)}`
                            : "—"}
                        </span>
                      </div>
                      <div className="pt-2 border-t text-xs text-muted-foreground">
                        <div className="flex justify-between">
                          <span>R²</span>
                          <span className="font-mono">
                            {advancedInsights.cross_domain.hrv_residual.r_squared.toFixed(
                              3,
                            )}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>Features</span>
                          <span className="font-mono">
                            {advancedInsights.cross_domain.hrv_residual.model_features.join(
                              ", ",
                            )}
                          </span>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>

          {/* Lag Correlations */}
          {advancedInsights.lag_correlations.pairs.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <GitBranch className="h-4 w-4 text-violet-500" />
                  <CardTitle className="text-base">
                    Lag Cross-Correlations
                  </CardTitle>
                </div>
                <CardDescription>
                  How metrics influence each other across days
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
                  {advancedInsights.lag_correlations.pairs
                    .filter(
                      (p) =>
                        p.correlation !== null &&
                        p.p_value !== null &&
                        p.p_value < 0.1,
                    )
                    .sort(
                      (a, b) =>
                        Math.abs(b.correlation ?? 0) -
                        Math.abs(a.correlation ?? 0),
                    )
                    .slice(0, 9)
                    .map((pair) => (
                      <div
                        key={`${pair.metric_a}-${pair.metric_b}-${String(pair.lag_days)}`}
                        className="p-2 rounded-lg bg-muted/30 text-sm"
                      >
                        <div className="flex justify-between items-center">
                          <span className="text-muted-foreground">
                            {pair.metric_a} → {pair.metric_b} ({pair.lag_days}d)
                          </span>
                          <span
                            className={cn(
                              "font-mono font-medium",
                              getCrossCorrelationColor(pair.correlation),
                            )}
                          >
                            {pair.correlation?.toFixed(2) ?? "—"}
                            {pair.p_value !== null && pair.p_value < 0.05 && (
                              <span className="text-green-500 ml-0.5">*</span>
                            )}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground/60">
                          n={pair.sample_size}
                        </p>
                      </div>
                    ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Weekday vs Weekend */}
          {Object.keys(advancedInsights.cross_domain.weekday_weekend).length >
            0 && (
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-teal-500" />
                  <CardTitle className="text-base">
                    Weekday vs Weekend
                  </CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-4">
                  {Object.entries(
                    advancedInsights.cross_domain.weekday_weekend,
                  ).map(([metric, split]) => (
                    <div
                      key={metric}
                      className="p-2 rounded-lg bg-muted/30 text-sm"
                    >
                      <p className="font-medium capitalize mb-1">{metric}</p>
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>
                          Weekday: {split.weekday_mean?.toFixed(1) ?? "—"}
                        </span>
                        <span>
                          Weekend: {split.weekend_mean?.toFixed(1) ?? "—"}
                        </span>
                      </div>
                      {split.delta !== null && (
                        <p
                          className={cn(
                            "text-xs font-mono mt-1",
                            Math.abs(split.delta) > 5
                              ? "text-yellow-500"
                              : "text-muted-foreground",
                          )}
                        >
                          {split.delta > 0 ? "+" : ""}
                          {split.delta.toFixed(1)}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
