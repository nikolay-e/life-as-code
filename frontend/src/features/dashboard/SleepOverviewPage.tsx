import { useState, useMemo } from "react";
import { useAnalytics } from "../../hooks/useAnalytics";
import { useHealthDataRange } from "../../hooks/useHealthData";
import { useToday } from "../../hooks/useToday";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../../components/ui/card";
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
import { format, parseISO, subDays } from "date-fns";
import {
  Moon,
  Calendar,
  Loader2,
  Thermometer,
  Clock,
  Award,
  RotateCcw,
  Sparkles,
  Star,
  Hash,
  Brain,
  Battery,
  Activity,
  Wind,
  Droplet,
  Bed,
  AlarmClock,
  Sunset,
  Heart,
} from "lucide-react";
import type { SleepData, WhoopSleepData } from "../../types/api";

function ModeSelector({
  mode,
  setMode,
}: Readonly<{ mode: TrendMode; setMode: (m: TrendMode) => void }>) {
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
            <span className="text-[10px]">{cfg.description}</span>
          </Button>
        );
      })}
    </div>
  );
}

function SummaryCard({
  title,
  value,
  subtitle,
  icon: Icon,
}: Readonly<{
  title: string;
  value: string;
  subtitle?: string;
  icon: React.ElementType;
}>) {
  return (
    <Card>
      <CardContent className="pt-4 pb-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className="text-2xl font-bold mt-1">{value}</p>
            {subtitle && (
              <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>
            )}
          </div>
          <div className="p-2 rounded-full bg-sleep-muted">
            <Icon className="h-5 w-5 text-sleep" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function formatSkinTempDeviation(v: number | null): string {
  if (v === null) return "—";
  const sign = v >= 0 ? "+" : "";
  return `${sign}${v.toFixed(2)} °C`;
}

function bodyBatteryArrowFor(v: number | null): string {
  if (v === null) return "";
  return v >= 0 ? "↑" : "↓";
}

function bodyBatteryColorFor(v: number | null): string {
  if (v === null) return "";
  return v >= 0 ? "text-green-700" : "text-red-700";
}

function correlationColor(value: number): string {
  if (Math.abs(value) < 0.4) return "text-muted-foreground";
  return value > 0 ? "text-green-700" : "text-red-700";
}

function CorrelationValue({
  label,
  value,
}: Readonly<{ label: string; value: number | null | undefined }>) {
  if (value === null || value === undefined) return null;
  const color = correlationColor(value);
  return (
    <div className="flex justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className={color}>{value.toFixed(2)}</span>
    </div>
  );
}

function MetricValue({
  label,
  value,
  unit,
  good,
}: Readonly<{
  label: string;
  value: number | null | undefined;
  unit?: string;
  good?: boolean;
}>) {
  if (value === null || value === undefined) return null;
  let color = "";
  if (good === true) color = "text-green-700";
  else if (good === false) color = "text-yellow-700";
  return (
    <div className="flex justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className={`font-medium ${color}`}>
        {typeof value === "number" ? value.toFixed(1) : value}
        {unit ? ` ${unit}` : ""}
      </span>
    </div>
  );
}

function formatScore(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${String(Math.round(v))}/100`;
}

function formatScoreSubtitle(v: number | null | undefined): string | undefined {
  if (v === null || v === undefined) return undefined;
  return `avg: ${String(Math.round(v))}/100`;
}

function formatPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${v.toFixed(0)}%`;
}

function deepSleepSubtitle(v: number | null | undefined): string | undefined {
  if (v === null || v === undefined) return undefined;
  return v >= 15 ? "On target (15%+)" : "Below target";
}

function formatLatency(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${String(Math.round(v))} min`;
}

function latencySubtitle(v: number | null | undefined): string | undefined {
  if (v === null || v === undefined) return undefined;
  return v <= 20 ? "Good (<20 min)" : "Elevated";
}

function pickLatest<T extends { date: string }>(
  items: T[] | undefined,
  field: keyof T,
): T | null {
  if (!items || items.length === 0) return null;
  const filtered = items.filter((entry) => {
    const value = entry[field];
    return value !== null && value !== undefined;
  });
  if (filtered.length === 0) return null;
  const sorted = [...filtered].sort((a, b) => b.date.localeCompare(a.date));
  return sorted[0] ?? null;
}

function pickLatestWhoop(
  items: WhoopSleepData[] | undefined,
): WhoopSleepData | null {
  if (!items || items.length === 0) return null;
  const sorted = [...items].sort((a, b) => b.date.localeCompare(a.date));
  return sorted[0] ?? null;
}

function formatHoursMinutes(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return "—";
  const total = Math.max(0, Math.round(minutes));
  const h = Math.floor(total / 60);
  const m = total % 60;
  return `${String(h)}:${String(m).padStart(2, "0")}`;
}

function formatMinutesUnit(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return "—";
  return `${String(Math.round(minutes))} min`;
}

function spo2Color(value: number | null | undefined): string {
  if (value === null || value === undefined) return "text-muted-foreground";
  if (value >= 95) return "text-green-700";
  if (value >= 90) return "text-yellow-700";
  return "text-red-700";
}

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  valueClass,
}: Readonly<{
  title: string;
  value: string;
  subtitle?: string;
  icon: React.ElementType;
  valueClass?: string;
}>) {
  return (
    <Card>
      <CardContent className="pt-4 pb-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className={`text-2xl font-bold mt-1 ${valueClass ?? ""}`}>
              {value}
            </p>
            {subtitle && (
              <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>
            )}
          </div>
          <div className="p-2 rounded-full bg-sleep-muted">
            <Icon className="h-5 w-5 text-sleep" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function pickSleepLatestField(
  sleep: SleepData[] | undefined,
  field: keyof SleepData,
): number | null {
  const entry = pickLatest(sleep ?? [], field);
  if (!entry) return null;
  const value = entry[field];
  return typeof value === "number" ? value : null;
}

function zScoreColor(z: number): string {
  if (z >= 0.5) return "text-green-700";
  if (z <= -0.5) return "text-red-700";
  return "";
}

function formatSleepTime(timeStr: string | null | undefined): string {
  if (!timeStr) return "—";
  try {
    return format(parseISO(timeStr), "h:mm a");
  } catch {
    return "—";
  }
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

  const eightSleepData = healthData?.eight_sleep_sessions ?? [];

  const latestEightSleepBiometrics = useMemo(() => {
    let hr: number | null = null;
    let hrv: number | null = null;
    let latencyOut: number | null = null;
    for (let i = eightSleepData.length - 1; i >= 0; i--) {
      const s = eightSleepData[i];
      if (hr === null && s.heart_rate !== null) hr = s.heart_rate;
      if (hrv === null && s.hrv !== null) hrv = s.hrv;
      if (latencyOut === null && s.latency_out_seconds !== null) {
        latencyOut = s.latency_out_seconds;
      }
      if (hr !== null && hrv !== null && latencyOut !== null) break;
    }
    if (hr === null && hrv === null && latencyOut === null) return null;
    return { hr, hrv, latencyOut };
  }, [eightSleepData]);

  if (analyticsError) {
    return (
      <ErrorCard
        message={`Failed to load sleep data: ${analyticsError.message}`}
      />
    );
  }

  if (analyticsLoading || healthLoading || !analyticsData) {
    return (
      <div className="space-y-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              Sleep Analytics
            </h1>
            <p className="text-muted-foreground mt-1">
              Deep dive into your sleep data
            </p>
          </div>
          <ModeSelector mode={mode} setMode={setMode} />
        </div>
        <LoadingState message="Analyzing sleep data..." />
      </div>
    );
  }

  const { sleep_metrics: sleepMetrics, advanced_insights: advancedInsights } =
    analyticsData;
  const baselines = analyticsData.metric_baselines;
  const rawSeries = analyticsData.raw_series;
  const sleepQuality = advancedInsights?.sleep_quality;
  const sleepTemp = advancedInsights?.sleep_temperature;

  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition -- Record keys may be absent at runtime
  const sleepScoreCurrent = baselines.sleep_score?.current_value ?? null;
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  const sleepScoreMean = baselines.sleep_score?.mean ?? null;
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  const sleepLatencyCurrent = baselines.sleep_latency?.current_value ?? null;
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  const tossCurrent = baselines.toss_and_turn?.current_value ?? null;
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  const tossMean = baselines.toss_and_turn?.mean ?? null;
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  const respCurrent = baselines.respiratory_rate?.current_value ?? null;
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  const respMean = baselines.respiratory_rate?.mean ?? null;

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Sleep Analytics</h1>
          <p className="text-muted-foreground mt-1">
            Deep dive into your sleep data
          </p>
        </div>
        <div className="flex items-center gap-3">
          {isFetching && (
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
          )}
          <ModeSelector mode={mode} setMode={setMode} />
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          title="Sleep Score"
          value={formatScore(sleepScoreCurrent)}
          subtitle={formatScoreSubtitle(sleepScoreMean)}
          icon={Star}
        />
        <SummaryCard
          title="Sleep Duration"
          value={
            sleepMetrics.avg_sleep_short === null
              ? "—"
              : formatSleepMinutes(sleepMetrics.avg_sleep_short)
          }
          subtitle={`target: ${formatSleepMinutes(sleepMetrics.target_sleep)}`}
          icon={Moon}
        />
        <SummaryCard
          title="Deep Sleep"
          value={formatPct(sleepQuality?.deep_sleep_pct)}
          subtitle={deepSleepSubtitle(sleepQuality?.deep_sleep_pct)}
          icon={Brain}
        />
        <SummaryCard
          title="Sleep Latency"
          value={formatLatency(sleepLatencyCurrent)}
          subtitle={latencySubtitle(sleepLatencyCurrent)}
          icon={Clock}
        />
      </div>

      {/* Sleep Timing */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg flex items-center gap-2">
            <AlarmClock className="h-5 w-5 text-sleep" />
            Sleep Timing
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
            {(() => {
              const sleepArr = healthData?.sleep ?? [];
              const whoopSleepArr = healthData?.whoop_sleep ?? [];
              let bedtime: string | null = null;
              let wakeTime: string | null = null;
              for (let i = sleepArr.length - 1; i >= 0; i--) {
                const s = sleepArr[i];
                if (s.sleep_start_time) {
                  bedtime = s.sleep_start_time;
                  wakeTime = s.sleep_end_time ?? null;
                  break;
                }
              }
              if (!bedtime) {
                for (let i = whoopSleepArr.length - 1; i >= 0; i--) {
                  const s = whoopSleepArr[i];
                  if (s.sleep_start_time) {
                    bedtime = s.sleep_start_time;
                    wakeTime = s.sleep_end_time ?? null;
                    break;
                  }
                }
              }
              const parseTimeMinutes = (t: string): number | null => {
                try {
                  const d = parseISO(t);
                  return d.getHours() * 60 + d.getMinutes();
                } catch {
                  return null;
                }
              };
              const bedtimes = sleepArr
                .map((s) =>
                  s.sleep_start_time
                    ? parseTimeMinutes(s.sleep_start_time)
                    : null,
                )
                .filter((v): v is number => v !== null);
              const avgBedtimeMin =
                bedtimes.length > 0
                  ? bedtimes.reduce((a, b) => a + b, 0) / bedtimes.length
                  : null;
              const avgBedtimeStr =
                avgBedtimeMin !== null
                  ? `${String(Math.floor((((avgBedtimeMin % 1440) + 1440) % 1440) / 60) % 12 || 12)}:${String(Math.round(avgBedtimeMin % 60)).padStart(2, "0")} ${avgBedtimeMin % 1440 >= 720 ? "PM" : "AM"}`
                  : null;
              return (
                <>
                  <StatCard
                    title="Bedtime"
                    value={formatSleepTime(bedtime)}
                    icon={Sunset}
                  />
                  <StatCard
                    title="Wake Time"
                    value={formatSleepTime(wakeTime)}
                    icon={AlarmClock}
                  />
                  <StatCard
                    title="Avg Bedtime"
                    value={avgBedtimeStr ?? "—"}
                    icon={Clock}
                  />
                  <StatCard
                    title="Nights Tracked"
                    value={String(
                      sleepArr.filter((s) => s.sleep_start_time).length,
                    )}
                    icon={Calendar}
                  />
                </>
              );
            })()}
          </div>
        </CardContent>
      </Card>

      {/* Sleep Duration Chart */}
      <ChartErrorBoundary>
        <ChartCard
          title="Sleep Duration"
          icon={Moon}
          iconColorClass="text-sleep"
          iconBgClass="bg-sleep-muted"
        >
          <SleepChart
            data={healthData?.sleep ?? []}
            showTrends
            dateRange={dateRange}
          />
        </ChartCard>
      </ChartErrorBoundary>

      {/* Sleep Stages Breakdown */}
      <ChartErrorBoundary>
        <ChartCard
          title="Sleep Stage Breakdown"
          icon={Moon}
          iconColorClass="text-sleep"
          iconBgClass="bg-sleep-muted"
        >
          <SleepChart
            data={healthData?.sleep ?? []}
            showBreakdown
            dateRange={dateRange}
          />
        </ChartCard>
      </ChartErrorBoundary>

      {/* Temperature Environment */}
      <div className="grid gap-6 md:grid-cols-2">
        <ChartErrorBoundary>
          <ChartCard
            title="Temperature Environment"
            icon={Thermometer}
            iconColorClass="text-orange-500"
            iconBgClass="bg-orange-100 dark:bg-orange-900/30"
          >
            <TemperatureChart data={eightSleepData} dateRange={dateRange} />
          </ChartCard>
        </ChartErrorBoundary>

        {sleepTemp && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-lg flex items-center gap-2">
                <Thermometer className="h-5 w-5 text-orange-500" />
                Temperature & Sleep
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <CorrelationValue
                label="Bed Temp → Sleep Score"
                value={sleepTemp.bed_temp_sleep_score_r}
              />
              <CorrelationValue
                label="Bed Temp → Deep Sleep %"
                value={sleepTemp.bed_temp_deep_pct_r}
              />
              <CorrelationValue
                label="Room Temp → Sleep Score"
                value={sleepTemp.room_temp_sleep_score_r}
              />
              <hr className="my-2 border-border/50" />
              <MetricValue
                label="Optimal Bed Temp"
                value={sleepTemp.optimal_bed_temp}
                unit="°C"
              />
              <MetricValue
                label="Optimal Room Temp"
                value={sleepTemp.optimal_room_temp}
                unit="°C"
              />
              <p className="text-xs text-muted-foreground mt-2">
                Based on {sleepTemp.sample_size} nights
              </p>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Eight Sleep Scores */}
      {eightSleepData.length > 0 && (
        <div className="grid gap-4 md:grid-cols-3">
          <ScoreCard
            title="Sleep Fitness"
            icon={Award}
            baseline={baselines.sleep_fitness}
            series={rawSeries.sleep_fitness}
          />
          <ScoreCard
            title="Sleep Routine"
            icon={RotateCcw}
            baseline={baselines.sleep_routine}
            series={rawSeries.sleep_routine}
          />
          <ScoreCard
            title="Sleep Quality"
            icon={Sparkles}
            baseline={baselines.sleep_quality_es}
            series={rawSeries.sleep_quality_es}
          />
        </div>
      )}

      {/* Sleep Quality Analytics */}
      {sleepQuality && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <Brain className="h-5 w-5 text-sleep" />
              Sleep Quality Analytics
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <div className="space-y-2">
                <MetricValue
                  label="Deep Sleep"
                  value={sleepQuality.deep_sleep_pct}
                  unit="%"
                  good={
                    sleepQuality.deep_sleep_pct === null
                      ? undefined
                      : sleepQuality.deep_sleep_pct >= 15
                  }
                />
                <MetricValue
                  label="REM Sleep"
                  value={sleepQuality.rem_sleep_pct}
                  unit="%"
                  good={
                    sleepQuality.rem_sleep_pct === null
                      ? undefined
                      : sleepQuality.rem_sleep_pct >= 20
                  }
                />
              </div>
              <div className="space-y-2">
                <MetricValue
                  label="Efficiency"
                  value={sleepQuality.efficiency}
                  unit="%"
                  good={
                    sleepQuality.efficiency === null
                      ? undefined
                      : sleepQuality.efficiency >= 85
                  }
                />
                <MetricValue
                  label="Consistency"
                  value={sleepQuality.consistency_score}
                  unit="/100"
                />
              </div>
              <div className="space-y-2">
                <MetricValue
                  label="Fragmentation"
                  value={sleepQuality.fragmentation_index}
                  unit="/hr"
                />
                <MetricValue
                  label="Sleep→HRV Response"
                  value={sleepQuality.sleep_hrv_responsiveness}
                  unit=""
                />
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Sleep Debt & Targets */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg flex items-center gap-2">
            <Moon className="h-5 w-5 text-sleep" />
            Sleep Debt & Targets
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <div className="text-center">
              <p className="text-sm text-muted-foreground">Target</p>
              <p className="text-xl font-bold">
                {formatSleepMinutes(sleepMetrics.target_sleep)}
              </p>
            </div>
            <div className="text-center">
              <p className="text-sm text-muted-foreground">Consistency (CV)</p>
              <p className="text-xl font-bold">
                {(sleepMetrics.sleep_cv * 100).toFixed(0)}%
              </p>
            </div>
            <div className="text-center">
              <p className="text-sm text-muted-foreground">Sleep Debt</p>
              <p className="text-xl font-bold text-red-700">
                {sleepMetrics.sleep_debt_short > 0
                  ? `-${formatSleepMinutes(sleepMetrics.sleep_debt_short)}`
                  : "—"}
              </p>
            </div>
            <div className="text-center">
              <p className="text-sm text-muted-foreground">Sleep Surplus</p>
              <p className="text-xl font-bold text-green-700">
                {sleepMetrics.sleep_surplus_short > 0
                  ? `+${formatSleepMinutes(sleepMetrics.sleep_surplus_short)}`
                  : "—"}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Body & Recovery */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg flex items-center gap-2">
            <Battery className="h-5 w-5 text-sleep" />
            Body & Recovery
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
            {(() => {
              const sleep = healthData?.sleep ?? [];
              const bodyBattery = pickSleepLatestField(
                sleep,
                "body_battery_change",
              );
              const skinTempDeviation = pickSleepLatestField(
                sleep,
                "skin_temp_deviation_c",
              );
              const awakeCount = pickSleepLatestField(sleep, "awake_count");
              const respRate = pickSleepLatestField(sleep, "respiratory_rate");
              const bodyBatteryArrow = bodyBatteryArrowFor(bodyBattery);
              const bodyBatteryColor = bodyBatteryColorFor(bodyBattery);
              return (
                <>
                  <StatCard
                    title="Body Battery Δ"
                    value={
                      bodyBattery === null
                        ? "—"
                        : `${bodyBatteryArrow} ${String(Math.round(bodyBattery))}`
                    }
                    icon={Battery}
                    valueClass={bodyBatteryColor}
                  />
                  <StatCard
                    title="Skin Temp Δ"
                    value={formatSkinTempDeviation(skinTempDeviation)}
                    icon={Thermometer}
                  />
                  <StatCard
                    title="Awakenings"
                    value={
                      awakeCount === null ? "—" : String(Math.round(awakeCount))
                    }
                    icon={Activity}
                  />
                  <StatCard
                    title="Respiratory Rate"
                    value={
                      respRate === null ? "—" : `${respRate.toFixed(1)} br/min`
                    }
                    icon={Wind}
                  />
                </>
              );
            })()}
          </div>
        </CardContent>
      </Card>

      {/* SpO2 (Garmin) */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg flex items-center gap-2">
            <Droplet className="h-5 w-5 text-sleep" />
            Blood Oxygen
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 grid-cols-2">
            {(() => {
              const sleep = healthData?.sleep ?? [];
              const spo2Avg = pickSleepLatestField(sleep, "spo2_avg");
              const spo2Min = pickSleepLatestField(sleep, "spo2_min");
              return (
                <>
                  <StatCard
                    title="SpO2 Avg"
                    value={spo2Avg === null ? "—" : `${spo2Avg.toFixed(1)} %`}
                    icon={Droplet}
                    valueClass={spo2Color(spo2Avg)}
                  />
                  <StatCard
                    title="SpO2 Min"
                    value={spo2Min === null ? "—" : `${spo2Min.toFixed(1)} %`}
                    icon={Droplet}
                    valueClass={spo2Color(spo2Min)}
                  />
                </>
              );
            })()}
          </div>
        </CardContent>
      </Card>

      {/* Eight Sleep Biometrics */}
      {latestEightSleepBiometrics !== null && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <Heart className="h-5 w-5 text-sleep" />
              Eight Sleep Biometrics
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 grid-cols-2 lg:grid-cols-3">
              {latestEightSleepBiometrics.hr !== null && (
                <StatCard
                  title="Sleep HR"
                  value={`${String(Math.round(latestEightSleepBiometrics.hr))} bpm`}
                  icon={Heart}
                />
              )}
              {latestEightSleepBiometrics.hrv !== null && (
                <StatCard
                  title="Sleep HRV"
                  value={`${String(Math.round(latestEightSleepBiometrics.hrv))} ms`}
                  icon={Activity}
                />
              )}
              {latestEightSleepBiometrics.latencyOut !== null && (
                <StatCard
                  title="Latency Out"
                  value={
                    latestEightSleepBiometrics.latencyOut < 60
                      ? `${String(Math.round(latestEightSleepBiometrics.latencyOut))}s`
                      : `${String(Math.round(latestEightSleepBiometrics.latencyOut / 60))}m`
                  }
                  icon={Clock}
                />
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Whoop Sleep Need */}
      {(() => {
        const whoopSleep = healthData?.whoop_sleep ?? [];
        if (whoopSleep.length === 0) return null;
        const latest = pickLatestWhoop(whoopSleep);
        if (!latest) return null;
        const debt = latest.sleep_need_debt_minutes;
        const debtColor = debt !== null && debt > 0 ? "text-red-700" : "";
        const consistency = latest.sleep_consistency_percentage;
        return (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-lg flex items-center gap-2">
                <Bed className="h-5 w-5 text-sleep" />
                Whoop Sleep Need
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
                <StatCard
                  title="Baseline need"
                  value={formatHoursMinutes(latest.sleep_need_baseline_minutes)}
                  icon={Moon}
                />
                <StatCard
                  title="Sleep debt"
                  value={formatHoursMinutes(debt)}
                  icon={Clock}
                  valueClass={debtColor}
                />
                <StatCard
                  title="Strain need"
                  value={formatHoursMinutes(latest.sleep_need_strain_minutes)}
                  icon={Activity}
                />
                <StatCard
                  title="Nap opportunity"
                  value={formatHoursMinutes(latest.sleep_need_nap_minutes)}
                  icon={Bed}
                />
                <StatCard
                  title="Sleep cycles"
                  value={
                    latest.sleep_cycle_count === null
                      ? "—"
                      : String(Math.round(latest.sleep_cycle_count))
                  }
                  icon={RotateCcw}
                />
                <StatCard
                  title="Disturbances"
                  value={
                    latest.disturbance_count === null
                      ? "—"
                      : String(Math.round(latest.disturbance_count))
                  }
                  icon={Hash}
                />
                <StatCard
                  title="No-data minutes"
                  value={formatMinutesUnit(latest.no_data_minutes)}
                  icon={Wind}
                />
                <StatCard
                  title="Consistency"
                  value={
                    consistency === null ? "—" : `${consistency.toFixed(0)}%`
                  }
                  icon={Sparkles}
                />
              </div>
            </CardContent>
          </Card>
        );
      })()}

      {/* Sleep Latency & Toss and Turn */}
      <div className="grid gap-6 md:grid-cols-2">
        <ChartErrorBoundary>
          <ChartCard
            title="Sleep Latency"
            icon={Clock}
            iconColorClass="text-sleep"
            iconBgClass="bg-sleep-muted"
          >
            <SleepLatencyChart data={eightSleepData} dateRange={dateRange} />
          </ChartCard>
        </ChartErrorBoundary>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <Hash className="h-5 w-5 text-stress" />
              Toss & Turn
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <MetricValue label="Current" value={tossCurrent} unit="times" />
              <MetricValue label="Average" value={tossMean} unit="times" />
              <MetricValue
                label="Respiratory Rate"
                value={respCurrent}
                unit="br/min"
              />
              <MetricValue
                label="Resp. Rate Avg"
                value={respMean}
                unit="br/min"
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ScoreCard({
  title,
  icon: Icon,
  baseline,
  series,
}: Readonly<{
  title: string;
  icon: React.ElementType;
  baseline?: {
    current_value: number | null;
    mean: number | null;
    z_score: number | null;
  };
  series?: { date: string; value: number | null }[];
}>) {
  const current = baseline?.current_value;
  const mean = baseline?.mean;
  const zScore = baseline?.z_score;

  return (
    <Card>
      <CardContent className="pt-4 pb-3">
        <div className="flex items-center gap-2 mb-2">
          <Icon className="h-4 w-4 text-sleep" />
          <span className="text-sm font-medium">{title}</span>
        </div>
        <p className="text-2xl font-bold">{formatScore(current)}</p>
        <div className="flex justify-between text-xs text-muted-foreground mt-1">
          <span>
            avg:{" "}
            {mean === null || mean === undefined
              ? "—"
              : String(Math.round(mean))}
          </span>
          {zScore !== null && zScore !== undefined && (
            <span className={zScoreColor(zScore)}>
              {`${(zScore >= 0 ? "+" : "") + zScore.toFixed(1)}σ`}
            </span>
          )}
        </div>
        {series && series.length > 0 && (
          <div className="flex gap-[2px] mt-2 h-8 items-end">
            {series.slice(-14).map((point) => {
              const v = point.value;
              if (v === null) return null;
              const height = Math.max(4, (v / 100) * 32);
              return (
                <div
                  key={point.date}
                  className="flex-1 rounded-sm bg-sleep/60"
                  style={{ height: `${String(height)}px` }}
                />
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
