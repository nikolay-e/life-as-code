import { useState } from "react";
import { useAnalytics } from "../../hooks/useAnalytics";
import { Button } from "../../components/ui/button";
import { LoadingState } from "../../components/ui/loading-state";
import { ErrorCard } from "../../components/ui/error-card";
import { TREND_MODES, MODE_ORDER, type TrendMode } from "../../lib/metrics";
import { Calendar, Loader2 } from "lucide-react";
import { HealthScoreSection } from "./statistics/HealthScoreSection";
import { RecoverySection } from "./statistics/RecoverySection";
import { SleepSection } from "./statistics/SleepSection";
import { ActivitySection } from "./statistics/ActivitySection";
import { ClinicalSection } from "./statistics/ClinicalSection";
import { AdvancedSection } from "./statistics/AdvancedSection";
import { LongevitySection } from "./statistics/LongevitySection";

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
    longevity_insights: longevityInsights,
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

      <HealthScoreSection
        healthScore={healthScore}
        dayCompleteness={dayCompleteness}
        dataSourceSummary={dataSourceSummary}
        metricBaselines={metricBaselines}
        shortTermDays={shortTermDays}
        baselineDays={baselineDays}
        trendWindow={trendWindow}
        useShiftedZScore={useShiftedZScore}
      />

      <RecoverySection
        recoveryMetrics={recoveryMetrics}
        sleepMetrics={sleepMetrics}
        activityMetrics={activityMetrics}
        shortTermDays={shortTermDays}
        trendWindow={trendWindow}
      />

      <ActivitySection
        activityMetrics={activityMetrics}
        weightMetrics={weightMetrics}
        recoveryMetrics={recoveryMetrics}
        shortTermDays={shortTermDays}
        baselineDays={baselineDays}
      />

      <SleepSection
        sleepMetrics={sleepMetrics}
        shortTermDays={shortTermDays}
        baselineDays={baselineDays}
      />

      <ClinicalSection clinicalAlerts={clinicalAlerts} />

      <AdvancedSection
        overreaching={overreaching}
        correlations={correlations}
        velocity={velocity}
        anomalies={anomalies}
        recoveryCapacity={recoveryCapacity}
        illnessRisk={illnessRisk}
        decorrelation={decorrelation}
        advancedInsights={advancedInsights}
        baselineDays={baselineDays}
      />

      {longevityInsights && (
        <LongevitySection longevityInsights={longevityInsights} />
      )}
    </div>
  );
}
