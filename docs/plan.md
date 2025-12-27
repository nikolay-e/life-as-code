# Frontend React Improvement Plan

## Executive Summary

Анализ фронтенда выявил критические области для улучшения:

**Проблемы диаграмм:**

- **Нет трендовых линий** - только WeightChart имеет линейную регрессию
- **Отсутствуют moving averages** - для HRV, сна, стресса критически важны
- **Дублирование логики** - каждый чарт повторяет фильтрацию/сортировку
- **Негибкая архитектура** - нет единой конфигурации для переиспользования

**Рекомендации по трендам (на основе веб-исследования):**

- **EMA > SMA** для health-метрик (EMA чувствительнее к недавним изменениям)
- **7 дней** - короткосрочный тренд, **30 дней** - долгосрочный
- **Персональные baselines** вместо фиксированных порогов

---

## Phase 0: Trend Analysis & Moving Averages (NEW)

### 0.1 Create Statistical Utilities

**Создать:** `src/lib/statistics.ts`

```typescript
// Exponential Moving Average - рекомендуется для health-метрик
export function calculateEMA<T extends { date: string; value: number | null }>(
  data: T[],
  period: number,
  valueKey: keyof T = 'value' as keyof T
): (T & { ema: number | null })[] {
  const k = 2 / (period + 1);
  let ema: number | null = null;

  return data.map((point, index) => {
    const value = point[valueKey] as number | null;
    if (value === null) return { ...point, ema: null };

    if (ema === null) {
      ema = value; // первое значение = начальный EMA
    } else {
      ema = value * k + ema * (1 - k);
    }

    return { ...point, ema };
  });
}

// Simple Moving Average - для стабильных метрик (шаги, дистанция)
export function calculateSMA<T extends { date: string; value: number | null }>(
  data: T[],
  window: number,
  valueKey: keyof T = 'value' as keyof T
): (T & { sma: number | null })[] {
  return data.map((point, index) => {
    if (index < window - 1) return { ...point, sma: null };

    const values = data
      .slice(index - window + 1, index + 1)
      .map((d) => d[valueKey] as number | null)
      .filter((v): v is number => v !== null);

    if (values.length < window * 0.5) return { ...point, sma: null }; // >50% пропусков

    const sum = values.reduce((acc, val) => acc + val, 0);
    return { ...point, sma: sum / values.length };
  });
}

// Персональный baseline (rolling average за N дней)
export function calculateBaseline<T extends { date: string; value: number | null }>(
  data: T[],
  windowDays: number = 14,
  valueKey: keyof T = 'value' as keyof T
): { baseline: number; deviation: number } | null {
  const values = data
    .slice(-windowDays)
    .map((d) => d[valueKey] as number | null)
    .filter((v): v is number => v !== null);

  if (values.length < windowDays * 0.5) return null;

  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const variance = values.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0) / values.length;

  return { baseline: mean, deviation: Math.sqrt(variance) };
}
```

### 0.2 Create Trend Hook

**Создать:** `src/hooks/useTrendData.ts`

```typescript
import { useMemo } from "react";
import { calculateEMA, calculateSMA, calculateBaseline } from "@/lib/statistics";

type TrendMethod = "ema" | "sma";

interface TrendOptions {
  method?: TrendMethod;
  shortTermWindow?: number;  // default: 7 дней
  longTermWindow?: number;   // default: 30 дней
  showBaseline?: boolean;
}

export function useTrendData<T extends { date: string }>(
  data: T[],
  valueKey: keyof T,
  options: TrendOptions = {}
) {
  const {
    method = "ema",
    shortTermWindow = 7,
    longTermWindow = 30,
    showBaseline = false,
  } = options;

  return useMemo(() => {
    const sortedData = [...data].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    );

    const normalized = sortedData.map((d) => ({
      ...d,
      value: d[valueKey] as number | null,
    }));

    const calcFn = method === "ema" ? calculateEMA : calculateSMA;

    // Короткосрочный тренд
    const withShortTerm = calcFn(normalized, shortTermWindow);

    // Долгосрочный тренд
    const withLongTerm = calcFn(withShortTerm as any, longTermWindow).map((d) => ({
      ...d,
      shortTermTrend: (d as any).ema ?? (d as any).sma,
      longTermTrend: d.ema ?? d.sma,
    }));

    // Baseline
    const baseline = showBaseline ? calculateBaseline(normalized, 14) : null;

    return {
      chartData: withLongTerm,
      baseline,
      hasData: withLongTerm.some((d) => d.value !== null),
    };
  }, [data, valueKey, method, shortTermWindow, longTermWindow, showBaseline]);
}
```

