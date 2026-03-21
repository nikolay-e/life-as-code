import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../../../components/ui/card";
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
  Moon,
  Activity,
  TrendingUp,
  Minus,
  Heart,
  Scale,
  Brain,
  Flame,
  GitBranch,
  Radar,
  ArrowUpRight,
  ArrowDownRight,
  RefreshCw,
  Thermometer,
  Unlink,
  Dumbbell,
} from "lucide-react";
import { cn } from "../../../lib/utils";
import {
  getCorrelationColor,
  getHrvSdColor,
  getTsbColor,
  getAllostaticScoreColor,
  getCrossCorrelationColor,
  signPrefix,
  formatMetricLabel,
} from "./stat-utils";

function OverreachingCard({
  overreaching,
}: Readonly<{
  overreaching: OverreachingMetrics;
}>) {
  return (
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
            {overreaching.score != null ? overreaching.score.toFixed(2) : "—"}
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
              {(overreaching.components.strain_component ?? null) !== null && (
                <span className="text-orange-500">
                  S:
                  {(overreaching.components.strain_component as number).toFixed(
                    1,
                  )}
                </span>
              )}
              {(overreaching.components.hrv_component ?? null) !== null && (
                <span className="text-red-500">
                  H:
                  {(overreaching.components.hrv_component as number).toFixed(1)}
                </span>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function CorrelationsCard({
  correlations,
}: Readonly<{
  correlations: CorrelationMetrics;
}>) {
  return (
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
              {correlations.hrv_rhr_correlation != null
                ? correlations.hrv_rhr_correlation.toFixed(2)
                : "—"}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-muted-foreground">Sleep → HRV</span>
            <span
              className={cn(
                "font-mono text-sm",
                correlations.sleep_hrv_lag_correlation != null &&
                  correlations.sleep_hrv_lag_correlation > 0.3
                  ? "text-green-500"
                  : "text-muted-foreground",
              )}
            >
              {correlations.sleep_hrv_lag_correlation != null
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
                correlations.strain_recovery_correlation != null &&
                  correlations.strain_recovery_correlation < -0.2
                  ? "text-green-500"
                  : "text-muted-foreground",
              )}
            >
              {correlations.strain_recovery_correlation != null
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
  );
}

function VelocityCard({ velocity }: Readonly<{ velocity: VelocityMetrics }>) {
  return (
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
                  {value != null
                    ? `${signPrefix(value)}${value.toFixed(2)} ${unit}`
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
  );
}

function AnomaliesCard({ anomalies }: Readonly<{ anomalies: AnomalyMetrics }>) {
  if (anomalies.anomaly_count === 0) return null;
  return (
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
          {anomalies.anomalies.slice(0, 8).map((anomaly) => (
            <div
              key={`${anomaly.date}-${anomaly.metric}`}
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
  );
}

function RecoveryCapacityCard({
  recoveryCapacity,
}: Readonly<{
  recoveryCapacity: RecoveryCapacityMetrics;
}>) {
  return (
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
              {recoveryCapacity.avg_recovery_days != null
                ? `${recoveryCapacity.avg_recovery_days.toFixed(1)} days`
                : "—"}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Recovery Efficiency</p>
            <p className="text-lg font-semibold">
              {recoveryCapacity.recovery_efficiency != null
                ? recoveryCapacity.recovery_efficiency.toFixed(2)
                : "—"}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">High Strain Events</p>
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
  );
}

function IllnessRiskCard({
  illnessRisk,
}: Readonly<{ illnessRisk: IllnessRiskSignal }>) {
  return (
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
              {illnessRisk.combined_deviation != null
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
              Sleep Drop: {illnessRisk.components.sleep_drop?.toFixed(2) ?? "—"}
              σ
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
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
    <Card
      className={decorrelation.is_decorrelated ? "border-orange-500/50" : ""}
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
            <span className="text-sm text-muted-foreground">Current (14d)</span>
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
          {decorrelation.correlation_delta != null && (
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Delta</span>
              <span
                className={cn(
                  "font-mono text-sm",
                  decorrelation.correlation_delta > 0.1 && "text-orange-500",
                )}
              >
                {signPrefix(decorrelation.correlation_delta)}
                {decorrelation.correlation_delta.toFixed(2)}
              </span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function HrvAdvancedCard({
  insights,
}: Readonly<{ insights: AdvancedInsights }>) {
  const h = insights.hrv_advanced;
  return (
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
            <span className="text-sm text-muted-foreground">lnRMSSD</span>
            <span className="font-mono text-sm font-semibold">
              {h.ln_rmssd_current?.toFixed(2) ?? "—"}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-muted-foreground">7d Mean</span>
            <span className="font-mono text-sm">
              {h.ln_rmssd_mean_7d?.toFixed(2) ?? "—"}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-muted-foreground">SD (7d)</span>
            <span
              className={cn(
                "font-mono text-sm",
                getHrvSdColor(h.ln_rmssd_sd_7d),
              )}
            >
              {h.ln_rmssd_sd_7d?.toFixed(3) ?? "—"}
            </span>
          </div>
          <div className="pt-2 border-t text-xs text-muted-foreground">
            <div className="flex justify-between">
              <span>HRV-RHR r(14d)</span>
              <span className="font-mono">
                {h.hrv_rhr_rolling_r_14d?.toFixed(2) ?? "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span>HRV-RHR r(60d)</span>
              <span className="font-mono">
                {h.hrv_rhr_rolling_r_60d?.toFixed(2) ?? "—"}
              </span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function SleepQualityCard({
  insights,
}: Readonly<{ insights: AdvancedInsights }>) {
  const sq = insights.sleep_quality;
  return (
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
            <span className="text-sm text-muted-foreground">Efficiency</span>
            <span className="font-mono text-sm">
              {sq.efficiency?.toFixed(1) ?? "—"}%
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-muted-foreground">Deep Sleep</span>
            <span
              className={cn(
                "font-mono text-sm",
                sq.deep_sleep_pct != null && sq.deep_sleep_pct >= 15
                  ? "text-green-500"
                  : "text-yellow-500",
              )}
            >
              {sq.deep_sleep_pct?.toFixed(1) ?? "—"}%
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-muted-foreground">REM Sleep</span>
            <span
              className={cn(
                "font-mono text-sm",
                sq.rem_sleep_pct != null && sq.rem_sleep_pct >= 20
                  ? "text-green-500"
                  : "text-yellow-500",
              )}
            >
              {sq.rem_sleep_pct?.toFixed(1) ?? "—"}%
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-muted-foreground">Consistency</span>
            <span className="font-mono text-sm">
              {sq.consistency_score?.toFixed(0) ?? "—"}/100
            </span>
          </div>
          <div className="pt-2 border-t text-xs text-muted-foreground">
            <div className="flex justify-between">
              <span>Sleep→HRV</span>
              <span className="font-mono">
                r {sq.sleep_hrv_responsiveness?.toFixed(2) ?? "—"}
                {sq.sleep_hrv_p_value != null &&
                  sq.sleep_hrv_p_value < 0.05 && (
                    <span className="text-green-500 ml-1">*</span>
                  )}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Fragmentation</span>
              <span className="font-mono">
                {sq.fragmentation_index?.toFixed(1) ?? "—"}/hr
              </span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function FitnessCard({ insights }: Readonly<{ insights: AdvancedInsights }>) {
  const f = insights.fitness;
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <Dumbbell className="h-4 w-4 text-blue-500" />
          <CardTitle className="text-base">Fitness & Training</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <span className="text-sm text-muted-foreground">Last Workout</span>
            <span
              className={cn(
                "font-mono text-sm",
                f.days_since_last_workout != null &&
                  f.days_since_last_workout > 7
                  ? "text-red-500"
                  : "text-green-500",
              )}
            >
              {f.days_since_last_workout != null
                ? `${String(f.days_since_last_workout)}d ago`
                : "—"}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-muted-foreground">Frequency</span>
            <span className="font-mono text-sm">
              {f.training_frequency_7d}/w · {f.training_frequency_30d}/mo
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-muted-foreground">
              CTL / ATL / TSB
            </span>
            <span className="font-mono text-sm">
              {f.ctl?.toFixed(1) ?? "—"} / {f.atl?.toFixed(1) ?? "—"} /{" "}
              <span className={cn(getTsbColor(f.tsb))}>
                {f.tsb?.toFixed(1) ?? "—"}
              </span>
            </span>
          </div>
          {f.vo2_max_current != null && (
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">VO2 Max</span>
              <span className="font-mono text-sm">
                {f.vo2_max_current.toFixed(1)}
              </span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function AllostaticLoadCard({
  insights,
}: Readonly<{ insights: AdvancedInsights }>) {
  const al = insights.allostatic_load;
  return (
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
                getAllostaticScoreColor(al.composite_score),
              )}
            >
              {al.composite_score?.toFixed(1) ?? "—"}
            </span>
          </div>
          <div className="text-xs text-muted-foreground pt-2 border-t space-y-1">
            {Object.entries(al.breach_rates).map(([metric, rate]) => (
              <div key={metric} className="flex justify-between">
                <span>{formatMetricLabel(metric)}</span>
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
  );
}

function HrvResidualCard({
  insights,
}: Readonly<{ insights: AdvancedInsights }>) {
  const residual = insights.cross_domain.hrv_residual;
  if (residual.r_squared == null) return null;
  return (
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
            <span className="text-sm text-muted-foreground">Predicted</span>
            <span className="font-mono text-sm">
              {residual.predicted?.toFixed(1) ?? "—"} ms
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-muted-foreground">Actual</span>
            <span className="font-mono text-sm">
              {residual.actual?.toFixed(1) ?? "—"} ms
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-muted-foreground">Residual z</span>
            <span
              className={cn(
                "font-mono text-sm",
                getZScoreColor(residual.residual_z),
              )}
            >
              {residual.residual_z?.toFixed(2) ?? "—"}σ
            </span>
          </div>
          <div className="text-xs text-muted-foreground pt-2 border-t">
            R² = {residual.r_squared.toFixed(3)}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function CrossDomainCard({
  insights,
}: Readonly<{ insights: AdvancedInsights }>) {
  const cd = insights.cross_domain;
  if (cd.weight_hrv_coupling == null) return null;
  return (
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
            <span className="text-sm text-muted-foreground">Weight↔HRV</span>
            <span
              className={cn(
                "font-mono text-sm",
                getCrossCorrelationColor(cd.weight_hrv_coupling),
              )}
            >
              r {cd.weight_hrv_coupling.toFixed(2)}
            </span>
          </div>
          <div className="text-xs text-muted-foreground pt-2 border-t space-y-1">
            {Object.entries(cd.weekday_weekend).map(([metric, split]) => (
              <div key={metric} className="flex justify-between">
                <span>{formatMetricLabel(metric)}</span>
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
    <>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <OverreachingCard overreaching={overreaching} />
        <CorrelationsCard correlations={correlations} />
        <VelocityCard velocity={velocity} />
      </div>

      <AnomaliesCard anomalies={anomalies} />

      <RecoveryCapacityCard recoveryCapacity={recoveryCapacity} />

      <IllnessRiskCard illnessRisk={illnessRisk} />

      <DecorrelationCard
        decorrelation={decorrelation}
        baselineDays={baselineDays}
      />

      {advancedInsights && (
        <div>
          <h2 className="text-xl font-semibold mb-4">Advanced Insights</h2>
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
    </>
  );
}
