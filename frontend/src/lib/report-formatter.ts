import { format } from "date-fns";
import type { HealthData } from "../types/api";
import {
  buildDashboardCards,
  TREND_MODES,
  MODE_ORDER,
  computeAllMetrics,
  getBaselineOptions,
  computeHealthAnalysis,
  type ComputedMetric,
  type HealthAnalysis,
} from "./metrics";
import {
  calculateRecoveryCapacity,
  calculateIllnessRiskSignal,
  calculateDecorrelationAlert,
} from "./health-metrics";

function formatNum(v: number | null, decimals = 2): string {
  return v !== null ? v.toFixed(decimals) : "N/A";
}

function formatMinutes(mins: number): string {
  const h = Math.floor(mins / 60);
  const m = Math.round(mins % 60);
  return h > 0 ? `${String(h)}h ${String(m)}m` : `${String(m)}m`;
}

export function formatTrendsForLLM(
  modeConfig: {
    label: string;
    shortTerm: number;
    baseline: number;
    trendWindow: number;
    description: string;
  },
  healthAnalysis: HealthAnalysis,
  computedMetrics: Record<string, ComputedMetric>,
  useShiftedZScore: boolean,
): string {
  const {
    healthScore,
    recoveryMetrics,
    sleepMetrics,
    activityMetrics,
    weightMetrics,
  } = healthAnalysis;

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

  const hrvData = computedMetrics.hrv.raw;
  const rhrData = computedMetrics.rhr.raw;
  const sleepData = computedMetrics.sleep.raw;
  const strainData = computedMetrics.strain.raw;

  const recoveryCapacity = calculateRecoveryCapacity(
    hrvData,
    strainData,
    modeConfig.baseline,
  );

  const illnessRisk = calculateIllnessRiskSignal(
    hrvData,
    rhrData,
    sleepData,
    modeConfig.baseline,
    3,
  );

  const decorrelationAlert = calculateDecorrelationAlert(
    hrvData,
    rhrData,
    14,
    modeConfig.baseline,
  );

  lines.push(
    `## Clinical Metrics`,
    ``,
    `### Recovery Capacity`,
    `- Avg Recovery Days: ${recoveryCapacity.avgRecoveryDays !== null ? recoveryCapacity.avgRecoveryDays.toFixed(1) : "N/A"}`,
    `- Recovery Efficiency: ${recoveryCapacity.recoveryEfficiency !== null ? recoveryCapacity.recoveryEfficiency.toFixed(2) : "N/A"}`,
    `- High Strain Events: ${String(recoveryCapacity.highStrainEvents)}`,
    `- Recovered Events: ${String(recoveryCapacity.recoveredEvents)}`,
    ``,
    `### Pre-Illness Risk Signal`,
    `- Risk Level: ${illnessRisk.riskLevel ?? "N/A"}`,
    `- Combined Deviation: ${illnessRisk.combinedDeviation !== null ? illnessRisk.combinedDeviation.toFixed(2) : "N/A"}`,
    `- Consecutive Days Elevated: ${String(illnessRisk.consecutiveDaysElevated)}`,
    `- HRV Drop: ${illnessRisk.components.hrvDrop !== null ? illnessRisk.components.hrvDrop.toFixed(2) : "N/A"}`,
    `- RHR Rise: ${illnessRisk.components.rhrRise !== null ? illnessRisk.components.rhrRise.toFixed(2) : "N/A"}`,
    `- Sleep Drop: ${illnessRisk.components.sleepDrop !== null ? illnessRisk.components.sleepDrop.toFixed(2) : "N/A"}`,
    ``,
    `### HRV-RHR Decorrelation Alert`,
    `- Is Decorrelated: ${decorrelationAlert.isDecorrelated ? "YES" : "No"}`,
    `- Current Correlation: ${decorrelationAlert.currentCorrelation !== null ? decorrelationAlert.currentCorrelation.toFixed(3) : "N/A"}`,
    `- Baseline Correlation: ${decorrelationAlert.baselineCorrelation !== null ? decorrelationAlert.baselineCorrelation.toFixed(3) : "N/A"}`,
    `- Correlation Delta: ${decorrelationAlert.correlationDelta !== null ? decorrelationAlert.correlationDelta.toFixed(3) : "N/A"}`,
    ``,
  );

  lines.push(
    `---`,
    `Z-Score Interpretation: <-2 very low, -1 to -2 low, -1 to +1 normal, +1 to +2 high, >+2 very high`,
    `ACWR Interpretation: <0.8 detraining, 0.8-1.3 optimal, 1.3-1.5 caution, >1.5 injury risk`,
  );

  return lines.join("\n");
}

export function formatCombinedReport(data: HealthData | null): string {
  if (!data) return "";

  const now = new Date();
  const sections: string[] = [];

  sections.push(
    `# Life-as-Code Health Report`,
    `Generated: ${format(now, "yyyy-MM-dd HH:mm")}`,
    ``,
    `========================================`,
    `PART 1: DASHBOARD SUMMARY (All Ranges)`,
    `========================================`,
    ``,
  );

  for (const m of MODE_ORDER) {
    const cfg = TREND_MODES[m];
    const cards = buildDashboardCards(data, cfg.rangeDays, now);

    sections.push(
      `## ${cfg.label} (${cfg.description}, ${String(cfg.rangeDays)} days)`,
      ...cards.map(
        (card) => `• ${card.title}: ${card.value} (${card.subtitle})`,
      ),
      ``,
    );
  }

  sections.push(
    ``,
    `========================================`,
    `PART 2: DETAILED TRENDS ANALYSIS`,
    `========================================`,
    ``,
  );

  for (const m of MODE_ORDER) {
    const cfg = TREND_MODES[m];
    const opts = getBaselineOptions(m, cfg);

    const metrics = computeAllMetrics(
      data,
      cfg.baseline,
      cfg.shortTerm,
      cfg.trendWindow,
      opts,
    );

    const analysis = computeHealthAnalysis(data, metrics, cfg, opts);

    sections.push(
      formatTrendsForLLM(cfg, analysis, metrics, cfg.useShiftedZScore),
      ``,
      `---`,
      ``,
    );
  }

  return sections.join("\n");
}
