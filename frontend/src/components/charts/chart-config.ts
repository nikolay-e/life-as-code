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

export const MULTI_PROVIDER_CONFIGS = {
  hrv: {
    garminColor: "hsl(var(--hrv))",
    whoopColor: "hsl(var(--whoop))",
  },
  sleep: {
    garminColor: "hsl(var(--sleep))",
    whoopColor: "hsl(var(--whoop))",
  },
  restingHr: {
    garminColor: "hsl(var(--heart))",
    whoopColor: "hsl(var(--whoop))",
  },
  calories: {
    garminColor: "hsl(var(--calories))",
    whoopColor: "hsl(var(--whoop-strain))",
  },
} as const;
