import type { CSSProperties } from "react";

export { TREND_CONFIGS, type TrendMethod } from "../../lib/metrics";

export const chartTooltipStyle: CSSProperties = {
  backgroundColor: "hsl(var(--card) / 0.85)",
  border: "1px solid hsl(var(--border) / 0.5)",
  borderRadius: "var(--radius)",
  padding: "6px 10px",
  fontSize: "11px",
  lineHeight: "1.3",
  boxShadow: "0 2px 8px -2px rgb(0 0 0 / 0.1)",
  backdropFilter: "blur(4px)",
};

export const SOURCE_COLORS = {
  garmin: "hsl(var(--garmin))",
  whoop: "hsl(var(--whoop))",
  googleFit: "hsl(var(--google-fit))",
  appleHealth: "hsl(var(--apple-health))",
} as const;

export const MULTI_PROVIDER_CONFIGS = {
  hrv: {
    garminColor: SOURCE_COLORS.garmin,
    whoopColor: SOURCE_COLORS.whoop,
  },
  sleep: {
    garminColor: SOURCE_COLORS.garmin,
    whoopColor: SOURCE_COLORS.whoop,
  },
  restingHr: {
    garminColor: SOURCE_COLORS.garmin,
    whoopColor: SOURCE_COLORS.whoop,
  },
  calories: {
    garminColor: SOURCE_COLORS.garmin,
    whoopColor: SOURCE_COLORS.whoop,
  },
} as const;
