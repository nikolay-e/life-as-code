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
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  CheckCircle,
  Clock,
} from "lucide-react";
import { cn } from "../../../lib/utils";
import { ZCard } from "../../../components/luxury/ZCard";
import { SectionHead, SerifEm } from "../../../components/luxury/SectionHead";
import { getConfidenceColor, signPrefix, formatDaysLabel } from "./stat-utils";
import { splitValueUnit } from "../../../lib/formatters";

function getQualityBadgeAppearance(confidence: number): {
  color: string;
  Icon: typeof CheckCircle;
} {
  if (confidence < 0.6) {
    return { color: "text-rust", Icon: AlertTriangle };
  }
  if (confidence < 0.8) {
    return { color: "text-brass", Icon: Clock };
  }
  return { color: "text-moss", Icon: CheckCircle };
}

function ScorePillar({
  label,
  value,
  detail,
  large = false,
}: Readonly<{
  label: string;
  value: number | null;
  detail: string;
  large?: boolean;
}>) {
  return (
    <div className="flex flex-col gap-2 px-6 py-7">
      <span className="type-mono-eyebrow text-muted-foreground">{label}</span>
      <span
        className={cn(
          "font-serif leading-none tracking-[-0.04em]",
          large
            ? "text-[clamp(56px,7vw,96px)]"
            : "text-[clamp(40px,4.5vw,60px)]",
          getHealthScoreColor(value),
        )}
        style={{
          fontVariationSettings: '"opsz" 144, "SOFT" 50',
          fontWeight: 320,
          fontFeatureSettings: '"lnum","tnum"',
        }}
      >
        {value == null ? "—" : value.toFixed(2)}
      </span>
      <span
        className={cn(
          "type-mono-label",
          large ? getHealthScoreColor(value) : "text-muted-foreground",
        )}
      >
        {large ? getHealthScoreLabel(value) : detail}
      </span>
    </div>
  );
}

interface MetricCardProps {
  readonly title: string;
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
  const zScoreLabel = useShiftedZScore ? "period z" : "z";

  const trendIcon = (() => {
    if (baseline.trend_slope === null) {
      return <Minus className="h-3.5 w-3.5 text-muted-foreground" />;
    }
    if (baseline.trend_slope > 0) {
      return <TrendingUp className="h-3.5 w-3.5 text-moss" />;
    }
    return <TrendingDown className="h-3.5 w-3.5 text-rust" />;
  })();

  const formatted = formatValue(baseline.current_value);
  const { value: numStr, unit: unitStr } = splitValueUnit(formatted);

  const coveragePercent = Math.round(baseline.quality_coverage * 100);
  const confidencePercent = Math.round(baseline.quality_confidence * 100);
  const { color: confColor } = getQualityBadgeAppearance(
    baseline.quality_confidence,
  );

  if (baseline.valid_points === 0) {
    return (
      <ZCard
        name={title}
        period="vs baseline"
        value="—"
        zScore={null}
        zLabel={zScoreLabel}
        footer={<>No data available</>}
      />
    );
  }

