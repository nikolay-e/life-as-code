import { useState, useMemo, useCallback } from "react";
import { toast } from "sonner";
import { useHealthData } from "../../hooks/useHealthData";
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
  type DataQuality,
  type BaselineMetrics,
} from "../../lib/health-metrics";
import { PROVIDER_CONFIGS } from "../../lib/providers";
import {
  METRIC_REGISTRY,
  formatSleepMinutes,
  TREND_MODES,
  MODE_ORDER,
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
  Copy,
  Check,
  type LucideIcon,
} from "lucide-react";
import { cn } from "../../lib/utils";

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

  const trendIcon =
    baseline.trendSlope === null ? (
      <Minus className="h-4 w-4 text-muted-foreground" />
    ) : baseline.trendSlope > 0 ? (
      <TrendingUp className="h-4 w-4 text-green-500" />
    ) : (
      <TrendingDown className="h-4 w-4 text-red-500" />
    );

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

function formatTrendsForLLM(
  modeConfig: {
    label: string;
    shortTerm: number;
    baseline: number;
    trendWindow: number;
    description: string;
  },
  healthAnalysis: {
    healthScore: {
      overall: number | null;
      recoveryCore: number | null;
      behaviorSupport: number | null;
      contributors: Array<{
        name: string;
        rawZScore: number | null;
        goodnessZScore: number | null;
        confidence: number;
        isGated: boolean;
      }>;
    };
    recoveryMetrics: {
      hrvRhrImbalance: number | null;
      recoveryCV: number;
      stressLoadShort: number | null;
      stressLoadLong: number | null;
      stressTrend: number | null;
    };
    sleepMetrics: {
      sleepDebtShort: number;
      sleepSurplusShort: number;
      sleepCV: number;
      targetSleep: number;
      avgSleepShort: number | null;
      avgSleepLong: number | null;
    };
    activityMetrics: {
      acuteLoad: number | null;
      chronicLoad: number | null;
      acwr: number | null;
      stepsAvgShort: number | null;
      stepsAvgLong: number | null;
      stepsChange: number | null;
      stepsCV: number;
    };
    weightMetrics: {
      emaShort: number | null;
      emaLong: number | null;
      periodChange: number | null;
      volatilityShort: number;
      volatilityLong: number;
    };
  },
  computedMetrics: Record<
    string,
    {
      baseline: {
        currentValue: number | null;
        zScore: number | null;
        shiftedZScore: number | null;
        shortTermMean: number | null;
        longTermMean: number | null;
        trendSlope: number | null;
        cv: number;
      };
      quality: { confidence: number };
    }
  >,
  useShiftedZScore: boolean,
): string {
  const {
    healthScore,
    recoveryMetrics,
    sleepMetrics,
    activityMetrics,
    weightMetrics,
  } = healthAnalysis;

  const formatNum = (v: number | null, decimals = 2): string =>
    v !== null ? v.toFixed(decimals) : "N/A";

  const formatMinutes = (mins: number): string => {
    const h = Math.floor(mins / 60);
    const m = Math.round(mins % 60);
    return h > 0 ? `${String(h)}h ${String(m)}m` : `${String(m)}m`;
  };

  const lines: string[] = [
    `# Health Trends Report`,
    `Generated: ${new Date().toISOString().split("T")[0]}`,
    `Mode: ${modeConfig.label} (${modeConfig.description})`,
    `Analysis Window: ${String(modeConfig.shortTerm)} days current vs ${String(modeConfig.baseline)} days baseline`,
    `Trend Window: ${String(modeConfig.trendWindow)} days`,
    ``,
    `## Overall Health Score`,
    `- Overall Score: ${formatNum(healthScore.overall)}`,
    `- Recovery Core (70%): ${formatNum(healthScore.recoveryCore)}`,
    `- Behavior Support (30%): ${formatNum(healthScore.behaviorSupport)}`,
    ``,
    `### Score Contributors`,
  ];

  for (const c of healthScore.contributors) {
    const status = c.isGated ? " [EXCLUDED - low confidence]" : "";
    lines.push(
      `- ${c.name}: z=${formatNum(c.goodnessZScore)} (raw=${formatNum(c.rawZScore)}, conf=${(c.confidence * 100).toFixed(0)}%)${status}`,
    );
  }

  lines.push(
    ``,
    `## Recovery Analysis`,
    `- HRV-RHR Imbalance: ${formatNum(recoveryMetrics.hrvRhrImbalance)} (negative=recovered, positive=strained)`,
    `- Recovery CV: ${(recoveryMetrics.recoveryCV * 100).toFixed(1)}%`,
    `- Stress Load (${String(modeConfig.shortTerm)}d): ${formatNum(recoveryMetrics.stressLoadShort, 0)}`,
    `- Stress Load (${String(modeConfig.baseline)}d): ${formatNum(recoveryMetrics.stressLoadLong, 0)}`,
    `- Stress Trend: ${formatNum(recoveryMetrics.stressTrend, 1)} (negative=improving)`,
    ``,
    `## Sleep Analysis`,
    `- Sleep Target: ${formatMinutes(sleepMetrics.targetSleep)}/night`,
    `- Sleep Debt (${String(modeConfig.shortTerm)}d): ${formatMinutes(sleepMetrics.sleepDebtShort)}`,
    `- Sleep Surplus (${String(modeConfig.shortTerm)}d): ${formatMinutes(sleepMetrics.sleepSurplusShort)}`,
    `- Sleep Consistency (CV): ${(sleepMetrics.sleepCV * 100).toFixed(1)}%`,
    `- Average Sleep (${String(modeConfig.shortTerm)}d): ${sleepMetrics.avgSleepShort !== null ? formatMinutes(sleepMetrics.avgSleepShort) : "N/A"}`,
    `- Average Sleep (${String(modeConfig.baseline)}d): ${sleepMetrics.avgSleepLong !== null ? formatMinutes(sleepMetrics.avgSleepLong) : "N/A"}`,
    ``,
    `## Activity Analysis`,
    `- Acute:Chronic Workload Ratio: ${formatNum(activityMetrics.acwr)} (0.8-1.3 optimal, >1.5 injury risk)`,
    `- Acute Load: ${formatNum(activityMetrics.acuteLoad, 1)}`,
    `- Chronic Load: ${formatNum(activityMetrics.chronicLoad, 1)}`,
    `- Steps (${String(modeConfig.shortTerm)}d avg): ${activityMetrics.stepsAvgShort !== null ? Math.round(activityMetrics.stepsAvgShort).toLocaleString() : "N/A"}`,
    `- Steps (${String(modeConfig.baseline)}d avg): ${activityMetrics.stepsAvgLong !== null ? Math.round(activityMetrics.stepsAvgLong).toLocaleString() : "N/A"}`,
    `- Steps Change: ${activityMetrics.stepsChange !== null ? (activityMetrics.stepsChange > 0 ? "+" : "") + Math.round(activityMetrics.stepsChange).toLocaleString() : "N/A"}`,
    `- Steps CV: ${(activityMetrics.stepsCV * 100).toFixed(1)}%`,
    ``,
    `## Weight Analysis`,
    `- Weight EMA (${String(modeConfig.shortTerm)}d): ${weightMetrics.emaShort !== null ? `${weightMetrics.emaShort.toFixed(1)} kg` : "N/A"}`,
    `- Weight EMA (${String(modeConfig.baseline)}d): ${weightMetrics.emaLong !== null ? `${weightMetrics.emaLong.toFixed(1)} kg` : "N/A"}`,
    `- Period Change: ${weightMetrics.periodChange !== null ? `${(weightMetrics.periodChange > 0 ? "+" : "") + weightMetrics.periodChange.toFixed(2)} kg` : "N/A"}`,
    `- Short-term Volatility: ±${weightMetrics.volatilityShort.toFixed(2)} kg`,
    `- Long-term Volatility: ±${weightMetrics.volatilityLong.toFixed(2)} kg`,
    ``,
    `## Individual Metrics`,
  );

  const zScoreType = useShiftedZScore ? "period z-score" : "raw z-score";
  lines.push(`Note: Using ${zScoreType} for this mode.`, ``);

  for (const [key, metric] of Object.entries(computedMetrics)) {
    const { baseline, quality } = metric;
    const zScore = useShiftedZScore ? baseline.shiftedZScore : baseline.zScore;
    lines.push(
      `### ${key.toUpperCase()}`,
      `- Current: ${formatNum(baseline.currentValue)}`,
      `- Z-Score: ${formatNum(zScore)}`,
      `- ${String(modeConfig.shortTerm)}d Average: ${formatNum(baseline.shortTermMean)}`,
      `- ${String(modeConfig.baseline)}d Baseline: ${formatNum(baseline.longTermMean)}`,
      `- Trend Slope: ${baseline.trendSlope !== null ? `${(baseline.trendSlope > 0 ? "+" : "") + baseline.trendSlope.toFixed(3)}/day` : "N/A"}`,
      `- CV: ${(baseline.cv * 100).toFixed(1)}%`,
      `- Confidence: ${(quality.confidence * 100).toFixed(0)}%`,
      ``,
    );
  }

  lines.push(
    `---`,
    `Z-Score Interpretation: <-2 very low, -1 to -2 low, -1 to +1 normal, +1 to +2 high, >+2 very high`,
    `ACWR Interpretation: <0.8 detraining, 0.8-1.3 optimal, 1.3-1.5 caution, >1.5 injury risk`,
  );

  return lines.join("\n");
}