### 0.3 Chart Configuration System

**Обновить:** `src/components/charts/chart-config.ts`

```typescript
import { CSSProperties } from "react";

export const chartTooltipStyle: CSSProperties = {
  backgroundColor: "hsl(var(--background))",
  border: "1px solid hsl(var(--border))",
  borderRadius: "var(--radius)",
};

// Конфигурация трендов для каждой метрики
export const TREND_CONFIGS = {
  hrv: {
    method: "ema" as const,
    shortTermWindow: 7,
    longTermWindow: 30,
    showBaseline: true,
    yAxisFormatter: (v: number) => `${v.toFixed(0)} ms`,
    color: "hsl(var(--primary))",
    trendColor: "hsl(var(--muted-foreground))",
  },
  sleep: {
    method: "ema" as const,
    shortTermWindow: 7,
    longTermWindow: 30,
    showBaseline: true,
    yAxisFormatter: (v: number) => `${v.toFixed(1)}h`,
    color: "#60a5fa",
    trendColor: "#93c5fd",
  },
  heartRate: {
    method: "ema" as const,
    shortTermWindow: 7,
    longTermWindow: 14,
    showBaseline: true,
    yAxisFormatter: (v: number) => `${v.toFixed(0)} bpm`,
    color: "#ef4444",
    trendColor: "#fca5a5",
  },
  stress: {
    method: "ema" as const,
    shortTermWindow: 5,
    longTermWindow: 14,
    showBaseline: false,
    yAxisFormatter: (v: number) => `${v.toFixed(0)}`,
    color: "#f59e0b",
    trendColor: "#fcd34d",
  },
  steps: {
    method: "sma" as const,  // SMA для кумулятивных метрик
    shortTermWindow: 7,
    longTermWindow: 30,
    showBaseline: false,
    yAxisFormatter: (v: number) => `${(v / 1000).toFixed(0)}k`,
    color: "#22c55e",
    trendColor: "#86efac",
  },
  weight: {
    method: "ema" as const,
    shortTermWindow: 7,
    longTermWindow: 30,
    showBaseline: true,
    yAxisFormatter: (v: number) => `${v.toFixed(1)} kg`,
    color: "hsl(var(--primary))",
    trendColor: "hsl(var(--muted-foreground))",
  },
} as const;

export type MetricType = keyof typeof TREND_CONFIGS;
```

### 0.4 Updated HRVChart with Trends

**Обновить:** `src/components/charts/HRVChart.tsx`

