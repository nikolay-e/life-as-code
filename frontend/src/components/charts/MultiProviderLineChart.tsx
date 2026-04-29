import { memo, useMemo } from "react";
import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
  Legend,
} from "recharts";
import { format } from "date-fns";
import { EmptyChartMessage } from "./shared";
import { chartTooltipStyle, SOURCE_COLORS } from "./chart-config";
import { renderTrendLines } from "./TrendLines";
import {
  dateToTimestamp,
  type MultiProviderDataPoint,
} from "../../lib/chart-utils";
import { loessSmooth } from "../../lib/statistics";
import {
  LOESS_BANDWIDTH_SHORT,
  LOESS_BANDWIDTH_LONG,
} from "../../lib/constants";
import { type ChartAnnotation, CATEGORY_COLOR } from "./annotations";

interface MultiProviderLineChartProps {
  readonly data: MultiProviderDataPoint[];
  readonly config: {
    garminColor: string;
    whoopColor: string;
    eightSleepColor?: string;
  };
  readonly emptyMessage: string;
  readonly garminLabel: string;
  readonly whoopLabel: string;
  readonly eightSleepLabel?: string;
  readonly unit: string;
  readonly height?: number | `${number}%`;
  readonly yDomain?: [number | string, number | string];
  readonly valueFormatter?: (value: number) => string;
  readonly baselineValue?: number | null;
  readonly showTrends?: boolean;
  readonly bandwidthShort?: number;
  readonly bandwidthLong?: number;
  readonly annotations?: readonly ChartAnnotation[];
  readonly baselineMean?: number | null;
  readonly baselineStd?: number | null;
  dateRange?: { start: string; end: string };
}

