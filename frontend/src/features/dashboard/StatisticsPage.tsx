import { useState } from "react";
import { format } from "date-fns";
import { useAnalytics } from "../../hooks/useAnalytics";
import { Button } from "../../components/ui/button";
import { LoadingState } from "../../components/ui/loading-state";
import { ErrorCard } from "../../components/ui/error-card";
import { TREND_MODES, MODE_ORDER, type TrendMode } from "../../lib/metrics";
import { Loader2 } from "lucide-react";
import { Masthead } from "../../components/luxury/Masthead";
import { SectionHead, SerifEm } from "../../components/luxury/SectionHead";
import { useToday } from "../../hooks/useToday";
import { HealthScoreSection } from "./statistics/HealthScoreSection";
import { RecoverySection } from "./statistics/RecoverySection";
import { SleepSection } from "./statistics/SleepSection";
import { ActivitySection } from "./statistics/ActivitySection";
import { ClinicalSection } from "./statistics/ClinicalSection";
import { AdvancedSection } from "./statistics/AdvancedSection";
import { LongevitySection } from "./statistics/LongevitySection";

function ModeBar({
  mode,
  setMode,
  isFetching,
}: Readonly<{
  mode: TrendMode;
  setMode: (m: TrendMode) => void;
  isFetching: boolean;
}>) {
  return (
    <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6 pt-14 pb-7 border-b border-foreground">
      <h2
        className="font-serif text-[clamp(36px,5vw,64px)] leading-none tracking-[-0.03em]"
        style={{
          fontVariationSettings: '"opsz" 144, "SOFT" 80',
          fontWeight: 350,
        }}
      >
        Statistics, <SerifEm>three horizons</SerifEm>
      </h2>
      <div className="flex items-end gap-3">
        {isFetching && (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-brass mb-2" />
        )}
        <div className="flex flex-wrap gap-0" role="tablist">
          {MODE_ORDER.map((m) => {
            const cfg = TREND_MODES[m];
            return (
              <Button
                key={m}
                variant={mode === m ? "default" : "outline"}
                size="sm"
                onClick={() => {
                  setMode(m);
                }}
                className="-ml-px first:ml-0"
              >
                {cfg.label} · {cfg.description}
              </Button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function TrendsMasthead() {
  const today = useToday();
  return (
    <Masthead
      leftLine="Section IV · Longitudinal"
      title={
        <>
          The <SerifEm>arc</SerifEm> of you
        </>
      }
      rightLine={`baselines & deviation · ${format(today, "d LLLL yyyy")}`}
    />
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
      <div className="space-y-0">
        <TrendsMasthead />
        <ModeBar mode={mode} setMode={setMode} isFetching={false} />
        <div className="pt-10">
          <ErrorCard message={`Failed to load health data: ${error.message}`} />
        </div>
      </div>
    );
  }

  if (isLoading || !analyticsData) {
    return (
      <div className="space-y-0">
        <TrendsMasthead />
        <ModeBar mode={mode} setMode={setMode} isFetching={isFetching} />
        <div className="pt-10">
          <LoadingState message="Analyzing health data..." />
        </div>
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
    <div className="space-y-0">
      <TrendsMasthead />
      <ModeBar mode={mode} setMode={setMode} isFetching={isFetching} />

      <section className="pt-12">
        <SectionHead
          title={
            <>
              Health <SerifEm>score</SerifEm>
            </>
          }
          meta={
            <>
              composite of recovery + behavior
              <br />
              {TREND_MODES[mode].label} window · {baselineDays}d baseline
            </>
          }
        />
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
      </section>

      <section className="pt-14">
        <SectionHead
          title={
            <>
              Recovery <SerifEm>balance</SerifEm>
            </>
          }
          meta={<>core load &amp; readiness</>}
        />
        <RecoverySection
          recoveryMetrics={recoveryMetrics}
          sleepMetrics={sleepMetrics}
          activityMetrics={activityMetrics}
          shortTermDays={shortTermDays}
          trendWindow={trendWindow}
        />
      </section>

      <section className="pt-14">
        <SectionHead
          title={
            <>
              Activity, weight &amp; <SerifEm>stress</SerifEm>
            </>
          }
          meta={<>load profile &amp; behavior support</>}
        />
        <ActivitySection
          activityMetrics={activityMetrics}
          weightMetrics={weightMetrics}
          recoveryMetrics={recoveryMetrics}
          shortTermDays={shortTermDays}
          baselineDays={baselineDays}
        />
      </section>

      <section className="pt-14">
        <SectionHead
          title={
            <>
              Sleep <SerifEm>analysis</SerifEm>
            </>
          }
          meta={<>target, debt &amp; consistency</>}
        />
        <SleepSection
          sleepMetrics={sleepMetrics}
          shortTermDays={shortTermDays}
          baselineDays={baselineDays}
        />
      </section>

      {clinicalAlerts.any_alert && (
        <section className="pt-14">
          <SectionHead
            title={
              <>
                Clinical <SerifEm>alerts</SerifEm>
              </>
            }
            meta={<>signals worth a second look</>}
          />
          <ClinicalSection clinicalAlerts={clinicalAlerts} />
        </section>
      )}

      <section className="pt-14">
        <SectionHead
          title={
            <>
              Advanced <SerifEm>signals</SerifEm>
            </>
          }
          meta={<>overreaching · correlations · velocity</>}
        />
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
      </section>

      {longevityInsights && (
        <section className="pt-14 pb-10">
          <SectionHead
            title={
              <>
                Longevity <SerifEm>pillars</SerifEm>
              </>
            }
            meta={<>biological age &amp; training zones</>}
          />
          <LongevitySection longevityInsights={longevityInsights} />
        </section>
      )}
    </div>
  );
}