  return (
    <ZCard
      name={title}
      period={`${formatDaysLabel(baselineDays)} median`}
      value={numStr}
      unit={unitStr}
      zScore={displayZScore}
      zLabel={zScoreLabel}
      footer={
        <div className="flex flex-col gap-2">
          <div className="grid grid-cols-3 gap-3 text-foreground">
            <div className="flex flex-col gap-0.5">
              <span className="type-mono-label text-muted-foreground">
                {formatDaysLabel(shortTermDays)} avg
              </span>
              <span className="font-mono text-[12px] tracking-tight">
                {formatValue(baseline.short_term_mean)}
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="type-mono-label text-muted-foreground">
                {formatDaysLabel(baselineDays)} avg
              </span>
              <span className="font-mono text-[12px] tracking-tight">
                {formatValue(baseline.mean)}
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="type-mono-label text-muted-foreground">
                trend · {formatDaysLabel(trendWindow)}
              </span>
              <span className="flex items-center gap-1 font-mono text-[12px] tracking-tight">
                {trendIcon}
                {baseline.trend_slope == null
                  ? "—"
                  : `${signPrefix(baseline.trend_slope)}${baseline.trend_slope.toFixed(2)}/d`}
              </span>
            </div>
          </div>
          <div className="flex justify-between gap-2 pt-2 border-t border-border type-mono-label text-muted-foreground normal-case tracking-wide">
            <span className={confColor}>{confidencePercent}% conf</span>
            <span>{coveragePercent}% cov</span>
            <span>cv {(baseline.cv * 100).toFixed(1)}%</span>
            <span>{baseline.valid_points} pts</span>
          </div>
        </div>
      }
    />
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
  const hasTrainingLoad = healthScore.training_load != null;

  return (
    <div className="flex flex-col gap-12">
      <article className="border border-border bg-background">
        <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-3 px-6 pt-6 pb-4 border-b border-border">
          <div className="flex flex-col gap-1.5">
            <span className="type-mono-eyebrow text-muted-foreground">
              composite score
            </span>
            <h3
              className="font-serif text-[clamp(22px,2.4vw,28px)] leading-none tracking-[-0.02em]"
              style={{
                fontVariationSettings: '"opsz" 144, "SOFT" 80',
                fontWeight: 350,
              }}
            >
              Health <SerifEm>status</SerifEm>
            </h3>
          </div>
          <p className="type-mono-label text-muted-foreground normal-case tracking-wide max-w-md md:text-right">
            {hasTrainingLoad
              ? "recovery core 60% · training load 20% · behavior 20%"
              : "recovery core 75% · behavior support 25%"}
          </p>
        </header>

        <div
          className={cn(
            "grid divide-y md:divide-y-0 md:divide-x divide-border",
            hasTrainingLoad ? "md:grid-cols-4" : "md:grid-cols-3",
          )}
        >
          <ScorePillar
            label="overall"
            value={healthScore.overall}
            detail=""
            large
          />
          <ScorePillar
            label="recovery core"
            value={healthScore.recovery_core}
            detail="HRV · RHR · Sleep · Stress"
          />
          {hasTrainingLoad && (
            <ScorePillar
              label="training load"
              value={healthScore.training_load}
              detail="Strain optimality"
            />
          )}
          <ScorePillar
            label="behavior support"
            value={healthScore.behavior_support}
            detail="Steps · Calories · Weight"
          />
        </div>

        <div className="px-6 py-6 border-t border-border">
          <div className="flex items-end justify-between gap-3 mb-4">
            <span className="type-mono-eyebrow text-muted-foreground">
              contributors
            </span>
            <span className="type-mono-label text-muted-foreground normal-case tracking-wide">
              day {Math.round(dayCompleteness * 100)}% complete
              {!stepsUsesToday && (
                <span className="text-brass ml-2">· steps using yesterday</span>
              )}
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-px bg-border border border-border">
            {healthScore.contributors.map((c) => (
              <div
                key={c.name}
                className={cn(
                  "flex flex-col gap-1 px-3 py-3 bg-background",
                  c.is_gated && "opacity-60",
                )}
              >
                <span className="type-mono-label text-muted-foreground">
                  {c.name}
                </span>
                <span
                  className={cn(
                    "font-mono text-[14px] tracking-tight",
                    c.is_gated
                      ? "text-muted-foreground line-through"
                      : getZScoreColor(c.goodness_z_score),
                  )}
                >
                  {formatZScore(c.goodness_z_score)}
                </span>
                <span className="type-mono-label text-muted-foreground/70 normal-case tracking-wide">
                  raw {formatZScore(c.raw_z_score)} ·{" "}
                  <span className={getConfidenceColor(c.confidence)}>
                    {(c.confidence * 100).toFixed(0)}%
                  </span>
                </span>
                {c.long_term_percentile != null && (
                  <span className="type-mono-label text-muted-foreground/60 normal-case tracking-wide">
                    P{c.long_term_percentile.toFixed(0)} all-time
                  </span>
                )}
                {c.is_gated && (
                  <span className="type-mono-label text-rust normal-case tracking-wide">
                    {c.gate_reason}
                  </span>
                )}
                {!c.is_gated && c.gate_reason && (
                  <span className="type-mono-label text-muted-foreground/60 normal-case tracking-wide">
                    {c.gate_reason}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>

        {dataSourceSummary.length > 0 && (
          <div className="px-6 py-6 border-t border-border">
            <div className="flex items-end justify-between mb-4">
              <span className="type-mono-eyebrow text-muted-foreground">
                smart data fusion
              </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-px bg-border border border-border">
              {dataSourceSummary.map((s) => (
                <div
                  key={s.metric}
                  className="flex flex-col gap-1 px-3 py-3 bg-background"
                >
                  <span className="type-mono-label text-foreground/80">
                    {s.metric}
                  </span>
                  <span className="font-mono text-[12px] tracking-tight text-muted-foreground">
                    <span className={PROVIDER_CONFIGS.garmin.colorClass}>
                      {s.garmin_only}
                      {PROVIDER_CONFIGS.garmin.shortName}
                    </span>{" "}
                    /{" "}
                    <span className={PROVIDER_CONFIGS.whoop.colorClass}>
                      {s.whoop_only}
                      {PROVIDER_CONFIGS.whoop.shortName}
                    </span>{" "}
                    /{" "}
                    <span className={PROVIDER_CONFIGS.eight_sleep.colorClass}>
                      {s.eight_sleep_only}
                      {PROVIDER_CONFIGS.eight_sleep.shortName}
                    </span>
                    {s.blended > 0 && (
                      <span
                        className={`${PROVIDER_CONFIGS.blended.colorClass} ml-1`}
                      >
                        ({s.blended})
                      </span>
                    )}
                  </span>
                  <span className="type-mono-label text-muted-foreground/70 normal-case tracking-wide">
                    conf {(s.avg_confidence * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </article>

      <div>
        <SectionHead
          title={
            <>
              Individual <SerifEm>metrics</SerifEm>
            </>
          }
          meta={<>per-metric baseline deviation</>}
        />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 border-t border-border lg:[&>*]:border-l lg:[&>*]:border-border lg:[&>*:nth-child(3n+1)]:border-l-0 md:[&>*:nth-child(2n)]:border-l md:[&>*:nth-child(2n)]:border-border">
          {METRIC_REGISTRY.filter((def) => def.key in metricBaselines).map(
            (def) => {
              const baseline = metricBaselines[def.key];
              return (
                <MetricCard
                  key={def.key}
                  title={def.title}
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
    </div>
  );
}