export const MultiProviderLineChart = memo(
  ({
    data,
    config,
    emptyMessage,
    garminLabel,
    whoopLabel,
    eightSleepLabel,
    unit,
    height = 250,
    yDomain = ["dataMin - 5", "dataMax + 5"],
    valueFormatter = (v) => v.toFixed(0),
    baselineValue,
    showTrends = false,
    bandwidthShort = LOESS_BANDWIDTH_SHORT,
    bandwidthLong = LOESS_BANDWIDTH_LONG,
    annotations,
    baselineMean,
    baselineStd,
    dateRange,
  }: MultiProviderLineChartProps) => {
    const hasEightSleep =
      eightSleepLabel && data.some((d) => d.eightSleepValue != null);
    const hasData = data.some(
      (d) =>
        d.garminValue !== null ||
        d.whoopValue !== null ||
        d.eightSleepValue != null,
    );

    const yMin = typeof yDomain[0] === "number" ? yDomain[0] : null;

    const chartData = useMemo(() => {
      const baseData = data.map((d) => ({
        ...d,
        timestamp: dateToTimestamp(d.date),
      }));

      if (!showTrends || baseData.length === 0) return baseData;

      const withAvg = baseData.map((d) => {
        const vals = [d.garminValue, d.whoopValue, d.eightSleepValue].filter(
          (v): v is number => v != null,
        );
        return {
          ...d,
          avgValue:
            vals.length > 0
              ? vals.reduce((a, b) => a + b, 0) / vals.length
              : null,
        };
      });

      const loessShort = loessSmooth(withAvg, "avgValue", bandwidthShort);
      const loessLong = loessSmooth(withAvg, "avgValue", bandwidthLong);

      const clamp = (v: number | null) =>
        v !== null && yMin !== null ? Math.max(yMin, v) : v;

      return withAvg.map((d, i) => ({
        ...d,
        trendShort: clamp(loessShort[i]?.loess ?? null),
        trendLong: clamp(loessLong[i]?.loess ?? null),
      }));
    }, [data, showTrends, bandwidthShort, bandwidthLong, yMin]);

    const xDomain = useMemo(() => {
      if (dateRange) {
        return [
          dateToTimestamp(dateRange.start),
          dateToTimestamp(dateRange.end),
        ];
      }
      return undefined;
    }, [dateRange]);

    const visibleAnnotations = useMemo(() => {
      if (!annotations?.length || !xDomain) return [];
      const [domainStart, domainEnd] = xDomain;
      return annotations
        .map((a) => ({
          ...a,
          startTs: dateToTimestamp(a.startDate),
          endTs: a.endDate ? dateToTimestamp(a.endDate) : null,
        }))
        .filter((a) => a.startTs >= domainStart && a.startTs <= domainEnd);
    }, [annotations, xDomain]);

    const zScoreBand1 = useMemo(() => {
      if (
        baselineMean == null ||
        baselineStd == null ||
        !Number.isFinite(baselineMean) ||
        !Number.isFinite(baselineStd) ||
        baselineStd <= 0
      ) {
        return null;
      }
      return {
        y1: baselineMean - baselineStd,
        y2: baselineMean + baselineStd,
      };
    }, [baselineMean, baselineStd]);

    if (!hasData) {
      return <EmptyChartMessage message={emptyMessage} />;
    }

    return (
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart
          data={chartData}
          barGap={0}
          barCategoryGap="20%"
          syncId="health-dashboard"
        >
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis
            dataKey="timestamp"
            tickFormatter={(value: number) => format(new Date(value), "MMM d")}
            className="text-xs"
            type="number"
            scale="time"
            domain={xDomain ?? ["dataMin", "dataMax"]}
          />
          <YAxis
            domain={yDomain}
            className="text-xs"
            allowDecimals={false}
            tickFormatter={(v: number) => Math.round(v).toString()}
          />
          <Tooltip
            labelFormatter={(value) =>
              format(new Date(value as number), "MMM d")
            }
            formatter={(value, name) => {
              if (name === "trendShort" || name === "trendLong") return null;
              const v = value as number | undefined;
              if (v === undefined) return ["-", name];
              if (name === "garminValue") {
                return [`${valueFormatter(v)}${unit}`, garminLabel];
              }
              if (name === "whoopValue") {
                return [`${valueFormatter(v)}${unit}`, whoopLabel];
              }
              if (name === "eightSleepValue" && eightSleepLabel) {
                return [`${valueFormatter(v)}${unit}`, eightSleepLabel];
              }
              return [v, name];
            }}
            contentStyle={chartTooltipStyle}
          />

          {zScoreBand1 && (
            <ReferenceArea
              y1={zScoreBand1.y1}
              y2={zScoreBand1.y2}
              fill="hsl(var(--success))"
              fillOpacity={0.06}
              ifOverflow="extendDomain"
            />
          )}

          <Bar
            dataKey="garminValue"
            fill={config.garminColor}
            radius={[4, 4, 0, 0]}
            name="garminValue"
          />
          <Bar
            dataKey="whoopValue"
            fill={config.whoopColor}
            radius={[4, 4, 0, 0]}
            name="whoopValue"
          />
          {hasEightSleep && (
            <Bar
              dataKey="eightSleepValue"
              fill={config.eightSleepColor ?? SOURCE_COLORS.eightSleep}
              radius={[4, 4, 0, 0]}
              name="eightSleepValue"
            />
          )}

          {renderTrendLines(showTrends)}

          {baselineValue !== null && baselineValue !== undefined && (
            <ReferenceLine
              y={baselineValue}
              stroke="hsl(var(--muted-foreground))"
              strokeDasharray="3 3"
              label={{
                value: `Baseline: ${valueFormatter(baselineValue)}`,
                position: "insideTopRight",
                fill: "hsl(var(--muted-foreground))",
                fontSize: 11,
              }}
            />
          )}

          {visibleAnnotations.map((a) => {
            const color = CATEGORY_COLOR[a.category];
            if (a.endTs && a.endTs > a.startTs) {
              return (
                <ReferenceArea
                  key={`ann-${String(a.id)}`}
                  x1={a.startTs}
                  x2={a.endTs}
                  fill={color}
                  fillOpacity={0.08}
                  stroke={color}
                  strokeOpacity={0.35}
                  strokeDasharray="2 2"
                  ifOverflow="extendDomain"
                />
              );
            }
            return (
              <ReferenceLine
                key={`ann-${String(a.id)}`}
                x={a.startTs}
                stroke={color}
                strokeOpacity={0.55}
                strokeDasharray="2 3"
                label={{
                  value: a.label,
                  position: "top",
                  fill: color,
                  fontSize: 10,
                }}
              />
            );
          })}

          {showTrends && (
            <Legend
              formatter={(value: string) => {
                if (value === "garminValue") {
                  return garminLabel;
                }
                if (value === "whoopValue") {
                  return whoopLabel;
                }
                if (value === "eightSleepValue") {
                  return eightSleepLabel ?? "Eight Sleep";
                }
                if (value === "trendShort") {
                  return "Short trend";
                }
                if (value === "trendLong") {
                  return "Long trend";
                }
                return value;
              }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    );
  },
);

MultiProviderLineChart.displayName = "MultiProviderLineChart";