export function TrendsPage() {
  const [mode, setMode] = useState<TrendMode>("short");
  const [copied, setCopied] = useState(false);
  const modeConfig = TREND_MODES[mode];
  const {
    baseline: baselineDays,
    shortTerm: shortTermDays,
    trendWindow,
    useShiftedZScore,
  } = modeConfig;
  const { data, isLoading, error } = useHealthData(baselineDays, true);

  const baselineOptions = useMemo(
    () => getBaselineOptions(mode, modeConfig),
    [mode, modeConfig],
  );

  const handleCopyToClipboard = useCallback(async () => {
    const metrics = computeAllMetrics(
      data,
      baselineDays,
      shortTermDays,
      trendWindow,
      baselineOptions,
    );

    const analysis = computeHealthAnalysis(
      data,
      metrics,
      modeConfig,
      baselineOptions,
    );

    const text = formatTrendsForLLM(
      modeConfig,
      analysis,
      metrics,
      useShiftedZScore,
    );

    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success(`${modeConfig.label} trends copied to clipboard`);
      setTimeout(() => {
        setCopied(false);
      }, 2000);
    } catch {
      toast.error("Failed to copy to clipboard");
    }
  }, [
    data,
    baselineDays,
    shortTermDays,
    trendWindow,
    baselineOptions,
    modeConfig,
    useShiftedZScore,
  ]);

  if (error) {
    return (
      <ErrorCard message={`Failed to load health data: ${error.message}`} />
    );
  }

  if (isLoading || !data) {
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
                  <span className="text-[10px] opacity-70">
                    {cfg.description}
                  </span>
                </Button>
              );
            })}
            <Button
              variant="ghost"
              size="icon"
              disabled
              className="h-9 w-9 ml-1"
              aria-label="Copy trends data for LLM analysis"
            >
              <Copy className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <LoadingState message="Analyzing health data..." />
      </div>
    );
  }

  const computedMetrics = computeAllMetrics(
    data,
    baselineDays,
    shortTermDays,
    trendWindow,
    baselineOptions,
  );

  const healthAnalysis = computeHealthAnalysis(
    data,
    computedMetrics,
    modeConfig,
    baselineOptions,
  );

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
                <span className="text-[10px] opacity-70">
                  {cfg.description}
                </span>
              </Button>
            );
          })}
          <Button
            variant="ghost"
            size="icon"
            onClick={handleCopyToClipboard}
            className="h-9 w-9 ml-1"
            aria-label="Copy trends data for LLM analysis"
          >
            {copied ? (
              <Check className="h-4 w-4 text-green-500" />
            ) : (
              <Copy className="h-4 w-4" />
            )}
          </Button>
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
                Composite score based on recovery core (70%) + behavior support
                (30%)
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 md:grid-cols-3">
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
                Steps + Load Balance
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
                      c.confidence >= 0.8
                        ? "text-green-500"
                        : c.confidence >= 0.6
                          ? "text-yellow-500"
                          : "text-red-500",
                    )}
                  >
                    conf: {(c.confidence * 100).toFixed(0)}%
                  </p>
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
                recoveryMetrics.hrvRhrImbalance !== null
                  ? recoveryMetrics.hrvRhrImbalance > 1
                    ? "text-red-500"
                    : recoveryMetrics.hrvRhrImbalance < -1
                      ? "text-green-500"
                      : "text-blue-500"
                  : "text-muted-foreground",
              )}
            >
              {recoveryMetrics.hrvRhrImbalance !== null
                ? recoveryMetrics.hrvRhrImbalance.toFixed(2)
                : "—"}
            </p>
            <p className="text-xs text-muted-foreground">
              {recoveryMetrics.hrvRhrImbalance !== null
                ? recoveryMetrics.hrvRhrImbalance > 1
                  ? "Body under strain"
                  : recoveryMetrics.hrvRhrImbalance < -1
                    ? "Well recovered"
                    : "Balanced"
                : "Insufficient data"}
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
                sleepMetrics.sleepDebtShort > 120
                  ? "text-red-500"
                  : sleepMetrics.sleepDebtShort > 60
                    ? "text-yellow-500"
                    : "text-green-500",
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
                activityMetrics.acwr !== null
                  ? activityMetrics.acwr > 1.5
                    ? "text-red-500"
                    : activityMetrics.acwr < 0.8
                      ? "text-yellow-500"
                      : "text-green-500"
                  : "text-muted-foreground",
              )}
            >
              {activityMetrics.acwr !== null
                ? activityMetrics.acwr.toFixed(2)
                : "—"}
            </p>
            <p className="text-xs text-muted-foreground">
              {activityMetrics.acwr !== null
                ? activityMetrics.acwr > 1.5
                  ? "Injury risk - reduce load"
                  : activityMetrics.acwr < 0.8
                    ? "Detraining risk"
                    : "Sweet spot"
                : "Insufficient strain data"}
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
                activityMetrics.stepsChange !== null
                  ? activityMetrics.stepsChange < -1000
                    ? "text-red-500"
                    : activityMetrics.stepsChange > 1000
                      ? "text-green-500"
                      : "text-blue-500"
                  : "text-muted-foreground",
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
                    weightMetrics.periodChange !== null
                      ? weightMetrics.periodChange > 0.5
                        ? "text-red-500"
                        : weightMetrics.periodChange < -0.5
                          ? "text-green-500"
                          : "text-blue-500"
                      : "",
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
                    recoveryMetrics.stressTrend !== null
                      ? recoveryMetrics.stressTrend > 5
                        ? "text-red-500"
                        : recoveryMetrics.stressTrend < -5
                          ? "text-green-500"
                          : "text-blue-500"
                      : "",
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
    </div>
  );
}
