import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../../../components/ui/card";
import {
  formatZScore,
  getZScoreColor,
  getHealthScoreLabel,
  getHealthScoreColor,
} from "../../../lib/health/format";
import { PROVIDER_CONFIGS } from "../../../lib/providers";
import { METRIC_REGISTRY } from "../../../lib/metrics";
import type {
  MetricBaseline,
  HealthScore,
  DataSourceSummary,
} from "../../../types/api";
import {
  type LucideIcon,
  Gauge,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  CheckCircle,
  Clock,
} from "lucide-react";
import { cn } from "../../../lib/utils";
import { getConfidenceColor, signPrefix, formatDaysLabel } from "./stat-utils";

function getQualityBadgeAppearance(confidence: number): {
  color: string;
  Icon: typeof CheckCircle;
} {
  if (confidence < 0.6) {
    return { color: "text-red-600 dark:text-red-400", Icon: AlertTriangle };
  }
  if (confidence < 0.8) {
    return { color: "text-yellow-600 dark:text-yellow-400", Icon: Clock };
  }
  return { color: "text-green-600 dark:text-green-400", Icon: CheckCircle };
}

function DataQualityBadge({ baseline }: { baseline: MetricBaseline }) {
  const coveragePercent = Math.round(baseline.quality_coverage * 100);
  const confidencePercent = Math.round(baseline.quality_confidence * 100);
  const { color, Icon } = getQualityBadgeAppearance(
    baseline.quality_confidence,
  );

  return (
    <div className="flex items-center gap-1.5 text-xs">
      <Icon className={cn("h-3 w-3", color)} />
      <span className={color}>{confidencePercent}% conf</span>
      <span className="text-muted-foreground">({coveragePercent}% cov)</span>
      {baseline.latency_days != null && baseline.latency_days > 1 && (
        <span className="text-muted-foreground">
          · {baseline.latency_days}d ago
        </span>
      )}
    </div>
  );
}

interface MetricCardProps {
  readonly title: string;
  readonly icon: LucideIcon;
  readonly iconColorClass: string;
  readonly iconBgClass: string;
  readonly baseline: MetricBaseline;
  readonly format: (value: number | null) => string;
  readonly invertZScore?: boolean;
  readonly shortTermDays: number;
  readonly baselineDays: number;
  readonly trendWindow: number;
  readonly useShiftedZScore: boolean;
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
    invertZScore && rawZScore != null ? -rawZScore : rawZScore;

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
                    {baseline.trend_slope != null
                      ? `${signPrefix(baseline.trend_slope)}${baseline.trend_slope.toFixed(2)}/d`
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

export interface HealthScoreSectionProps {
  readonly healthScore: HealthScore;
  readonly dayCompleteness: number;
  readonly dataSourceSummary: DataSourceSummary[];
  readonly metricBaselines: Record<string, MetricBaseline>;
  readonly shortTermDays: number;
  readonly baselineDays: number;
  readonly trendWindow: number;
  readonly useShiftedZScore: boolean;
}

export function HealthScoreSection({
  healthScore,
  dayCompleteness,
  dataSourceSummary,
  metricBaselines,
  shortTermDays,
  baselineDays,
  trendWindow,
  useShiftedZScore,
}: HealthScoreSectionProps) {
  const stepsUsesToday = Boolean(healthScore.steps_status.use_today);
  return (
    <>
      <Card className="border-2">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-primary/10">
              <Gauge className="h-6 w-6 text-primary" />
            </div>
            <div>
              <CardTitle>Health Status Score</CardTitle>
              <CardDescription>
                {healthScore.training_load != null
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
              healthScore.training_load != null
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
                {healthScore.overall != null
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
                {healthScore.recovery_core != null
                  ? healthScore.recovery_core.toFixed(2)
                  : "—"}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                HRV + RHR + Sleep + Stress
              </p>
            </div>
            {healthScore.training_load != null && (
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
                {healthScore.behavior_support != null
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
                {!stepsUsesToday && (
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
                  {c.long_term_percentile != null && (
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
    </>
  );
}
