import { useState, useMemo } from "react";
import { useAnalytics } from "../../hooks/useAnalytics";
import { useHealthDataRange } from "../../hooks/useHealthData";
import { useToday } from "../../hooks/useToday";
import { Button } from "../../components/ui/button";
import { LoadingState } from "../../components/ui/loading-state";
import { ErrorCard } from "../../components/ui/error-card";
import { ChartCard } from "../../components/charts/ChartCard";
import { ChartErrorBoundary } from "../../components/charts/ChartErrorBoundary";
import { SleepChart } from "../../components/charts/SleepChart";
import { TemperatureChart } from "../../components/charts/TemperatureChart";
import { SleepLatencyChart } from "../../components/charts/SleepLatencyChart";
import { TREND_MODES, MODE_ORDER, type TrendMode } from "../../lib/metrics";
import { formatSleepMinutes } from "../../lib/metrics/registry";
import { format, subDays } from "date-fns";
import { Moon, Loader2, Thermometer, Clock, Brain } from "lucide-react";
import { Masthead } from "../../components/luxury/Masthead";
import { SectionHead, SerifEm } from "../../components/luxury/SectionHead";
import { Vital } from "../../components/luxury/Vital";

function ModeSelector({
  mode,
  setMode,
}: Readonly<{ mode: TrendMode; setMode: (m: TrendMode) => void }>) {
  return (
    <div className="flex flex-wrap gap-0">
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
  );
}

function correlationTone(value: number): "up" | "down" | "flat" {
  if (Math.abs(value) < 0.4) return "flat";
  return value > 0 ? "up" : "down";
}

const toneClass = {
  up: "text-moss",
  down: "text-rust",
  flat: "text-muted-foreground",
};

function CorrelationRow({
  label,
  value,
}: Readonly<{ label: string; value: number | null | undefined }>) {
  if (value === null || value === undefined) return null;
  const tone = correlationTone(value);
  return (
    <div className="flex justify-between items-baseline py-2.5 border-b border-border last:border-b-0">
      <span className="type-mono-label text-muted-foreground">{label}</span>
      <span
        className={`font-mono text-[13px] ${toneClass[tone]}`}
        style={{ fontFeatureSettings: '"lnum","tnum"' }}
      >
        {value.toFixed(2)}
      </span>
    </div>
  );
}

function MetricRow({
  label,
  value,
  unit,
}: Readonly<{
  label: string;
  value: number | null | undefined;
  unit?: string;
}>) {
  if (value === null || value === undefined) return null;
  return (
    <div className="flex justify-between items-baseline py-2.5 border-b border-border last:border-b-0">
      <span className="type-mono-label text-muted-foreground">{label}</span>
      <span
        className="font-mono text-[13px] text-foreground"
        style={{ fontFeatureSettings: '"lnum","tnum"' }}
      >
        {typeof value === "number" ? value.toFixed(1) : value}
        {unit ? ` ${unit}` : ""}
      </span>
    </div>
  );
}

function formatScore(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return String(Math.round(v));
}

function formatPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v.toFixed(0);
}

function formatLatencyValue(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return String(Math.round(v));
}

function fmtDelta(value: number | null, unit = ""): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : value < 0 ? "" : "±";
  const arrow = value > 0 ? "↑" : value < 0 ? "↓" : "→";
  return `${arrow} ${sign}${value.toFixed(value >= 10 ? 0 : 1)}${unit}`;
}

function deltaTone(
  value: number | null,
  goodDirection: "up" | "down",
): "up" | "down" | "flat" {
  if (value == null || !Number.isFinite(value)) return "flat";
  if (Math.abs(value) < 0.5) return "flat";
  if (value > 0) return goodDirection === "up" ? "up" : "down";
  return goodDirection === "down" ? "up" : "down";
}

