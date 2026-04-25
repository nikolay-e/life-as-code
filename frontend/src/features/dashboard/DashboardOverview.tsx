import { useMemo, useState } from "react";
import {
  useHealthDataRange,
  useSyncStatus,
  useAutoSync,
} from "../../hooks/useHealthData";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { LoadingState } from "../../components/ui/loading-state";
import { ErrorCard } from "../../components/ui/error-card";
import { HRVChart } from "../../components/charts/HRVChart";
import { SleepChart } from "../../components/charts/SleepChart";
import { WeightChart } from "../../components/charts/WeightChart";
import { HeartRateChart } from "../../components/charts/HeartRateChart";
import { StepsChart } from "../../components/charts/StepsChart";
import { RecoveryChart } from "../../components/charts/RecoveryChart";
import { TrainingLoadChart } from "../../components/charts/TrainingLoadChart";
import { CaloriesChart } from "../../components/charts/CaloriesChart";
import { ChartCard } from "../../components/charts/ChartCard";
import { ChartErrorBoundary } from "../../components/charts/ChartErrorBoundary";
import { format, subDays, differenceInDays, parseISO } from "date-fns";
import {
  Activity,
  RefreshCw,
  Heart,
  Zap,
  Moon,
  Scale,
  Footprints,
  Flame,
  Loader2,
} from "lucide-react";
import {
  METRIC_REGISTRY,
  TREND_MODES,
  MODE_ORDER,
  type ViewMode,
} from "../../lib/metrics";
import { DASHBOARD_METRIC_KEYS } from "../../lib/metrics/keys";
import { toTimeMs } from "../../lib/health";
import { getLatestSyncDate } from "../../lib/sync-utils";
import { useAnalytics } from "../../hooks/useAnalytics";
import { useToday } from "../../hooks/useToday";
import {
  LOESS_BANDWIDTH_SHORT,
  LOESS_BANDWIDTH_LONG,
} from "../../lib/constants";
import { Masthead } from "../../components/luxury/Masthead";
import { SectionHead, SerifEm } from "../../components/luxury/SectionHead";
import { Vital } from "../../components/luxury/Vital";
import { RingChart } from "../../components/luxury/RingChart";
import { splitValueUnit } from "../../lib/formatters";

const DASHBOARD_KEYS = new Set<string>(DASHBOARD_METRIC_KEYS);

function deriveRecovery(
  recoveryFromAnalytics: number | null | undefined,
  fallbackHrv: number | null | undefined,
  fallbackHrvBaseline: number | null | undefined,
): number {
  if (recoveryFromAnalytics != null && Number.isFinite(recoveryFromAnalytics)) {
    return Math.max(0, Math.min(100, Math.round(recoveryFromAnalytics)));
  }
  if (
    fallbackHrv != null &&
    fallbackHrvBaseline != null &&
    fallbackHrvBaseline > 0
  ) {
    const ratio = fallbackHrv / fallbackHrvBaseline;
    return Math.max(0, Math.min(100, Math.round(50 + (ratio - 1) * 100)));
  }
  return 0;
}

function recoveryVerdict(score: number): {
  headline: string;
  emphasis: string;
  subline: string;
} {
  if (score >= 80) {
    return {
      headline: "Recovered.",
      emphasis: "Train hard.",
      subline: "primed",
    };
  }
  if (score >= 65) {
    return {
      headline: "Steady.",
      emphasis: "Productive day.",
      subline: "ready",
    };
  }
  if (score >= 45) {
    return {
      headline: "Moderate.",
      emphasis: "Train light.",
      subline: "cautious",
    };
  }
  return { headline: "Depleted.", emphasis: "Recover today.", subline: "rest" };
}

function deltaSign(value: number): string {
  if (value > 0) return "+";
  if (value < 0) return "";
  return "±";
}

function deltaArrow(value: number): string {
  if (value > 0) return "↑";
  if (value < 0) return "↓";
  return "→";
}

function fmtDelta(value: number | null, unit = ""): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const digits = value >= 10 ? 0 : 1;
  return `${deltaArrow(value)} ${deltaSign(value)}${value.toFixed(digits)}${unit}`;
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