```typescript
import { memo, useMemo } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend
} from "recharts";
import { format, parseISO } from "date-fns";
import type { HRVData } from "../../types/api";
import { EmptyChartMessage } from "./shared";
import { chartTooltipStyle, TREND_CONFIGS } from "./chart-config";
import { useTrendData } from "../../hooks/useTrendData";

interface HRVChartProps {
  data: HRVData[];
  showTrends?: boolean;       // показать 7-day и 30-day тренды
  showBaseline?: boolean;     // показать персональный baseline
}

export const HRVChart = memo(function HRVChart({
  data,
  showTrends = false,
  showBaseline = false,
}: HRVChartProps) {
  const config = TREND_CONFIGS.hrv;

  const { chartData, baseline, hasData } = useTrendData(
    data.map((d) => ({ date: d.date, value: d.hrv_avg })),
    "value",
    {
      method: config.method,
      shortTermWindow: config.shortTermWindow,
      longTermWindow: config.longTermWindow,
      showBaseline,
    }
  );

  if (!hasData) {
    return <EmptyChartMessage message="No HRV data available" />;
  }

  return (
    <ResponsiveContainer width="100%" height={250}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="date"
          tickFormatter={(value) => format(parseISO(value), "MMM d")}
          stroke="hsl(var(--muted-foreground))"
          fontSize={12}
        />
        <YAxis
          tickFormatter={config.yAxisFormatter}
          stroke="hsl(var(--muted-foreground))"
          fontSize={12}
        />
        <Tooltip
          contentStyle={chartTooltipStyle}
          labelFormatter={(value) => format(parseISO(value as string), "PPP")}
        />

        {/* Raw data */}
        <Line
          type="monotone"
          dataKey="value"
          stroke={config.color}
          strokeWidth={1.5}
          dot={{ r: 2 }}
          name="HRV"
        />

        {/* 7-day trend */}
        {showTrends && (
          <Line
            type="monotone"
            dataKey="shortTermTrend"
            stroke={config.trendColor}
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={false}
            name="7-day trend"
          />
        )}

        {/* 30-day trend */}
        {showTrends && (
          <Line
            type="monotone"
            dataKey="longTermTrend"
            stroke={config.color}
            strokeWidth={2}
            strokeOpacity={0.5}
            dot={false}
            name="30-day trend"
          />
        )}

        {/* Baseline reference */}
        {showBaseline && baseline && (
          <ReferenceLine
            y={baseline.baseline}
            stroke="hsl(var(--muted-foreground))"
            strokeDasharray="3 3"
            label={{ value: `Baseline: ${baseline.baseline.toFixed(0)}ms`, position: "right" }}
          />
        )}

        {showTrends && <Legend />}
      </LineChart>
    </ResponsiveContainer>
  );
});
```

---

## Phase 1: Performance Critical (Charts)

### 1.1 Memoize Chart Components

**Проблема:** Все 7 чарт-компонентов пересчитывают данные на каждый рендер родителя.

**Файлы:**

- `src/components/charts/SleepChart.tsx`
- `src/components/charts/WeightChart.tsx`
- `src/components/charts/HRVChart.tsx`
- `src/components/charts/HeartRateChart.tsx`
- `src/components/charts/StressChart.tsx`
- `src/components/charts/StepsChart.tsx`
- `src/components/charts/WorkoutVolumeChart.tsx`

**Изменения:**

```typescript
// Before
export function SleepChart({ data, showBreakdown = false }: SleepChartProps) {
  const chartData = data
    .filter((d) => d.total_sleep_minutes !== null)
    .map(...)
    .sort(...);
  // ...
}

// After
import { memo, useMemo } from "react";

export const SleepChart = memo(function SleepChart({
  data,
  showBreakdown = false
}: SleepChartProps) {
  const chartData = useMemo(() =>
    data
      .filter((d) => d.total_sleep_minutes !== null)
      .map(...)
      .sort(...),
    [data]
  );
  // ...
});
```

**Приоритет:** CRITICAL - Recharts требует стабильных ссылок на data

### 1.2 Extract Shared Chart Utilities

**Создать:** `src/lib/chart-utils.ts`

```typescript
export function sortByDateAsc<T extends { date: string }>(items: T[]): T[] {
  return [...items].sort((a, b) =>
    new Date(a.date).getTime() - new Date(b.date).getTime()
  );
}

export function sortByDateDesc<T extends { date: string }>(items: T[]): T[] {
  return [...items].sort((a, b) =>
    new Date(b.date).getTime() - new Date(a.date).getTime()
  );
}

export function getLatestDate<T extends { date: string }>(items: T[]): string | null {
  if (!items.length) return null;
  return sortByDateDesc(items)[0].date;
}
```

---

## Phase 2: Code Splitting & Lazy Loading

### 2.1 Route-Based Code Splitting

**Файл:** `src/App.tsx`

