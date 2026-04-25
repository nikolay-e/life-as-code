import { getZScoreColor } from "../../../lib/health/format";
import type {
  OverreachingMetrics,
  CorrelationMetrics,
  VelocityMetrics,
  AnomalyMetrics,
  RecoveryCapacityMetrics,
  IllnessRiskSignal,
  DecorrelationAlert,
  AdvancedInsights,
} from "../../../types/api";
import {
  Minus,
  ArrowUpRight,
  ArrowDownRight,
  type LucideIcon,
} from "lucide-react";
import { cn } from "../../../lib/utils";
import { SectionHead, SerifEm } from "../../../components/luxury/SectionHead";
import {
  getCorrelationColor,
  getHrvSdColor,
  getTsbColor,
  getAllostaticScoreColor,
  getCrossCorrelationColor,
  signPrefix,
  formatMetricLabel,
} from "./stat-utils";

interface PanelProps {
  readonly title: string;
  readonly description?: string;
  readonly badge?: { readonly label: string; readonly toneClass: string };
  readonly className?: string;
  readonly children: React.ReactNode;
}

function Panel({ title, description, badge, className, children }: PanelProps) {
  return (
    <article
      className={cn(
        "border border-border bg-background flex flex-col transition-colors duration-300 hover:bg-secondary/40",
        className,
      )}
    >
      <header className="px-5 py-4 border-b border-border flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h3
            className="font-serif text-[18px] leading-none tracking-[-0.01em]"
            style={{
              fontVariationSettings: '"opsz" 144, "SOFT" 100',
              fontStyle: "italic",
              fontWeight: 400,
            }}
          >
            {title}
          </h3>
          {description && (
            <span className="type-mono-label text-muted-foreground normal-case tracking-wide">
              {description}
            </span>
          )}
        </div>
        {badge && (
          <span
            className={cn(
              "type-mono-label px-2 py-0.5 border border-border",
              badge.toneClass,
            )}
          >
            {badge.label}
          </span>
        )}
      </header>
      <div className="px-5 py-5 flex-1">{children}</div>
    </article>
  );
}

interface RowProps {
  readonly label: React.ReactNode;
  readonly value: React.ReactNode;
  readonly toneClass?: string;
}

function Row({ label, value, toneClass }: RowProps) {
  return (
    <div className="flex justify-between items-center gap-3 py-1">
      <span className="type-mono-label text-muted-foreground normal-case tracking-wide">
        {label}
      </span>
      <span
        className={cn(
          "font-mono text-[13px] tracking-tight",
          toneClass ?? "text-foreground",
        )}
        style={{ fontFeatureSettings: '"lnum","tnum"' }}
      >
        {value}
      </span>
    </div>
  );
}

function HeroValue({
  value,
  toneClass,
}: Readonly<{ value: React.ReactNode; toneClass?: string }>) {
  return (
    <div
      className={cn(
        "font-serif text-[clamp(40px,5vw,60px)] leading-none tracking-[-0.04em] mb-4",
        toneClass ?? "text-foreground",
      )}
      style={{
        fontVariationSettings: '"opsz" 144, "SOFT" 50',
        fontWeight: 320,
        fontFeatureSettings: '"lnum","tnum"',
      }}
    >
      {value}
    </div>
  );
}

function getRiskTone(level: string | null | undefined): string {
  switch (level) {
    case "low":
      return "text-moss";
    case "moderate":
      return "text-brass";
    case "high":
      return "text-rust";
    case "critical":
      return "text-rust";
    default:
      return "text-muted-foreground";
  }
}

function OverreachingCard({
  overreaching,
}: Readonly<{ overreaching: OverreachingMetrics }>) {
  return (
    <Panel
      title="Overreaching"
      description="strain vs HRV signal"
      badge={
        overreaching.risk_level
          ? {
              label: overreaching.risk_level,
              toneClass: getRiskTone(overreaching.risk_level),
            }
          : undefined
      }
    >
      <HeroValue
        value={overreaching.score == null ? "—" : overreaching.score.toFixed(2)}
        toneClass={getRiskTone(overreaching.risk_level)}
      />
      <Row
        label="Low recovery streak"
        value={`${String(overreaching.consecutive_low_recovery_days)}d`}
      />
      {(overreaching.components.strain_component ?? null) !== null && (
        <Row
          label="Strain component"
          value={(overreaching.components.strain_component as number).toFixed(
            1,
          )}
          toneClass="text-brass"
        />
      )}
      {(overreaching.components.hrv_component ?? null) !== null && (
        <Row
          label="HRV component"
          value={(overreaching.components.hrv_component as number).toFixed(1)}
          toneClass="text-rust"
        />
      )}
    </Panel>
  );
}