export function SleepOverviewPage() {
  const [mode, setMode] = useState<TrendMode>("recent");
  const {
    data: analyticsData,
    isLoading: analyticsLoading,
    isFetching,
    error: analyticsError,
  } = useAnalytics(mode);

  const today = useToday();
  const cfg = TREND_MODES[mode];
  const rangeDays = cfg.rangeDays;
  const startDate = format(subDays(today, rangeDays), "yyyy-MM-dd");
  const endDate = format(subDays(today, 1), "yyyy-MM-dd");

  const { data: healthData, isLoading: healthLoading } = useHealthDataRange(
    startDate,
    endDate,
  );

  const dateRange = useMemo(
    () => ({ start: startDate, end: endDate }),
    [startDate, endDate],
  );

  const todayDate = new Date();
  const dateLine = format(todayDate, "d LLLL yyyy");
  const weekday = format(todayDate, "EEEE");

  if (analyticsError) {
    return (
      <ErrorCard
        message={`Failed to load sleep data: ${analyticsError.message}`}
      />
    );
  }

  if (analyticsLoading || healthLoading || !analyticsData) {
    return (
      <div className="space-y-0">
        <Masthead
          leftLine={`№ ${format(todayDate, "DDD")} · ${weekday}`}
          title={
            <>
              Of <SerifEm>sleep</SerifEm>
            </>
          }
          rightLine={dateLine}
        />
        <section className="py-7">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-5 pb-4 border-b border-border">
            <span className="type-mono-eyebrow text-muted-foreground">
              window
            </span>
            <ModeSelector mode={mode} setMode={setMode} />
          </div>
        </section>
        <LoadingState message="Analyzing sleep data..." />
      </div>
    );
  }

  const { sleep_metrics: sleepMetrics, advanced_insights: advancedInsights } =
    analyticsData;
  const baselines = analyticsData.metric_baselines;
  const sleepQuality = advancedInsights?.sleep_quality;
  const sleepTemp = advancedInsights?.sleep_temperature;

  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition -- Record keys may be absent at runtime
  const sleepScoreCurrent = baselines.sleep_score?.current_value ?? null;
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  const sleepScoreMean = baselines.sleep_score?.mean ?? null;
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  const sleepLatencyCurrent = baselines.sleep_latency?.current_value ?? null;
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  const sleepLatencyMean = baselines.sleep_latency?.mean ?? null;
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  const tossCurrent = baselines.toss_and_turn?.current_value ?? null;
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  const tossMean = baselines.toss_and_turn?.mean ?? null;
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  const respCurrent = baselines.respiratory_rate?.current_value ?? null;
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  const respMean = baselines.respiratory_rate?.mean ?? null;

  const eightSleepData = healthData?.eight_sleep_sessions ?? [];

  const sleepDurationSpark = (healthData?.sleep ?? [])
    .slice(-30)
    .map((p) => (p.total_sleep_minutes ?? 0) / 60)
    .filter((v) => v > 0);

  const avgSleepShort = sleepMetrics.avg_sleep_short;
  const targetSleep = sleepMetrics.target_sleep;
  const sleepDurationDelta =
    avgSleepShort != null ? (avgSleepShort - targetSleep) / 60 : null;

  const sleepScoreDelta =
    sleepScoreCurrent != null && sleepScoreMean != null
      ? sleepScoreCurrent - sleepScoreMean
      : null;

  const latencyDelta =
    sleepLatencyCurrent != null && sleepLatencyMean != null
      ? sleepLatencyCurrent - sleepLatencyMean
      : null;

  const deepSleepDelta =
    sleepQuality?.deep_sleep_pct != null
      ? sleepQuality.deep_sleep_pct - 15
      : null;

  return (
    <div className="space-y-0">
      <Masthead
        leftLine={`№ ${format(todayDate, "DDD")} · ${weekday}`}
        title={
          <>
            Of <SerifEm>sleep</SerifEm>
          </>
        }
        rightLine={dateLine}
      />

      <section className="py-7">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-5 pb-4 border-b border-border">
          <span className="type-mono-eyebrow text-muted-foreground">
            window
          </span>
          <ModeSelector mode={mode} setMode={setMode} />
        </div>
        <div className="mt-3 flex items-center gap-2 type-mono-label text-muted-foreground">
          {isFetching && (
            <>
              <Loader2 className="h-3 w-3 animate-spin text-brass" />
              <span>fetching…</span>
            </>
          )}
        </div>
      </section>

      <section className="pt-10">
        <SectionHead
          title={
            <>
              Vital <SerifEm>signs</SerifEm>
            </>
          }
          meta={
            <>
              4 indices · {cfg.label.toLowerCase()} window
              <br />
              vs {cfg.description}
            </>
          }
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 divide-y divide-border sm:divide-y-0 sm:divide-x sm:[&>*:nth-child(3)]:border-l-0 sm:[&>*:nth-child(3)]:border-t lg:[&>*:nth-child(3)]:border-l lg:[&>*:nth-child(3)]:border-t-0">
          <Vital
            name="sleep score"
            value={formatScore(sleepScoreCurrent)}
            unit="/100"
            delta={fmtDelta(sleepScoreDelta)}
            deltaTone={deltaTone(sleepScoreDelta, "up")}
          />
          <Vital
            name="duration"
            value={
              avgSleepShort === null
                ? "—"
                : formatSleepMinutes(avgSleepShort).replace(/\s*[a-zA-Z]+$/, "")
            }
            unit={
              avgSleepShort === null
                ? undefined
                : (/[a-zA-Z]+$/.exec(formatSleepMinutes(avgSleepShort))?.[0] ??
                  undefined)
            }
            delta={fmtDelta(sleepDurationDelta, "h")}
            deltaTone={deltaTone(sleepDurationDelta, "up")}
            spark={sleepDurationSpark}
          />
          <Vital
            name="deep sleep"
            value={formatPct(sleepQuality?.deep_sleep_pct)}
            unit="%"
            delta={fmtDelta(deepSleepDelta, "pp")}
            deltaTone={deltaTone(deepSleepDelta, "up")}
          />
          <Vital
            name="latency"
            value={formatLatencyValue(sleepLatencyCurrent)}
            unit="min"
            delta={fmtDelta(latencyDelta)}
            deltaTone={deltaTone(latencyDelta, "down")}
          />
        </div>
      </section>

      <section className="pt-14">
        <SectionHead
          title={
            <>
              Stage <SerifEm>distribution</SerifEm>
            </>
          }
          meta={
            <>
              duration & breakdown
              <br />
              {rangeDays}d view
            </>
          }
        />
        <div className="grid gap-6 lg:grid-cols-2">
          <ChartCard
            title="Duration"
            icon={Moon}
            iconColorClass="text-foreground"
            iconBgClass="border border-border"
          >
            <ChartErrorBoundary>
              <SleepChart
                data={healthData?.sleep ?? []}
                showTrends
                dateRange={dateRange}
              />
            </ChartErrorBoundary>
          </ChartCard>

          <ChartCard
            title="Stage Breakdown"
            icon={Moon}
            iconColorClass="text-foreground"
            iconBgClass="border border-border"
          >
            <ChartErrorBoundary>
              <SleepChart
                data={healthData?.sleep ?? []}
                showBreakdown
                dateRange={dateRange}
              />
            </ChartErrorBoundary>
          </ChartCard>
        </div>
      </section>

      <section className="pt-14">
        <SectionHead
          title={
            <>
              Thermal <SerifEm>environment</SerifEm>
            </>
          }
          meta={
            sleepTemp ? (
              <>
                {sleepTemp.sample_size} nights observed
                <br />
                bed & room correlations
              </>
            ) : undefined
          }
        />
        <div className="grid gap-6 lg:grid-cols-2">
          <ChartCard
            title="Temperature"
            icon={Thermometer}
            iconColorClass="text-foreground"
            iconBgClass="border border-border"
          >
            <ChartErrorBoundary>
              <TemperatureChart data={eightSleepData} dateRange={dateRange} />
            </ChartErrorBoundary>
          </ChartCard>

          {sleepTemp && (
            <article className="border border-border p-7">
              <header className="flex items-baseline justify-between pb-4 mb-4 border-b border-border">
                <span className="type-mono-eyebrow text-foreground/80">
                  Temperature & Sleep
                </span>
                <span className="type-mono-label text-muted-foreground">
                  n = {sleepTemp.sample_size}
                </span>
              </header>
              <div className="space-y-0">
                <CorrelationRow
                  label="Bed Temp → Sleep Score"
                  value={sleepTemp.bed_temp_sleep_score_r}
                />
                <CorrelationRow
                  label="Bed Temp → Deep Sleep %"
                  value={sleepTemp.bed_temp_deep_pct_r}
                />
                <CorrelationRow
                  label="Room Temp → Sleep Score"
                  value={sleepTemp.room_temp_sleep_score_r}
                />
                <MetricRow
                  label="Optimal Bed Temp"
                  value={sleepTemp.optimal_bed_temp}
                  unit="°C"
                />
                <MetricRow
                  label="Optimal Room Temp"
                  value={sleepTemp.optimal_room_temp}
                  unit="°C"
                />
              </div>
            </article>
          )}
        </div>
      </section>

      {eightSleepData.length > 0 && (
        <section className="pt-14">
          <SectionHead
            title={
              <>
                Eight Sleep <SerifEm>indices</SerifEm>
              </>
            }
            meta={<>fitness · routine · quality</>}
          />
          <div className="grid grid-cols-1 sm:grid-cols-3 divide-y divide-border sm:divide-y-0 sm:divide-x">
            <SleepIndexTile
              name="Sleep Fitness"
              baseline={baselines.sleep_fitness}
            />
            <SleepIndexTile
              name="Sleep Routine"
              baseline={baselines.sleep_routine}
            />
            <SleepIndexTile
              name="Sleep Quality"
              baseline={baselines.sleep_quality_es}
            />
          </div>
        </section>
      )}

      {sleepQuality && (
        <section className="pt-14">
          <SectionHead
            title={
              <>
                Quality <SerifEm>analytics</SerifEm>
              </>
            }
            meta={<>architecture & responsiveness</>}
          />
          <div className="grid gap-0 md:grid-cols-3 border-t border-border">
            <div className="p-7 border-b md:border-b-0 md:border-r border-border">
              <span className="type-mono-eyebrow text-muted-foreground block mb-4">
                stages
              </span>
              <div className="space-y-0">
                <MetricRow
                  label="Deep Sleep"
                  value={sleepQuality.deep_sleep_pct}
                  unit="%"
                />
                <MetricRow
                  label="REM Sleep"
                  value={sleepQuality.rem_sleep_pct}
                  unit="%"
                />
              </div>
            </div>
            <div className="p-7 border-b md:border-b-0 md:border-r border-border">
              <span className="type-mono-eyebrow text-muted-foreground block mb-4">
                consistency
              </span>
              <div className="space-y-0">
                <MetricRow
                  label="Efficiency"
                  value={sleepQuality.efficiency}
                  unit="%"
                />
                <MetricRow
                  label="Consistency"
                  value={sleepQuality.consistency_score}
                  unit="/100"
                />
              </div>
            </div>
            <div className="p-7">
              <span className="type-mono-eyebrow text-muted-foreground block mb-4">
                disturbance
              </span>
              <div className="space-y-0">
                <MetricRow
                  label="Fragmentation"
                  value={sleepQuality.fragmentation_index}
                  unit="/hr"
                />
                <MetricRow
                  label="Sleep→HRV Response"
                  value={sleepQuality.sleep_hrv_responsiveness}
                />
              </div>
            </div>
          </div>
        </section>
      )}

      <section className="pt-14">
        <SectionHead
          title={
            <>
              Debt & <SerifEm>targets</SerifEm>
            </>
          }
          meta={<>balance against {cfg.description}</>}
        />
        <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-y md:divide-y-0 divide-border border-y border-border">
          <DebtTile
            label="target"
            value={formatSleepMinutes(sleepMetrics.target_sleep)}
          />
          <DebtTile
            label="consistency cv"
            value={`${(sleepMetrics.sleep_cv * 100).toFixed(0)}%`}
          />
          <DebtTile
            label="debt"
            value={
              sleepMetrics.sleep_debt_short > 0
                ? `−${formatSleepMinutes(sleepMetrics.sleep_debt_short)}`
                : "—"
            }
            tone={sleepMetrics.sleep_debt_short > 0 ? "down" : "flat"}
          />
          <DebtTile
            label="surplus"
            value={
              sleepMetrics.sleep_surplus_short > 0
                ? `+${formatSleepMinutes(sleepMetrics.sleep_surplus_short)}`
                : "—"
            }
            tone={sleepMetrics.sleep_surplus_short > 0 ? "up" : "flat"}
          />
        </div>
      </section>

      <section className="pt-14">
        <SectionHead
          title={
            <>
              Onset & <SerifEm>movement</SerifEm>
            </>
          }
          meta={<>latency · toss & turn · respiration</>}
        />
        <div className="grid gap-6 lg:grid-cols-2">
          <ChartCard
            title="Sleep Latency"
            icon={Clock}
            iconColorClass="text-foreground"
            iconBgClass="border border-border"
          >
            <ChartErrorBoundary>
              <SleepLatencyChart data={eightSleepData} dateRange={dateRange} />
            </ChartErrorBoundary>
          </ChartCard>

          <article className="border border-border p-7">
            <header className="flex items-baseline justify-between pb-4 mb-4 border-b border-border">
              <span className="type-mono-eyebrow text-foreground/80">
                Toss & Turn
              </span>
              <Brain className="h-3.5 w-3.5 text-muted-foreground" />
            </header>
            <div className="space-y-0">
              <MetricRow label="Current" value={tossCurrent} unit="times" />
              <MetricRow label="Average" value={tossMean} unit="times" />
              <MetricRow
                label="Respiratory Rate"
                value={respCurrent}
                unit="br/min"
              />
              <MetricRow
                label="Resp. Rate Avg"
                value={respMean}
                unit="br/min"
              />
            </div>
          </article>
        </div>
      </section>
    </div>
  );
}