```typescript
// Before
import { LoginPage } from "./features/auth/LoginPage";
import { DashboardLayout } from "./features/dashboard/DashboardLayout";
import { DashboardOverview } from "./features/dashboard/DashboardOverview";
import { TrendsPage } from "./features/dashboard/TrendsPage";
import { DataStatusPage } from "./features/dashboard/DataStatusPage";
import { SettingsPage } from "./pages/SettingsPage";

// After
import { lazy, Suspense } from "react";
import { Spinner } from "./components/ui/spinner";

const LoginPage = lazy(() => import("./features/auth/LoginPage").then(m => ({ default: m.LoginPage })));
const DashboardLayout = lazy(() => import("./features/dashboard/DashboardLayout").then(m => ({ default: m.DashboardLayout })));
const DashboardOverview = lazy(() => import("./features/dashboard/DashboardOverview").then(m => ({ default: m.DashboardOverview })));
const TrendsPage = lazy(() => import("./features/dashboard/TrendsPage").then(m => ({ default: m.TrendsPage })));
const DataStatusPage = lazy(() => import("./features/dashboard/DataStatusPage").then(m => ({ default: m.DataStatusPage })));
const SettingsPage = lazy(() => import("./pages/SettingsPage").then(m => ({ default: m.SettingsPage })));

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-screen">
      <Spinner size="lg" />
    </div>
  );
}

// Wrap routes with Suspense
<Suspense fallback={<PageLoader />}>
  <Routes>...</Routes>
</Suspense>
```

### 2.2 Vite Bundle Optimization

**Файл:** `vite.config.ts`

```typescript
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'charts-vendor': ['recharts'],
          'query-vendor': ['@tanstack/react-query'],
        },
      },
    },
  },
});
```

---

## Phase 3: Custom Hooks Refactoring

### 3.1 Create Query Key Factory

**Файл:** `src/lib/query-keys.ts`

```typescript
export const healthKeys = {
  all: ['health'] as const,
  data: () => [...healthKeys.all, 'data'] as const,
  dataRange: (start: string, end: string) => [...healthKeys.data(), start, end] as const,
  sync: () => [...healthKeys.all, 'sync'] as const,
  syncStatus: () => [...healthKeys.sync(), 'status'] as const,
};

export const settingsKeys = {
  all: ['settings'] as const,
  thresholds: () => [...settingsKeys.all, 'thresholds'] as const,
  credentials: () => [...settingsKeys.all, 'credentials'] as const,
};
```

### 3.2 Create Sync Mutation Factory

**Файл:** `src/hooks/useSyncMutation.ts`

```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { healthKeys } from "@/lib/query-keys";

type SyncProvider = "garmin" | "hevy" | "whoop";

export function useSyncMutation(provider: SyncProvider, syncFn: () => Promise<SyncResponse>) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: syncFn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: healthKeys.data() });
      queryClient.invalidateQueries({ queryKey: healthKeys.syncStatus() });
    },
  });
}
```

### 3.3 Update useSettings.ts

Использовать factory вместо дублирования:

```typescript
export function useSyncGarmin() {
  return useSyncMutation("garmin", api.sync.garmin);
}

export function useSyncHevy() {
  return useSyncMutation("hevy", api.sync.hevy);
}

export function useSyncWhoop() {
  return useSyncMutation("whoop", api.sync.whoop);
}
```

---

## Phase 4: Component Optimization

### 4.1 Extract Sub-Components from Large Pages

**DashboardOverview.tsx (175 lines):**

- Extract `StatCard` component
- Extract `LastSyncDisplay` component

**SettingsPage.tsx (204 lines):**

- Extract `SyncStatusGrid` component
- Move sync message logic to hook

**DataStatusPage.tsx (184 lines):**

- Extract `DataSourceRow` component

### 4.2 Add useCallback for Event Handlers

**SettingsPage.tsx:**

```typescript
// Before
const handleSync = async (provider, mutate) => { ... };

// After
const handleSync = useCallback(async (
  provider: "garmin" | "hevy" | "whoop",
  mutate: typeof syncGarmin,
) => {
  // ...
}, []);
```

