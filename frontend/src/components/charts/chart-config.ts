import type { CSSProperties } from "react";
import { TREND_CONFIGS, type TrendMethod } from "../../lib/metrics";

export { TREND_CONFIGS, type TrendMethod };

export const chartTooltipStyle: CSSProperties = {
  backgroundColor: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: "var(--radius)",
  padding: "12px 16px",
  boxShadow:
    "0 4px 12px -2px rgb(0 0 0 / 0.08), 0 2px 6px -2px rgb(0 0 0 / 0.04)",
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