function CorrelationsCard({
  correlations,
}: Readonly<{ correlations: CorrelationMetrics }>) {
  return (
    <Panel
      title="Correlations"
      description={`sample ${String(correlations.sample_size)}d`}
    >
      <Row
        label="HRV ↔ RHR"
        value={
          correlations.hrv_rhr_correlation == null
            ? "—"
            : correlations.hrv_rhr_correlation.toFixed(2)
        }
        toneClass={getCorrelationColor(correlations.hrv_rhr_correlation)}
      />
      <Row
        label="Sleep → HRV"
        value={
          correlations.sleep_hrv_lag_correlation == null
            ? "—"
            : correlations.sleep_hrv_lag_correlation.toFixed(2)
        }
        toneClass={
          correlations.sleep_hrv_lag_correlation != null &&
          correlations.sleep_hrv_lag_correlation > 0.3
            ? "text-moss"
            : "text-muted-foreground"
        }
      />
      <Row
        label="Strain → Recovery"
        value={
          correlations.strain_recovery_correlation == null
            ? "—"
            : correlations.strain_recovery_correlation.toFixed(2)
        }
        toneClass={
          correlations.strain_recovery_correlation != null &&
          correlations.strain_recovery_correlation < -0.2
            ? "text-moss"
            : "text-muted-foreground"
        }
      />
    </Panel>
  );
}

const VELOCITY_STATUS_ICONS: Record<string, LucideIcon> = {
  improving: ArrowUpRight,
  declining: ArrowDownRight,
  stable: Minus,
  gaining: ArrowUpRight,
  losing: ArrowDownRight,
};

const VELOCITY_STATUS_TONES: Record<string, string> = {
  improving: "text-moss",
  declining: "text-rust",
  stable: "text-muted-foreground",
  gaining: "text-brass",
  losing: "text-foreground",
};

function VelocityCard({ velocity }: Readonly<{ velocity: VelocityMetrics }>) {
  const items = [
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
  ];
  return (
    <Panel title="Velocity" description="rate of change">
      {items.map(({ label, value, unit, status }) => {
        const Icon = status ? VELOCITY_STATUS_ICONS[status] : undefined;
        const toneClass = status
          ? VELOCITY_STATUS_TONES[status]
          : "text-foreground";
        return (
          <Row
            key={label}
            label={label}
            value={
              <span className="flex items-center gap-2">
                {value == null
                  ? "—"
                  : `${signPrefix(value)}${value.toFixed(2)} ${unit}`}
                {Icon && <Icon className={cn("h-3 w-3", toneClass)} />}
              </span>
            }
          />
        );
      })}
    </Panel>
  );
}