function SleepIndexTile({
  name,
  baseline,
}: Readonly<{
  name: string;
  baseline?: {
    current_value: number | null;
    mean: number | null;
    z_score: number | null;
  };
}>) {
  const current = baseline?.current_value;
  const mean = baseline?.mean;
  const zScore = baseline?.z_score;
  const delta = current != null && mean != null ? current - mean : null;

  let zToneClass = "text-muted-foreground";
  if (zScore != null) {
    if (zScore >= 0.5) zToneClass = "text-moss";
    else if (zScore <= -0.5) zToneClass = "text-rust";
  }

  return (
    <article className="relative flex flex-col gap-3.5 px-5 py-7">
      <header className="flex items-baseline justify-between gap-3">
        <span className="type-mono-eyebrow text-foreground/80">{name}</span>
        <span className="type-mono-label text-muted-foreground">
          avg{" "}
          {mean === null || mean === undefined ? "—" : String(Math.round(mean))}
        </span>
      </header>
      <div
        className="font-serif text-[clamp(46px,5.5vw,68px)] leading-[0.9] tracking-[-0.04em] flex items-baseline gap-2"
        style={{
          fontVariationSettings: '"opsz" 144, "SOFT" 60',
          fontWeight: 350,
        }}
      >
        <span style={{ fontFeatureSettings: '"lnum","tnum"' }}>
          {formatScore(current)}
        </span>
        <span className="font-mono text-[12px] text-muted-foreground tracking-wide font-normal">
          /100
        </span>
      </div>
      <div className="flex items-center justify-between gap-3 mt-auto pt-2">
        <span className="font-mono text-[11px] text-muted-foreground">
          {fmtDelta(delta)}
        </span>
        {zScore !== null && zScore !== undefined && (
          <span
            className={`font-mono text-[11px] ${zToneClass}`}
            style={{ fontFeatureSettings: '"lnum","tnum"' }}
          >
            {`${(zScore >= 0 ? "+" : "") + zScore.toFixed(1)}σ`}
          </span>
        )}
      </div>
    </article>
  );
}

function DebtTile({
  label,
  value,
  tone = "flat",
}: Readonly<{
  label: string;
  value: string;
  tone?: "up" | "down" | "flat";
}>) {
  return (
    <div className="px-5 py-7 flex flex-col gap-3">
      <span className="type-mono-eyebrow text-muted-foreground">{label}</span>
      <div
        className={`font-serif text-[clamp(28px,3.6vw,42px)] leading-[0.95] tracking-[-0.03em] ${toneClass[tone]}`}
        style={{
          fontVariationSettings: '"opsz" 144, "SOFT" 60',
          fontWeight: 350,
          fontFeatureSettings: '"lnum","tnum"',
        }}
      >
        {value}
      </div>
    </div>
  );
}
