import { useState } from "react";
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
} from "../../lib/health/format";
import { PROVIDER_CONFIGS } from "../../lib/providers";
import {
  METRIC_REGISTRY,
  formatSleepMinutes,
  TREND_MODES,
  MODE_ORDER,
  type TrendMode,
} from "../../lib/metrics";
import type { MetricBaseline } from "../../types/api";
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

function getCrossCorrelationColor(value: number | null): string {
  if (value === null) return "";
  if (value > 0.3) return "text-green-500";
  if (value < -0.3) return "text-red-500";
  return "";
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

function DataQualityBadge({ baseline }: { baseline: MetricBaseline }) {
  const coveragePercent = Math.round(baseline.quality_coverage * 100);
  const confidencePercent = Math.round(baseline.quality_confidence * 100);
  let color = "text-green-600 dark:text-green-400";
  let Icon = CheckCircle;

  if (baseline.quality_confidence < 0.6) {
    color = "text-red-600 dark:text-red-400";
    Icon = AlertTriangle;
  } else if (baseline.quality_confidence < 0.8) {
    color = "text-yellow-600 dark:text-yellow-400";
    Icon = Clock;
  }

  return (
    <div className="flex items-center gap-1.5 text-xs">
      <Icon className={cn("h-3 w-3", color)} />
      <span className={color}>{confidencePercent}% conf</span>
      <span className="text-muted-foreground">({coveragePercent}% cov)</span>
      {baseline.latency_days !== null && baseline.latency_days > 1 && (
        <span className="text-muted-foreground">
          · {baseline.latency_days}d ago
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
  baseline: MetricBaseline;
  format: (value: number | null) => string;
  invertZScore?: boolean;
  shortTermDays: number;
  baselineDays: number;
  trendWindow: number;
  useShiftedZScore: boolean;
}

function MetricCard({
  title,
  icon: Icon,
  iconColorClass,
  iconBgClass,
  baseline,
  format: formatValue,
  invertZScore = false,
  shortTermDays,
  baselineDays,
  trendWindow,
  useShiftedZScore,
}: MetricCardProps) {
  const rawZScore = useShiftedZScore
    ? baseline.shifted_z_score
    : baseline.z_score;
  const displayZScore =
    invertZScore && rawZScore !== null ? -rawZScore : rawZScore;

  const zScoreLabel = useShiftedZScore ? "period z" : "z-score";

  const trendIcon = (() => {
    if (baseline.trend_slope === null) {
      return <Minus className="h-4 w-4 text-muted-foreground" />;
    }
    if (baseline.trend_slope > 0) {
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
          <DataQualityBadge baseline={baseline} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {baseline.valid_points === 0 ? (
          <p className="text-sm text-muted-foreground">No data available</p>
        ) : (
          <>
            <div className="flex items-baseline justify-between">
              <div>
                <span className="text-2xl font-bold">
                  {formatValue(baseline.current_value)}
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
                  {formatValue(baseline.short_term_mean)}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  {formatDaysLabel(baselineDays)} avg
                </p>
                <p className="font-medium">{formatValue(baseline.mean)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  trend ({formatDaysLabel(trendWindow)})
                </p>
                <div className="flex items-center gap-1">
                  {trendIcon}
                  <span className="font-medium">
                    {baseline.trend_slope !== null
                      ? `${baseline.trend_slope > 0 ? "+" : ""}${baseline.trend_slope.toFixed(2)}/d`
                      : "—"}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t">
              <span>CV: {(baseline.cv * 100).toFixed(1)}%</span>
              <span>Outliers: {(baseline.outlier_rate * 100).toFixed(1)}%</span>
              <span>{baseline.valid_points} pts</span>
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
  const {
    data: analyticsData,
    isLoading,
    isFetching,
    error,
  } = useAnalytics(mode);

  if (error) {
    return (
      <ErrorCard message={`Failed to load health data: ${error.message}`} />
    );
  }

  if (isLoading || !analyticsData) {
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
    health_score: healthScore,
    recovery_metrics: recoveryMetrics,
    sleep_metrics: sleepMetrics,
    activity_metrics: activityMetrics,
    weight_metrics: weightMetrics,
    clinical_alerts: clinicalAlerts,
    overreaching,
    correlations,
    velocity,
    anomalies,
    recovery_capacity: recoveryCapacity,
    illness_risk: illnessRisk,
    decorrelation,
    advanced_insights: advancedInsights,
    day_completeness: dayCompleteness,
    data_source_summary: dataSourceSummary,
    metric_baselines: metricBaselines,
    mode_config: modeConfig,
  } = analyticsData;

  const shortTermDays = modeConfig.short_term;
  const baselineDays = modeConfig.baseline;
  const trendWindow = modeConfig.trend_window;
  const useShiftedZScore = modeConfig.use_shifted_z_score;

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
          {isFetching && (
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
                {healthScore.training_load !== null
                  ? "Composite: recovery core (60%) + training load (20%) + behavior (20%)"
                  : "Composite: recovery core (75%) + behavior support (25%)"}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div
            className={cn(
              "grid gap-6 md:grid-cols-2",
              healthScore.training_load !== null
                ? "lg:grid-cols-4"
                : "lg:grid-cols-3",
            )}
          >
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
                  getHealthScoreColor(healthScore.recovery_core),
                )}
              >
                {healthScore.recovery_core !== null
                  ? healthScore.recovery_core.toFixed(2)
                  : "—"}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                HRV + RHR + Sleep + Stress
              </p>
            </div>
            {healthScore.training_load !== null && (
              <div className="text-center">
                <p className="text-sm text-muted-foreground mb-1">
                  Training Load
                </p>
                <p
                  className={cn(
                    "text-3xl font-bold",
                    getHealthScoreColor(healthScore.training_load),
                  )}
                >
                  {healthScore.training_load.toFixed(2)}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Strain optimality
                </p>
              </div>
            )}
            <div className="text-center">
              <p className="text-sm text-muted-foreground mb-1">
                Behavior Support
              </p>
              <p
                className={cn(
                  "text-3xl font-bold",
                  getHealthScoreColor(healthScore.behavior_support),
                )}
              >
                {healthScore.behavior_support !== null
                  ? healthScore.behavior_support.toFixed(2)
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
                {!(healthScore.steps_status as Record<string, boolean>)
                  .use_today && (
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
                    c.is_gated
                      ? "bg-muted/30 border border-dashed border-muted-foreground/30"
                      : "bg-muted/50",
                  )}
                >
                  <p className="text-xs text-muted-foreground">{c.name}</p>
                  <p
                    className={cn(
                      "text-sm font-semibold",
                      c.is_gated
                        ? "text-muted-foreground line-through"
                        : getZScoreColor(c.goodness_z_score),
                    )}
                  >
                    {formatZScore(c.goodness_z_score)}
                  </p>
                  <p className="text-[10px] text-muted-foreground/70">
                    raw: {formatZScore(c.raw_z_score)}
                  </p>
                  <p
                    className={cn(
                      "text-[10px]",
                      getConfidenceColor(c.confidence),
                    )}
                  >
                    conf: {(c.confidence * 100).toFixed(0)}%
                  </p>
                  {c.long_term_percentile !== null && (
                    <p className="text-[10px] text-muted-foreground/50">
                      P{c.long_term_percentile.toFixed(0)} all-time
                    </p>
                  )}
                  {c.is_gated && (
                    <p className="text-[10px] text-red-400">{c.gate_reason}</p>
                  )}
                  {!c.is_gated && c.gate_reason && (
                    <p className="text-[10px] text-muted-foreground/60">
                      {c.gate_reason}
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
                        {s.garmin_only}
                        {PROVIDER_CONFIGS.garmin.shortName}
                      </span>{" "}
                      /{" "}
                      <span className={PROVIDER_CONFIGS.whoop.colorClass}>
                        {s.whoop_only}
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
                      conf: {(s.avg_confidence * 100).toFixed(0)}%
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
                getHrvRhrColor(recoveryMetrics.hrv_rhr_imbalance),
              )}
            >
              {recoveryMetrics.hrv_rhr_imbalance !== null
                ? recoveryMetrics.hrv_rhr_imbalance.toFixed(2)
                : "—"}
            </p>
            <p className="text-xs text-muted-foreground">
              {getHrvRhrLabel(recoveryMetrics.hrv_rhr_imbalance)}
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
                getSleepDebtColor(sleepMetrics.sleep_debt_short),
              )}
            >
              {formatSleepMinutes(sleepMetrics.sleep_debt_short)}
            </p>
            <p className="text-xs text-muted-foreground">
              vs target {formatSleepMinutes(sleepMetrics.target_sleep)}/night
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
                getStepsChangeColor(activityMetrics.steps_change),
              )}
            >
              {activityMetrics.steps_change !== null
                ? `${activityMetrics.steps_change > 0 ? "+" : ""}${Math.round(activityMetrics.steps_change).toLocaleString()}`
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
          {METRIC_REGISTRY.filter((def) => def.key in metricBaselines).map(
            (def) => {
              const baseline = metricBaselines[def.key];
              return (
                <MetricCard
                  key={def.key}
                  title={def.title}
                  icon={def.icon}
                  iconColorClass={def.iconColorClass}
                  iconBgClass={def.iconBgClass}
                  baseline={baseline}
                  format={(value) => def.format(value)}
                  invertZScore={def.invertZScore}
                  shortTermDays={shortTermDays}
                  baselineDays={baselineDays}
                  trendWindow={trendWindow}
                  useShiftedZScore={useShiftedZScore}
                />
              );
            },
          )}
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
                  {formatSleepMinutes(sleepMetrics.target_sleep)}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  Consistency (CV)
                </p>
                <p className="font-medium">
                  {(sleepMetrics.sleep_cv * 100).toFixed(1)}%
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  {formatDaysLabel(shortTermDays)} Average
                </p>
                <p className="font-medium">
                  {sleepMetrics.avg_sleep_short !== null
                    ? formatSleepMinutes(sleepMetrics.avg_sleep_short)
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  {formatDaysLabel(baselineDays)} Average
                </p>
                <p className="font-medium">
                  {sleepMetrics.avg_sleep_long !== null
                    ? formatSleepMinutes(sleepMetrics.avg_sleep_long)
                    : "—"}
                </p>
              </div>
            </div>
            <div className="pt-2 border-t">
              <div className="flex justify-between text-sm">
                <span>
                  Debt:{" "}
                  <span className="font-medium text-red-500">
                    {formatSleepMinutes(sleepMetrics.sleep_debt_short)}
                  </span>
                </span>
                <span>
                  Surplus:{" "}
                  <span className="font-medium text-green-500">
                    {formatSleepMinutes(sleepMetrics.sleep_surplus_short)}
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
                  {activityMetrics.steps_avg_short !== null
                    ? Math.round(
                        activityMetrics.steps_avg_short,
                      ).toLocaleString()
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  Steps {formatDaysLabel(baselineDays)} avg
                </p>
                <p className="font-medium">
                  {activityMetrics.steps_avg_long !== null
                    ? Math.round(
                        activityMetrics.steps_avg_long,
                      ).toLocaleString()
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Acute Load</p>
                <p className="font-medium">
                  {activityMetrics.acute_load?.toFixed(1) ?? "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Chronic Load</p>
                <p className="font-medium">
                  {activityMetrics.chronic_load?.toFixed(1) ?? "—"}
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
                    {(activityMetrics.steps_cv * 100).toFixed(0)}%
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
                  {weightMetrics.ema_short !== null
                    ? `${weightMetrics.ema_short.toFixed(1)} kg`
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  EMA {formatDaysLabel(baselineDays)}
                </p>
                <p className="font-medium">
                  {weightMetrics.ema_long !== null
                    ? `${weightMetrics.ema_long.toFixed(1)} kg`
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
                    getWeightChangeColor(weightMetrics.period_change),
                  )}
                >
                  {weightMetrics.period_change !== null
                    ? `${weightMetrics.period_change > 0 ? "+" : ""}${weightMetrics.period_change.toFixed(2)} kg`
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  Volatility {formatDaysLabel(shortTermDays)}
                </p>
                <p className="font-medium">
                  ±{weightMetrics.volatility_short.toFixed(2)} kg
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
                  {recoveryMetrics.stress_load_short !== null
                    ? Math.round(recoveryMetrics.stress_load_short)
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">
                  {formatDaysLabel(baselineDays)} load
                </p>
                <p className="font-medium">
                  {recoveryMetrics.stress_load_long !== null
                    ? Math.round(recoveryMetrics.stress_load_long)
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Trend</p>
                <p
                  className={cn(
                    "font-medium",
                    getStressTrendColor(recoveryMetrics.stress_trend),
                  )}
                >
                  {recoveryMetrics.stress_trend !== null
                    ? `${recoveryMetrics.stress_trend > 0 ? "+" : ""}${recoveryMetrics.stress_trend.toFixed(1)}`
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Recovery CV</p>
                <p className="font-medium">
                  {recoveryMetrics.recovery_cv !== null
                    ? `${(recoveryMetrics.recovery_cv * 100).toFixed(1)}%`
                    : "—"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {clinicalAlerts.any_alert && (
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
              {clinicalAlerts.persistent_tachycardia && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <div className="flex items-center gap-2 mb-1">
                    <Heart className="h-4 w-4 text-red-500" />
                    <span className="text-sm font-medium text-red-600 dark:text-red-400">
                      Elevated RHR
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {clinicalAlerts.tachycardia_days} consecutive days above
                    baseline +2σ
                  </p>
                </div>
              )}
              {clinicalAlerts.acute_hrv_drop && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <div className="flex items-center gap-2 mb-1">
                    <TrendingDown className="h-4 w-4 text-red-500" />
                    <span className="text-sm font-medium text-red-600 dark:text-red-400">
                      Acute HRV Drop
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {clinicalAlerts.hrv_drop_percent !== null
                      ? `${(clinicalAlerts.hrv_drop_percent * 100).toFixed(0)}%`
                      : "—"}{" "}
                    drop from previous day
                  </p>
                </div>
              )}
              {clinicalAlerts.progressive_weight_loss && (
                <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
                  <div className="flex items-center gap-2 mb-1">
                    <Scale className="h-4 w-4 text-yellow-500" />
                    <span className="text-sm font-medium text-yellow-600 dark:text-yellow-400">
                      Weight Loss
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {clinicalAlerts.weight_loss_percent !== null
                      ? `${(clinicalAlerts.weight_loss_percent * 100).toFixed(1)}%`
                      : "—"}{" "}
                    loss over 30 days
                  </p>
                </div>
              )}
              {clinicalAlerts.severe_overtraining && (
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

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
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
                  overreaching.risk_level === "low" && "text-green-500",
                  overreaching.risk_level === "moderate" && "text-yellow-500",
                  overreaching.risk_level === "high" && "text-orange-500",
                  overreaching.risk_level === "critical" && "text-red-500",
                )}
              >
                {overreaching.score !== null
                  ? overreaching.score.toFixed(2)
                  : "—"}
              </span>
              {overreaching.risk_level && (
                <span
                  className={cn(
                    "text-sm font-medium px-2 py-0.5 rounded-full",
                    overreaching.risk_level === "low" &&
                      "bg-green-500/10 text-green-600",
                    overreaching.risk_level === "moderate" &&
                      "bg-yellow-500/10 text-yellow-600",
                    overreaching.risk_level === "high" &&
                      "bg-orange-500/10 text-orange-600",
                    overreaching.risk_level === "critical" &&
                      "bg-red-500/10 text-red-600",
                  )}
                >
                  {overreaching.risk_level}
                </span>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">Low HRV streak</p>
                <p className="font-medium">
                  {overreaching.consecutive_low_recovery_days} days
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Components</p>
                <div className="text-xs space-x-1">
                  {(overreaching.components.strain_component ?? null) !==
                    null && (
                    <span className="text-orange-500">
                      S:
                      {(
                        overreaching.components.strain_component as number
                      ).toFixed(1)}
                    </span>
                  )}
                  {(overreaching.components.hrv_component ?? null) !== null && (
                    <span className="text-red-500">
                      H:
                      {(
                        overreaching.components.hrv_component as number
                      ).toFixed(1)}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

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
                <span className="text-sm text-muted-foreground">HRV ↔ RHR</span>
                <span
                  className={cn(
                    "font-mono text-sm",
                    getCorrelationColor(correlations.hrv_rhr_correlation),
                  )}
                >
                  {correlations.hrv_rhr_correlation !== null
                    ? correlations.hrv_rhr_correlation.toFixed(2)
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
                    correlations.sleep_hrv_lag_correlation !== null &&
                      correlations.sleep_hrv_lag_correlation > 0.3
                      ? "text-green-500"
                      : "text-muted-foreground",
                  )}
                >
                  {correlations.sleep_hrv_lag_correlation !== null
                    ? correlations.sleep_hrv_lag_correlation.toFixed(2)
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
                    correlations.strain_recovery_correlation !== null &&
                      correlations.strain_recovery_correlation < -0.2
                      ? "text-green-500"
                      : "text-muted-foreground",
                  )}
                >
                  {correlations.strain_recovery_correlation !== null
                    ? correlations.strain_recovery_correlation.toFixed(2)
                    : "—"}
                </span>
              </div>
              <p className="text-xs text-muted-foreground pt-1 border-t">
                Sample size: {correlations.sample_size} days
              </p>
            </div>
          </CardContent>
        </Card>

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
                  value: velocity.hrv_velocity,
                  unit: "ms/d",
                  status: velocity.interpretation.hrv,
                },
                {
                  label: "RHR",
                  value: velocity.rhr_velocity,
                  unit: "bpm/d",
                  status: velocity.interpretation.rhr,
                },
                {
                  label: "Weight",
                  value: velocity.weight_velocity,
                  unit: "kg/d",
                  status: velocity.interpretation.weight,
                },
                {
                  label: "Sleep",
                  value: velocity.sleep_velocity,
                  unit: "min/d",
                  status: velocity.interpretation.sleep,
                },
              ].map(({ label, value, unit, status }) => (
                <div key={label} className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">{label}</span>
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
      </div>

      {anomalies.anomaly_count > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Radar className="h-4 w-4 text-amber-500" />
                <CardTitle className="text-base">
                  Anomalies Detected ({anomalies.anomaly_count})
                </CardTitle>
              </div>
              {anomalies.has_recent_anomaly && (
                <span className="text-xs px-2 py-1 rounded-full bg-amber-500/10 text-amber-600">
                  Recent
                </span>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-4">
              {anomalies.anomalies.slice(0, 8).map((anomaly, i) => (
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
                    z={anomaly.z_score.toFixed(1)} on{" "}
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
              <p className="text-xs text-muted-foreground">Avg Recovery Days</p>
              <p className="text-lg font-semibold">
                {recoveryCapacity.avg_recovery_days !== null
                  ? `${recoveryCapacity.avg_recovery_days.toFixed(1)} days`
                  : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">
                Recovery Efficiency
              </p>
              <p className="text-lg font-semibold">
                {recoveryCapacity.recovery_efficiency !== null
                  ? recoveryCapacity.recovery_efficiency.toFixed(2)
                  : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">
                High Strain Events
              </p>
              <p className="text-lg font-semibold">
                {recoveryCapacity.high_strain_events}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Recovered Events</p>
              <p className="text-lg font-semibold">
                {recoveryCapacity.recovered_events}
              </p>
            </div>
          </div>
          {recoveryCapacity.high_strain_events > 0 && (
            <p className="text-xs text-muted-foreground mt-2">
              Recovery rate:{" "}
              {Math.round(
                (recoveryCapacity.recovered_events /
                  recoveryCapacity.high_strain_events) *
                  100,
              )}
              %
            </p>
          )}
        </CardContent>
      </Card>

      <Card
        className={cn(
          illnessRisk.risk_level === "high" && "border-red-500/50",
          illnessRisk.risk_level === "moderate" && "border-yellow-500/50",
        )}
      >
        <CardHeader className="pb-2">
          <div className="flex items-center gap-2">
            <Thermometer
              className={cn(
                "h-4 w-4",
                illnessRisk.risk_level === "high" && "text-red-500",
                illnessRisk.risk_level === "moderate" && "text-yellow-500",
                illnessRisk.risk_level === "low" && "text-green-500",
                illnessRisk.risk_level === null && "text-muted-foreground",
              )}
            />
            <CardTitle className="text-base">Pre-Illness Risk</CardTitle>
            {illnessRisk.risk_level && (
              <span
                className={cn(
                  "text-xs px-1.5 py-0.5 rounded ml-auto",
                  illnessRisk.risk_level === "high" &&
                    "bg-red-500/20 text-red-600",
                  illnessRisk.risk_level === "moderate" &&
                    "bg-yellow-500/20 text-yellow-600",
                  illnessRisk.risk_level === "low" &&
                    "bg-green-500/20 text-green-600",
                )}
              >
                {illnessRisk.risk_level}
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
                {illnessRisk.combined_deviation !== null
                  ? illnessRisk.combined_deviation.toFixed(2)
                  : "—"}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">
                Consecutive Days
              </span>
              <span className="font-mono text-sm">
                {illnessRisk.consecutive_days_elevated}
              </span>
            </div>
            <div className="text-xs text-muted-foreground pt-2 border-t">
              <span className="block">
                HRV Drop: {illnessRisk.components.hrv_drop?.toFixed(2) ?? "—"}σ
              </span>
              <span className="block">
                RHR Rise: {illnessRisk.components.rhr_rise?.toFixed(2) ?? "—"}σ
              </span>
              <span className="block">
                Sleep Drop:{" "}
                {illnessRisk.components.sleep_drop?.toFixed(2) ?? "—"}σ
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {decorrelation.current_correlation !== null && (
        <Card
          className={
            decorrelation.is_decorrelated ? "border-orange-500/50" : ""
          }
        >
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <Unlink
                className={cn(
                  "h-4 w-4",
                  decorrelation.is_decorrelated
                    ? "text-orange-500"
                    : "text-muted-foreground",
                )}
              />
              <CardTitle className="text-base">HRV-RHR Correlation</CardTitle>
              {decorrelation.is_decorrelated && (
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
                  r = {decorrelation.current_correlation.toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">
                  Baseline ({baselineDays}d)
                </span>
                <span className="font-mono text-sm">
                  r = {decorrelation.baseline_correlation?.toFixed(2) ?? "—"}
                </span>
              </div>
              {decorrelation.correlation_delta !== null && (
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">Delta</span>
                  <span
                    className={cn(
                      "font-mono text-sm",
                      decorrelation.correlation_delta > 0.1 &&
                        "text-orange-500",
                    )}
                  >
                    {decorrelation.correlation_delta > 0 ? "+" : ""}
                    {decorrelation.correlation_delta.toFixed(2)}
                  </span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {advancedInsights && (
        <>
          <div>
            <h2 className="text-xl font-semibold mb-4">Advanced Insights</h2>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
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
                          VO2 Max
                        </span>
                        <span className="font-mono text-sm">
                          {advancedInsights.fitness.vo2_max_current.toFixed(1)}
                        </span>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <Activity className="h-4 w-4 text-cyan-500" />
                    <CardTitle className="text-base">Allostatic Load</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">
                        Composite Score
                      </span>
                      <span
                        className={cn(
                          "font-mono text-sm font-semibold",
                          getAllostaticScoreColor(
                            advancedInsights.allostatic_load.composite_score,
                          ),
                        )}
                      >
                        {advancedInsights.allostatic_load.composite_score?.toFixed(
                          1,
                        ) ?? "—"}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground pt-2 border-t space-y-1">
                      {Object.entries(
                        advancedInsights.allostatic_load.breach_rates,
                      ).map(([metric, rate]) => (
                        <div key={metric} className="flex justify-between">
                          <span>{metric}</span>
                          <span
                            className={cn(
                              "font-mono",
                              rate > 0.3 && "text-red-500",
                              rate > 0.15 && rate <= 0.3 && "text-yellow-500",
                            )}
                          >
                            {(rate * 100).toFixed(0)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {advancedInsights.cross_domain.hrv_residual.r_squared !==
                null && (
                <Card>
                  <CardHeader className="pb-2">
                    <div className="flex items-center gap-2">
                      <Brain className="h-4 w-4 text-violet-500" />
                      <CardTitle className="text-base">HRV Residual</CardTitle>
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
                          ) ?? "—"}{" "}
                          ms
                        </span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-muted-foreground">
                          Actual
                        </span>
                        <span className="font-mono text-sm">
                          {advancedInsights.cross_domain.hrv_residual.actual?.toFixed(
                            1,
                          ) ?? "—"}{" "}
                          ms
                        </span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-muted-foreground">
                          Residual z
                        </span>
                        <span
                          className={cn(
                            "font-mono text-sm",
                            getZScoreColor(
                              advancedInsights.cross_domain.hrv_residual
                                .residual_z,
                            ),
                          )}
                        >
                          {advancedInsights.cross_domain.hrv_residual.residual_z?.toFixed(
                            2,
                          ) ?? "—"}
                          σ
                        </span>
                      </div>
                      <div className="text-xs text-muted-foreground pt-2 border-t">
                        R² ={" "}
                        {advancedInsights.cross_domain.hrv_residual.r_squared.toFixed(
                          3,
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {advancedInsights.cross_domain.weight_hrv_coupling !== null && (
                <Card>
                  <CardHeader className="pb-2">
                    <div className="flex items-center gap-2">
                      <Scale className="h-4 w-4 text-emerald-500" />
                      <CardTitle className="text-base">Cross-Domain</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-muted-foreground">
                          Weight↔HRV
                        </span>
                        <span
                          className={cn(
                            "font-mono text-sm",
                            getCrossCorrelationColor(
                              advancedInsights.cross_domain.weight_hrv_coupling,
                            ),
                          )}
                        >
                          r={" "}
                          {advancedInsights.cross_domain.weight_hrv_coupling.toFixed(
                            2,
                          )}
                        </span>
                      </div>
                      <div className="text-xs text-muted-foreground pt-2 border-t space-y-1">
                        {Object.entries(
                          advancedInsights.cross_domain.weekday_weekend,
                        ).map(([metric, split]) => (
                          <div key={metric} className="flex justify-between">
                            <span>{metric}</span>
                            <span className="font-mono">
                              {split.weekday_mean?.toFixed(0) ?? "—"} /{" "}
                              {split.weekend_mean?.toFixed(0) ?? "—"}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
