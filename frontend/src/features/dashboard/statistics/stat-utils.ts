type Comparator = "<" | ">";
type ColorRule = readonly [Comparator, number, string];

interface ColorConfig {
  readonly nullColor: string;
  readonly rules: readonly ColorRule[];
  readonly defaultColor: string;
}

function colorByThresholds(value: number | null, config: ColorConfig): string {
  if (value === null) return config.nullColor;
  for (const [op, threshold, color] of config.rules) {
    if (op === "<" ? value < threshold : value > threshold) return color;
  }
  return config.defaultColor;
}

const CONFIDENCE: ColorConfig = {
  nullColor: "",
  rules: [
    ["<", 0.6, "text-red-700"],
    ["<", 0.8, "text-yellow-700"],
  ],
  defaultColor: "text-green-700",
};

const HRV_RHR: ColorConfig = {
  nullColor: "text-muted-foreground",
  rules: [
    [">", 1, "text-red-700"],
    ["<", -1, "text-green-700"],
  ],
  defaultColor: "text-blue-500",
};

const SLEEP_DEBT: ColorConfig = {
  nullColor: "",
  rules: [
    [">", 120, "text-red-700"],
    [">", 60, "text-yellow-700"],
  ],
  defaultColor: "text-green-700",
};

const ACWR: ColorConfig = {
  nullColor: "text-muted-foreground",
  rules: [
    [">", 1.5, "text-red-700"],
    ["<", 0.8, "text-yellow-700"],
  ],
  defaultColor: "text-green-700",
};

const STEPS_CHANGE: ColorConfig = {
  nullColor: "text-muted-foreground",
  rules: [
    ["<", -1000, "text-red-700"],
    [">", 1000, "text-green-700"],
  ],
  defaultColor: "text-blue-500",
};

const WEIGHT_CHANGE: ColorConfig = {
  nullColor: "",
  rules: [
    [">", 0.5, "text-red-700"],
    ["<", -0.5, "text-green-700"],
  ],
  defaultColor: "text-blue-500",
};

const STRESS_TREND: ColorConfig = {
  nullColor: "",
  rules: [
    [">", 5, "text-red-700"],
    ["<", -5, "text-green-700"],
  ],
  defaultColor: "text-blue-500",
};

const CORRELATION: ColorConfig = {
  nullColor: "text-muted-foreground",
  rules: [
    ["<", -0.3, "text-green-700"],
    [">", 0, "text-red-700"],
  ],
  defaultColor: "text-muted-foreground",
};

const HRV_SD: ColorConfig = {
  nullColor: "",
  rules: [
    ["<", 0.1, "text-green-700"],
    [">", 0.15, "text-red-700"],
  ],
  defaultColor: "",
};

const TSB: ColorConfig = {
  nullColor: "",
  rules: [
    [">", 0, "text-green-700"],
    ["<", -10, "text-red-700"],
  ],
  defaultColor: "",
};

const ALLOSTATIC_SCORE: ColorConfig = {
  nullColor: "text-yellow-700",
  rules: [
    ["<", 20, "text-green-700"],
    [">", 40, "text-red-700"],
  ],
  defaultColor: "text-yellow-700",
};

const CROSS_CORRELATION: ColorConfig = {
  nullColor: "",
  rules: [
    [">", 0.3, "text-green-700"],
    ["<", -0.3, "text-red-700"],
  ],
  defaultColor: "",
};

export const getConfidenceColor = (value: number): string =>
  colorByThresholds(value, CONFIDENCE);

export const getHrvRhrColor = (value: number | null): string =>
  colorByThresholds(value, HRV_RHR);

export const getSleepDebtColor = (value: number): string =>
  colorByThresholds(value, SLEEP_DEBT);

export const getAcwrColor = (value: number | null): string =>
  colorByThresholds(value, ACWR);

export const getStepsChangeColor = (value: number | null): string =>
  colorByThresholds(value, STEPS_CHANGE);

export const getWeightChangeColor = (value: number | null): string =>
  colorByThresholds(value, WEIGHT_CHANGE);

export const getStressTrendColor = (value: number | null): string =>
  colorByThresholds(value, STRESS_TREND);

export const getCorrelationColor = (value: number | null): string =>
  colorByThresholds(value, CORRELATION);

export const getHrvSdColor = (value: number | null): string =>
  colorByThresholds(value, HRV_SD);

export const getTsbColor = (value: number | null): string =>
  colorByThresholds(value, TSB);

export const getAllostaticScoreColor = (value: number | null): string =>
  colorByThresholds(value, ALLOSTATIC_SCORE);

export const getCrossCorrelationColor = (value: number | null): string =>
  colorByThresholds(value, CROSS_CORRELATION);

export function getHrvRhrLabel(value: number | null): string {
  if (value === null) return "Insufficient data";
  if (value > 1) return "Body under strain";
  if (value < -1) return "Well recovered";
  return "Balanced";
}

export function getAcwrLabel(value: number | null): string {
  if (value === null) return "Insufficient strain data";
  if (value > 1.5) return "Injury risk - reduce load";
  if (value < 0.8) return "Detraining risk";
  return "Sweet spot";
}

export function signPrefix(value: number): string {
  return value > 0 ? "+" : "";
}

const METRIC_LABELS: Record<string, string> = {
  hrv: "HRV",
  rhr: "RHR",
  sleep: "Sleep",
  stress: "Stress",
  weight: "Weight",
  steps: "Steps",
  strain: "Strain",
  recovery: "Recovery",
  calories: "Calories",
  hrv_age: "HRV Age",
  fitness_age: "Fitness Age",
  rhr_age: "RHR Age",
  recovery_age: "Recovery Age",
};

export function formatMetricLabel(key: string): string {
  return (
    METRIC_LABELS[key] ??
    key.replaceAll("_", " ").replaceAll(/\b\w/g, (c) => c.toUpperCase())
  );
}

export function formatDaysLabel(days: number): string {
  if (days >= 365) {
    const years = Math.round(days / 365);
    return `${String(years)}Y`;
  } else if (days >= 30) {
    const months = Math.round(days / 30);
    return `${String(months)}M`;
  }
  return `${String(days)}d`;
}