---

## Phase 5: Constants & Configuration

### 5.1 Extract Magic Values

**Создать:** `src/lib/constants.ts`

```typescript
export const STEP_GOAL_DEFAULT = 10000;
export const SYNC_REFETCH_INTERVAL = 30_000;
export const HEALTH_DATA_STALE_TIME = 5 * 60 * 1000;
export const HEALTH_DATA_GC_TIME = 30 * 60 * 1000;
```

### 5.2 Update QueryClient Configuration

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: HEALTH_DATA_STALE_TIME,
      gcTime: HEALTH_DATA_GC_TIME,
    },
  },
});
```

---

## Implementation Order

| Phase | Priority | Impact | Effort |
|-------|----------|--------|--------|
| **0.1 Statistical Utilities** | CRITICAL | High | Medium |
| **0.2 Trend Hook** | CRITICAL | High | Medium |
| **0.3 Chart Config System** | CRITICAL | High | Low |
| **0.4 Update HRVChart** | CRITICAL | High | Medium |
| 1.1 Chart Memoization | HIGH | High | Low |
| 1.2 Chart Utilities | HIGH | Medium | Low |
| 2.1 Code Splitting | MEDIUM | High | Medium |
| 2.2 Bundle Optimization | MEDIUM | Medium | Low |
| 3.1 Query Keys | MEDIUM | Medium | Low |
| 3.2 Sync Factory | LOW | Medium | Low |
| 4.1 Component Extraction | LOW | Low | Medium |
| 4.2 useCallback | LOW | Low | Low |
| 5.1 Constants | LOW | Low | Low |

---

## Acceptance Criteria

### Phase 0: Trend Analysis (Priority 1)

- [ ] `src/lib/statistics.ts` created with EMA, SMA, baseline functions
- [ ] `src/hooks/useTrendData.ts` created with memoized trend calculations
- [ ] `chart-config.ts` updated with TREND_CONFIGS for all metrics
- [ ] HRVChart updated with `showTrends` and `showBaseline` props
- [ ] SleepChart updated with trend lines
- [ ] HeartRateChart updated with trend lines
- [ ] StressChart updated with trend lines
- [ ] StepsChart updated with trend lines
- [ ] WeightChart updated with trend lines (replace linear regression with EMA)

### Phase 1-5: React Optimizations

- [ ] All chart components wrapped in React.memo
- [ ] All chart data transformations use useMemo
- [ ] Route-based lazy loading implemented
- [ ] Bundle split into vendor chunks
- [ ] Query key factory in use
- [ ] No duplicate date sorting logic
- [ ] Constants extracted from components
- [ ] SettingsPage handleSync uses useCallback

---

## Research Summary

### EMA vs SMA for Health Metrics

| Metric | Recommended | Window (short) | Window (long) | Reason |
|--------|-------------|----------------|---------------|--------|
| HRV | EMA | 7 days | 30 days | Needs responsiveness to recent stress/recovery |
| Sleep | EMA | 7 days | 30 days | Captures sleep debt and recovery patterns |
| Heart Rate | EMA | 7 days | 14 days | Reflects fitness adaptations quickly |
| Stress | EMA | 5 days | 14 days | Volatile metric, needs smoothing |
| Steps | SMA | 7 days | 30 days | Cumulative metric, equal weighting |
| Weight | EMA | 7 days | 30 days | Removes water weight fluctuations |

### Visual Design for Trends

```text
Raw data:      ─────── (solid, thin, with dots)
7-day trend:   - - - - (dashed, medium)
30-day trend:  ─────── (solid, thick, lower opacity)
Baseline:      · · · · (dotted horizontal reference line)
```

### Sources

- Garmin Lifestyle Logging: 4-week and 12-week trend windows
- Whoop Recovery: 14-day rolling baseline for personalization
- Oura Ring: 7-day trend for readiness, 30-day for long-term
- Research: EMA with k=2/(period+1) for health metrics
- Best practice: Show both raw data and smoothed trend on same chart