export function DashboardOverview() {
  const today = useToday();
  const [selectedRange, setSelectedRange] = useState<ViewMode>("recent");
  const [customStartDate, setCustomStartDate] = useState(
    format(subDays(today, 90), "yyyy-MM-dd"),
  );
  const [customEndDate, setCustomEndDate] = useState(
    format(today, "yyyy-MM-dd"),
  );

  const isToday = selectedRange === "today";
  const isCustom = selectedRange === "custom";
  const modeConfig =
    selectedRange !== "today" && selectedRange !== "custom"
      ? TREND_MODES[selectedRange]
      : null;
  const rangeDays = modeConfig?.rangeDays ?? 42;
  const bandwidthShort = modeConfig?.bandwidthShort ?? LOESS_BANDWIDTH_SHORT;
  const bandwidthLong = modeConfig?.bandwidthLong ?? LOESS_BANDWIDTH_LONG;

  const startDate = (() => {
    if (isCustom) return customStartDate;
    if (isToday) return format(today, "yyyy-MM-dd");
    return format(subDays(today, rangeDays), "yyyy-MM-dd");
  })();
  const endDate = (() => {
    if (isCustom) return customEndDate;
    if (isToday) return format(today, "yyyy-MM-dd");
    return format(subDays(today, 1), "yyyy-MM-dd");
  })();

  const selectedDays = Math.max(
    1,
    differenceInDays(parseISO(endDate), parseISO(startDate)) + 1,
  );

  const dateRange = useMemo(
    () => ({ start: startDate, end: endDate }),
    [startDate, endDate],
  );

  const { data, isLoading, isFetching, error } = useHealthDataRange(
    startDate,
    endDate,
  );
  const { data: syncStatus } = useSyncStatus();
  const { isSyncing } = useAutoSync();
  const { data: analyticsData } = useAnalytics("recent");

  const stepsFloor = useMemo(() => {
    const steps = data?.steps;
    if (!steps || steps.length === 0) return undefined;
    const window = Math.min(rangeDays, 90);
    const vals = steps
      .slice(-window)
      .map((s) => s.total_steps)
      .filter((v): v is number => v !== null);
    if (vals.length < 14) return undefined;
    const sorted = [...vals].sort((a, b) => a - b);
    const idx = Math.floor(sorted.length * 0.1);
    return Math.round(sorted[Math.min(idx, sorted.length - 1)]);
  }, [data, rangeDays]);

  // Hero recovery + verdict
  const recoveryBaseline = analyticsData?.metric_baselines.recovery;
  const hrvBaseline = analyticsData?.metric_baselines.hrv;
  const recovery = deriveRecovery(
    recoveryBaseline?.current_value,
    hrvBaseline?.current_value,
    hrvBaseline?.mean,
  );
  const verdict = recoveryVerdict(recovery);

  const hrvCurrent = hrvBaseline?.current_value;
  const hrvBaselineMean = hrvBaseline?.mean;
  const hrvDelta =
    hrvCurrent != null && hrvBaselineMean != null
      ? hrvCurrent - hrvBaselineMean
      : null;

  // Sparkline data (last ~30 datapoints from current range)
  const hrvSpark = useMemo(
    () =>
      (data?.hrv ?? [])
        .slice(-30)
        .map((p) => p.hrv_avg)
        .filter((v): v is number => v != null),
    [data],
  );
  const heartSpark = useMemo(
    () =>
      (data?.heart_rate ?? [])
        .slice(-30)
        .map((p) => p.resting_hr)
        .filter((v): v is number => v != null),
    [data],
  );
  const sleepSpark = useMemo(
    () =>
      (data?.sleep ?? [])
        .slice(-30)
        .map((p) => (p.total_sleep_minutes ?? 0) / 60)
        .filter((v) => v > 0),
    [data],
  );
  const stepsSpark = useMemo(
    () =>
      (data?.steps ?? [])
        .slice(-30)
        .map((p) => p.total_steps)
        .filter((v): v is number => v != null),
    [data],
  );

  if (isLoading) {
    return <LoadingState message="Loading health data..." />;
  }
  if (error) {
    return (
      <ErrorCard message={`Failed to load health data: ${error.message}`} />
    );
  }

  const lastSync = getLatestSyncDate(syncStatus);
  const todayDate = new Date();
  const dateLine = format(todayDate, "d LLLL yyyy");
  const weekday = format(todayDate, "EEEE");

  return (
    <div className="space-y-0">
      {/* ───────── Masthead ───────── */}
      <Masthead
        leftLine={`№ ${format(todayDate, "DDD")} · ${weekday}`}
        title={
          <>
            The <SerifEm>daily</SerifEm> readout
          </>
        }
        rightLine={dateLine}
      />

      {/* ───────── Hero ───────── */}
      <section className="grid grid-cols-1 lg:grid-cols-[1.1fr_0.9fr] gap-10 lg:gap-16 items-center py-14 lg:py-22 border-b border-border">
        <div>
          <span className="type-mono-eyebrow text-muted-foreground block mb-5">
            Today's verdict
          </span>
          <h1
            className="font-serif leading-[0.86] tracking-[-0.045em] text-[clamp(48px,9vw,116px)]"
            style={{
              fontVariationSettings: '"opsz" 144, "SOFT" 100',
              fontWeight: 350,
            }}
          >
            {verdict.headline}{" "}
            <span
              className="text-brass"
              style={{
                fontStyle: "italic",
                fontVariationSettings: '"opsz" 144, "SOFT" 100',
                fontWeight: 400,
              }}
            >
              {verdict.emphasis}
            </span>
          </h1>
          <p
            className="mt-7 font-serif text-[clamp(16px,1.5vw,19px)] leading-[1.55] text-muted-foreground max-w-[48ch]"
            style={{
              fontVariationSettings: '"opsz" 14, "SOFT" 30',
              fontWeight: 380,
            }}
          >
            {hrvCurrent != null && hrvBaselineMean != null ? (
              <>
                HRV closed at{" "}
                <strong className="text-foreground font-medium">
                  {Math.round(hrvCurrent)} ms
                </strong>
                {hrvDelta != null ? (
                  hrvDelta > 0 ? (
                    <>
                      {" "}
                      — above your baseline by{" "}
                      <strong className="text-foreground font-medium">
                        {Math.abs(hrvDelta).toFixed(1)} ms
                      </strong>
                      .
                    </>
                  ) : (
                    <>
                      {" "}
                      — below your baseline by{" "}
                      <strong className="text-foreground font-medium">
                        {Math.abs(hrvDelta).toFixed(1)} ms
                      </strong>
                      .
                    </>
                  )
                ) : (
                  "."
                )}{" "}
                Today's window leans toward{" "}
                {recovery >= 70
                  ? "productive load"
                  : recovery >= 50
                    ? "moderate work"
                    : "active recovery"}
                .
              </>
            ) : (
              <>
                Awaiting fresh signals. Connect a device in Settings to begin
                the daily briefing.
              </>
            )}
          </p>
          <div className="mt-7 flex items-center gap-2.5">
            <span className="type-mono-label text-muted-foreground">
              briefing
            </span>
            <span
              className="font-serif italic text-[17px]"
              style={{
                fontVariationSettings: '"opsz" 144, "SOFT" 100',
                fontWeight: 400,
              }}
            >
              drafted at {format(todayDate, "HH:mm")}
            </span>
          </div>
        </div>

        <RingChart
          value={recovery}
          label="recovery"
          subLabel={verdict.subline}
          notes={{
            tl: lastSync
              ? `last sync · ${format(new Date(toTimeMs(lastSync)), "HH:mm")}`
              : undefined,
            tr: `${String(recovery)}/100`,
            bl:
              hrvDelta != null
                ? `δ ${hrvDelta > 0 ? "+" : ""}${hrvDelta.toFixed(1)} hrv`
                : undefined,
            br: `${String(selectedDays)}d view`,
          }}
        />
      </section>

      {/* ───────── Range selector ───────── */}
      <section className="py-7">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-5 pb-4 border-b border-border">
          <span className="type-mono-eyebrow text-muted-foreground">
            window
          </span>
          <div className="flex flex-wrap gap-0">
            <Button
              variant={selectedRange === "today" ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setSelectedRange("today");
              }}
              className="-ml-px first:ml-0"
            >
              Today
            </Button>
            {MODE_ORDER.map((m) => {
              const cfg = TREND_MODES[m];
              return (
                <Button
                  key={m}
                  variant={selectedRange === m ? "default" : "outline"}
                  size="sm"
                  onClick={() => {
                    setSelectedRange(m);
                  }}
                  className="-ml-px"
                >
                  {cfg.label} · {cfg.description}
                </Button>
              );
            })}
            <Button
              variant={selectedRange === "custom" ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setSelectedRange("custom");
              }}
              className="-ml-px"
            >
              Custom
            </Button>
          </div>
        </div>
        {isCustom && (
          <div className="flex items-center gap-2 mt-4">
            <Input
              type="date"
              value={customStartDate}
              onChange={(e) => {
                setCustomStartDate(e.target.value);
              }}
              className="w-36"
            />
            <span className="text-muted-foreground">—</span>
            <Input
              type="date"
              value={customEndDate}
              onChange={(e) => {
                setCustomEndDate(e.target.value);
              }}
              className="w-36"
            />
            <span className="type-mono-label text-muted-foreground">
              ({selectedDays} days)
            </span>
          </div>
        )}
        <div className="mt-3 flex items-center gap-2 type-mono-label text-muted-foreground">
          {isSyncing ? (
            <>
              <RefreshCw className="h-3 w-3 animate-spin text-brass" />
              <span>syncing data…</span>
            </>
          ) : isFetching ? (
            <>
              <Loader2 className="h-3 w-3 animate-spin text-brass" />
              <span>fetching…</span>
            </>
          ) : lastSync ? (
            <span>
              last sync · {format(new Date(toTimeMs(lastSync)), "PPp")}
            </span>
          ) : null}
        </div>
      </section>

      {/* ───────── Vital signs ───────── */}
      <section className="pt-10">
        <SectionHead
          title={
            <>
              Vital <SerifEm>signs</SerifEm>
            </>
          }
          meta={
            <>
              {DASHBOARD_KEYS.size} metrics · last 24h
              <br />
              vs 12-week baseline
            </>
          }
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 divide-y divide-border sm:divide-y-0 sm:divide-x sm:[&>*:nth-child(3)]:border-l-0 sm:[&>*:nth-child(3)]:border-t lg:[&>*:nth-child(3)]:border-l lg:[&>*:nth-child(3)]:border-t-0">
          {METRIC_REGISTRY.filter((def) => DASHBOARD_KEYS.has(def.key))
            .slice(0, 4)
            .map((def) => {
              const baseline = analyticsData?.metric_baselines[def.key];
              const current = baseline?.current_value ?? null;
              const mean = baseline?.mean ?? null;
              const delta =
                current != null && mean != null ? current - mean : null;
              const goodDir =
                def.key === "rhr" || def.key === "stress" ? "down" : "up";
              const spark =
                def.key === "hrv"
                  ? hrvSpark
                  : def.key === "rhr"
                    ? heartSpark
                    : def.key === "sleep"
                      ? sleepSpark
                      : def.key === "steps"
                        ? stepsSpark
                        : [];
              const formatted = def.format(current);
              const { value: numStr, unit: unitStr } =
                splitValueUnit(formatted);
              return (
                <Vital
                  key={def.key}
                  name={def.title}
                  value={numStr}
                  unit={unitStr}
                  delta={fmtDelta(delta)}
                  deltaTone={deltaTone(delta, goodDir)}
                  spark={spark}
                />
              );
            })}
        </div>
      </section>

      {/* ───────── Charts grid ───────── */}
      <section className="pt-14 grid gap-6 lg:grid-cols-2">
        <ChartCard
          title="HRV"
          icon={Activity}
          iconColorClass="text-foreground"
          iconBgClass="border border-border"
        >
          <ChartErrorBoundary resetKeys={[startDate, endDate]}>
            <HRVChart
              data={data?.hrv ?? []}
              showTrends
              bandwidthShort={bandwidthShort}
              bandwidthLong={bandwidthLong}
              dateRange={dateRange}
            />
          </ChartErrorBoundary>
        </ChartCard>

        <ChartCard
          title="Sleep"
          icon={Moon}
          iconColorClass="text-foreground"
          iconBgClass="border border-border"
        >
          <ChartErrorBoundary resetKeys={[startDate, endDate]}>
            <SleepChart
              data={data?.sleep ?? []}
              showTrends
              bandwidthShort={bandwidthShort}
              bandwidthLong={bandwidthLong}
              dateRange={dateRange}
            />
          </ChartErrorBoundary>
        </ChartCard>

        <ChartCard
          title="Weight Trend"
          icon={Scale}
          iconColorClass="text-foreground"
          iconBgClass="border border-border"
        >
          <ChartErrorBoundary resetKeys={[startDate, endDate]}>
            <WeightChart
              data={data?.weight ?? []}
              showTrends
              bandwidthShort={bandwidthShort}
              bandwidthLong={bandwidthLong}
              dateRange={dateRange}
            />
          </ChartErrorBoundary>
        </ChartCard>

        <ChartCard
          title="Resting HR"
          icon={Heart}
          iconColorClass="text-foreground"
          iconBgClass="border border-border"
        >
          <ChartErrorBoundary resetKeys={[startDate, endDate]}>
            <HeartRateChart
              data={data?.heart_rate ?? []}
              showTrends
              bandwidthShort={bandwidthShort}
              bandwidthLong={bandwidthLong}
              dateRange={dateRange}
            />
          </ChartErrorBoundary>
        </ChartCard>

        <ChartCard
          title="Daily Steps"
          icon={Footprints}
          iconColorClass="text-foreground"
          iconBgClass="border border-border"
        >
          <ChartErrorBoundary resetKeys={[startDate, endDate]}>
            <StepsChart
              data={data?.steps ?? []}
              showTrends
              bandwidthShort={bandwidthShort}
              bandwidthLong={bandwidthLong}
              dateRange={dateRange}
              stepsFloor={stepsFloor}
            />
          </ChartErrorBoundary>
        </ChartCard>

        <ChartCard
          title="Recovery / Training Readiness"
          icon={Heart}
          iconColorClass="text-foreground"
          iconBgClass="border border-border"
        >
          <ChartErrorBoundary resetKeys={[startDate, endDate]}>
            <RecoveryChart
              whoopData={data?.whoop_recovery ?? []}
              garminData={data?.garmin_training_status ?? []}
              showTrends
              bandwidthShort={bandwidthShort}
              bandwidthLong={bandwidthLong}
              dateRange={dateRange}
            />
          </ChartErrorBoundary>
        </ChartCard>

        <ChartCard
          title="Training Load"
          icon={Zap}
          iconColorClass="text-foreground"
          iconBgClass="border border-border"
        >
          <ChartErrorBoundary resetKeys={[startDate, endDate]}>
            <TrainingLoadChart
              whoopData={data?.whoop_cycle ?? []}
              garminData={data?.garmin_training_status ?? []}
              dateRange={dateRange}
            />
          </ChartErrorBoundary>
        </ChartCard>

        <ChartCard
          title="Calories Burned"
          icon={Flame}
          iconColorClass="text-foreground"
          iconBgClass="border border-border"
        >
          <ChartErrorBoundary resetKeys={[startDate, endDate]}>
            <CaloriesChart
              garminData={data?.garmin_training_status ?? []}
              whoopData={data?.whoop_cycle ?? []}
              energyData={data?.energy ?? []}
              showTrends
              bandwidthShort={bandwidthShort}
              bandwidthLong={bandwidthLong}
              dateRange={dateRange}
            />
          </ChartErrorBoundary>
        </ChartCard>
      </section>
    </div>
  );
}