function AnomaliesCard({ anomalies }: Readonly<{ anomalies: AnomalyMetrics }>) {
  if (anomalies.anomaly_count === 0) return null;
  return (
    <Panel
      title={`Anomalies (${String(anomalies.anomaly_count)})`}
      description="z-score deviations"
      badge={
        anomalies.has_recent_anomaly
          ? { label: "recent", toneClass: "text-brass" }
          : undefined
      }
      className="md:col-span-2 lg:col-span-3"
    >
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        {anomalies.anomalies.slice(0, 8).map((anomaly) => {
          const tone =
            anomaly.severity === "critical"
              ? "text-rust border-rust/30 bg-rust/5"
              : anomaly.severity === "alert"
                ? "text-brass border-brass/30 bg-brass/5"
                : "text-foreground border-border bg-secondary/30";
          return (
            <div
              key={`${anomaly.date}-${anomaly.metric}`}
              className={cn("p-3 border", tone)}
            >
              <div className="flex items-center justify-between mb-1">
                <span
                  className="font-serif text-[14px]"
                  style={{
                    fontVariationSettings: '"opsz" 144, "SOFT" 100',
                    fontStyle: "italic",
                    fontWeight: 400,
                  }}
                >
                  {anomaly.metric}
                </span>
                <span className="type-mono-label normal-case tracking-wide">
                  {anomaly.severity}
                </span>
              </div>
              <span className="type-mono-label text-muted-foreground normal-case tracking-wide">
                z={anomaly.z_score.toFixed(1)} ·{" "}
                {new Date(anomaly.date).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                })}
              </span>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function RecoveryCapacityCard({
  recoveryCapacity,
}: Readonly<{ recoveryCapacity: RecoveryCapacityMetrics }>) {
  const rate =
    recoveryCapacity.high_strain_events > 0
      ? Math.round(
          (recoveryCapacity.recovered_events /
            recoveryCapacity.high_strain_events) *
            100,
        )
      : null;
  return (
    <Panel title="Recovery capacity" description="HRV bounce after high strain">
      <div className="grid grid-cols-2 gap-x-6 gap-y-3">
        <Row
          label="Avg recovery"
          value={
            recoveryCapacity.avg_recovery_days == null
              ? "—"
              : `${recoveryCapacity.avg_recovery_days.toFixed(1)}d`
          }
        />
        <Row
          label="Efficiency"
          value={
            recoveryCapacity.recovery_efficiency == null
              ? "—"
              : recoveryCapacity.recovery_efficiency.toFixed(2)
          }
        />
        <Row
          label="High strain events"
          value={recoveryCapacity.high_strain_events}
        />
        <Row label="Recovered" value={recoveryCapacity.recovered_events} />
      </div>
      {rate != null && (
        <div className="pt-3 mt-3 border-t border-border">
          <Row label="Recovery rate" value={`${String(rate)}%`} />
        </div>
      )}
    </Panel>
  );
}

function IllnessRiskCard({
  illnessRisk,
}: Readonly<{ illnessRisk: IllnessRiskSignal }>) {
  return (
    <Panel
      title="Pre-illness risk"
      description="HRV drop · RHR rise · sleep deficit"
      badge={
        illnessRisk.risk_level
          ? {
              label: illnessRisk.risk_level,
              toneClass: getRiskTone(illnessRisk.risk_level),
            }
          : undefined
      }
    >
      <Row
        label="Combined deviation"
        value={
          illnessRisk.combined_deviation == null
            ? "—"
            : illnessRisk.combined_deviation.toFixed(2)
        }
      />
      <Row
        label="Consecutive days"
        value={illnessRisk.consecutive_days_elevated}
      />
      <div className="pt-3 mt-3 border-t border-border flex flex-col gap-1">
        <Row
          label="HRV drop"
          value={`${illnessRisk.components.hrv_drop?.toFixed(2) ?? "—"}σ`}
        />
        <Row
          label="RHR rise"
          value={`${illnessRisk.components.rhr_rise?.toFixed(2) ?? "—"}σ`}
        />
        <Row
          label="Sleep drop"
          value={`${illnessRisk.components.sleep_drop?.toFixed(2) ?? "—"}σ`}
        />
      </div>
    </Panel>
  );
}

function DecorrelationCard({
  decorrelation,
  baselineDays,
}: Readonly<{
  decorrelation: DecorrelationAlert;
  baselineDays: number;
}>) {
  if (decorrelation.current_correlation == null) return null;
  return (
    <Panel
      title="HRV–RHR correlation"
      description="negative is healthy"
      badge={
        decorrelation.is_decorrelated
          ? { label: "decorrelated", toneClass: "text-brass" }
          : undefined
      }
    >
      <Row
        label="Current (14d)"
        value={`r ${decorrelation.current_correlation.toFixed(2)}`}
      />
      <Row
        label={`Baseline (${String(baselineDays)}d)`}
        value={`r ${decorrelation.baseline_correlation?.toFixed(2) ?? "—"}`}
      />
      {decorrelation.correlation_delta != null && (
        <Row
          label="Delta"
          value={`${signPrefix(decorrelation.correlation_delta)}${decorrelation.correlation_delta.toFixed(2)}`}
          toneClass={
            decorrelation.correlation_delta > 0.1
              ? "text-brass"
              : "text-foreground"
          }
        />
      )}
    </Panel>
  );
}

function HrvAdvancedCard({
  insights,
}: Readonly<{ insights: AdvancedInsights }>) {
  const h = insights.hrv_advanced;
  return (
    <Panel title="HRV advanced" description="lnRMSSD detail">
      <Row label="lnRMSSD" value={h.ln_rmssd_current?.toFixed(2) ?? "—"} />
      <Row label="7d mean" value={h.ln_rmssd_mean_7d?.toFixed(2) ?? "—"} />
      <Row
        label="SD (7d)"
        value={h.ln_rmssd_sd_7d?.toFixed(3) ?? "—"}
        toneClass={getHrvSdColor(h.ln_rmssd_sd_7d)}
      />
      <div className="pt-3 mt-3 border-t border-border flex flex-col gap-1">
        <Row
          label="HRV–RHR r (14d)"
          value={h.hrv_rhr_rolling_r_14d?.toFixed(2) ?? "—"}
        />
        <Row
          label="HRV–RHR r (60d)"
          value={h.hrv_rhr_rolling_r_60d?.toFixed(2) ?? "—"}
        />
      </div>
    </Panel>
  );
}

function SleepQualityCard({
  insights,
}: Readonly<{ insights: AdvancedInsights }>) {
  const sq = insights.sleep_quality;
  return (
    <Panel title="Sleep quality" description="architecture & response">
      <Row label="Efficiency" value={`${sq.efficiency?.toFixed(1) ?? "—"}%`} />
      <Row
        label="Deep sleep"
        value={`${sq.deep_sleep_pct?.toFixed(1) ?? "—"}%`}
        toneClass={
          sq.deep_sleep_pct != null && sq.deep_sleep_pct >= 15
            ? "text-moss"
            : "text-brass"
        }
      />
      <Row
        label="REM sleep"
        value={`${sq.rem_sleep_pct?.toFixed(1) ?? "—"}%`}
        toneClass={
          sq.rem_sleep_pct != null && sq.rem_sleep_pct >= 20
            ? "text-moss"
            : "text-brass"
        }
      />
      <Row
        label="Consistency"
        value={`${sq.consistency_score?.toFixed(0) ?? "—"}/100`}
      />
      <div className="pt-3 mt-3 border-t border-border flex flex-col gap-1">
        <Row
          label="Sleep → HRV"
          value={
            <>
              r {sq.sleep_hrv_responsiveness?.toFixed(2) ?? "—"}
              {sq.sleep_hrv_p_value != null && sq.sleep_hrv_p_value < 0.05 && (
                <span className="text-moss ml-1">*</span>
              )}
            </>
          }
        />
        <Row
          label="Fragmentation"
          value={`${sq.fragmentation_index?.toFixed(1) ?? "—"}/hr`}
        />
      </div>
    </Panel>
  );
}

function FitnessCard({ insights }: Readonly<{ insights: AdvancedInsights }>) {
  const f = insights.fitness;
  return (
    <Panel
      title="Fitness & training"
      description="training load &amp; freshness"
    >
      <Row
        label="Last workout"
        value={
          f.days_since_last_workout == null
            ? "—"
            : `${String(f.days_since_last_workout)}d ago`
        }
        toneClass={
          f.days_since_last_workout != null && f.days_since_last_workout > 7
            ? "text-rust"
            : "text-moss"
        }
      />
      <Row
        label="Frequency"
        value={`${String(f.training_frequency_7d)}/w · ${String(f.training_frequency_30d)}/mo`}
      />
      <Row
        label="CTL / ATL / TSB"
        value={
          <>
            {f.ctl?.toFixed(1) ?? "—"} / {f.atl?.toFixed(1) ?? "—"} /{" "}
            <span className={cn(getTsbColor(f.tsb))}>
              {f.tsb?.toFixed(1) ?? "—"}
            </span>
          </>
        }
      />
      {f.vo2_max_current != null && (
        <Row label="VO₂ max" value={f.vo2_max_current.toFixed(1)} />
      )}
    </Panel>
  );
}

function AllostaticLoadCard({
  insights,
}: Readonly<{ insights: AdvancedInsights }>) {
  const al = insights.allostatic_load;
  return (
    <Panel title="Allostatic load" description="composite stress score">
      <HeroValue
        value={al.composite_score?.toFixed(1) ?? "—"}
        toneClass={getAllostaticScoreColor(al.composite_score)}
      />
      <div className="pt-3 border-t border-border flex flex-col gap-1">
        {Object.entries(al.breach_rates).map(([metric, rate]) => (
          <Row
            key={metric}
            label={formatMetricLabel(metric)}
            value={`${(rate * 100).toFixed(0)}%`}
            toneClass={
              rate > 0.3
                ? "text-rust"
                : rate > 0.15
                  ? "text-brass"
                  : "text-foreground"
            }
          />
        ))}
      </div>
    </Panel>
  );
}

function HrvResidualCard({
  insights,
}: Readonly<{ insights: AdvancedInsights }>) {
  const residual = insights.cross_domain.hrv_residual;
  if (residual.r_squared == null) return null;
  return (
    <Panel
      title="HRV residual"
      description={`R² = ${residual.r_squared.toFixed(3)}`}
    >
      <Row
        label="Predicted"
        value={`${residual.predicted?.toFixed(1) ?? "—"} ms`}
      />
      <Row label="Actual" value={`${residual.actual?.toFixed(1) ?? "—"} ms`} />
      <Row
        label="Residual z"
        value={`${residual.residual_z?.toFixed(2) ?? "—"}σ`}
        toneClass={getZScoreColor(residual.residual_z)}
      />
    </Panel>
  );
}

function CrossDomainCard({
  insights,
}: Readonly<{ insights: AdvancedInsights }>) {
  const cd = insights.cross_domain;
  if (cd.weight_hrv_coupling == null) return null;
  return (
    <Panel title="Cross-domain" description="weekday vs weekend means">
      <Row
        label="Weight ↔ HRV"
        value={`r ${cd.weight_hrv_coupling.toFixed(2)}`}
        toneClass={getCrossCorrelationColor(cd.weight_hrv_coupling)}
      />
      <div className="pt-3 mt-3 border-t border-border flex flex-col gap-1">
        {Object.entries(cd.weekday_weekend).map(([metric, split]) => (
          <Row
            key={metric}
            label={formatMetricLabel(metric)}
            value={`${split.weekday_mean?.toFixed(0) ?? "—"} / ${split.weekend_mean?.toFixed(0) ?? "—"}`}
          />
        ))}
      </div>
    </Panel>
  );
}

export interface AdvancedSectionProps {
  readonly overreaching: OverreachingMetrics;
  readonly correlations: CorrelationMetrics;
  readonly velocity: VelocityMetrics;
  readonly anomalies: AnomalyMetrics;
  readonly recoveryCapacity: RecoveryCapacityMetrics;
  readonly illnessRisk: IllnessRiskSignal;
  readonly decorrelation: DecorrelationAlert;
  readonly advancedInsights?: AdvancedInsights;
  readonly baselineDays: number;
}

export function AdvancedSection({
  overreaching,
  correlations,
  velocity,
  anomalies,
  recoveryCapacity,
  illnessRisk,
  decorrelation,
  advancedInsights,
  baselineDays,
}: AdvancedSectionProps) {
  return (
    <div className="flex flex-col gap-12">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <OverreachingCard overreaching={overreaching} />
        <CorrelationsCard correlations={correlations} />
        <VelocityCard velocity={velocity} />
      </div>

      <AnomaliesCard anomalies={anomalies} />

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <RecoveryCapacityCard recoveryCapacity={recoveryCapacity} />
        <IllnessRiskCard illnessRisk={illnessRisk} />
        <DecorrelationCard
          decorrelation={decorrelation}
          baselineDays={baselineDays}
        />
      </div>

      {advancedInsights && (
        <div>
          <SectionHead
            title={
              <>
                Deeper <SerifEm>insights</SerifEm>
              </>
            }
            meta={<>HRV · sleep · fitness · cross-domain</>}
          />
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <HrvAdvancedCard insights={advancedInsights} />
            <SleepQualityCard insights={advancedInsights} />
            <FitnessCard insights={advancedInsights} />
            <AllostaticLoadCard insights={advancedInsights} />
            <HrvResidualCard insights={advancedInsights} />
            <CrossDomainCard insights={advancedInsights} />
          </div>
        </div>
      )}
    </div>
  );
}
