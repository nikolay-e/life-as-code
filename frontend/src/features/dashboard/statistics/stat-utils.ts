export function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.8) return "text-green-500";
  if (confidence >= 0.6) return "text-yellow-500";
  return "text-red-500";
}

export function getHrvRhrColor(value: number | null): string {
  if (value === null) return "text-muted-foreground";
  if (value > 1) return "text-red-500";
  if (value < -1) return "text-green-500";
  return "text-blue-500";
}

export function getHrvRhrLabel(value: number | null): string {
  if (value === null) return "Insufficient data";
  if (value > 1) return "Body under strain";
  if (value < -1) return "Well recovered";
  return "Balanced";
}

export function getSleepDebtColor(value: number): string {
  if (value > 120) return "text-red-500";
  if (value > 60) return "text-yellow-500";
  return "text-green-500";
}

export function getAcwrColor(value: number | null): string {
  if (value === null) return "text-muted-foreground";
  if (value > 1.5) return "text-red-500";
  if (value < 0.8) return "text-yellow-500";
  return "text-green-500";
}

export function getAcwrLabel(value: number | null): string {
  if (value === null) return "Insufficient strain data";
  if (value > 1.5) return "Injury risk - reduce load";
  if (value < 0.8) return "Detraining risk";
  return "Sweet spot";
}

export function getStepsChangeColor(value: number | null): string {
  if (value === null) return "text-muted-foreground";
  if (value < -1000) return "text-red-500";
  if (value > 1000) return "text-green-500";
  return "text-blue-500";
}

export function getWeightChangeColor(value: number | null): string {
  if (value === null) return "";
  if (value > 0.5) return "text-red-500";
  if (value < -0.5) return "text-green-500";
  return "text-blue-500";
}

export function getStressTrendColor(value: number | null): string {
  if (value === null) return "";
  if (value > 5) return "text-red-500";
  if (value < -5) return "text-green-500";
  return "text-blue-500";
}

export function getCorrelationColor(value: number | null): string {
  if (value === null) return "text-muted-foreground";
  if (value < -0.3) return "text-green-500";
  if (value > 0) return "text-red-500";
  return "text-muted-foreground";
}

export function getHrvSdColor(value: number | null): string {
  if (value === null) return "";
  if (value < 0.1) return "text-green-500";
  if (value > 0.15) return "text-red-500";
  return "";
}

export function getTsbColor(value: number | null): string {
  if (value === null) return "";
  if (value > 0) return "text-green-500";
  if (value < -10) return "text-red-500";
  return "";
}

export function getAllostaticScoreColor(value: number | null): string {
  if (value === null) return "text-yellow-500";
  if (value < 20) return "text-green-500";
  if (value > 40) return "text-red-500";
  return "text-yellow-500";
}

export function getCrossCorrelationColor(value: number | null): string {
  if (value === null) return "";
  if (value > 0.3) return "text-green-500";
  if (value < -0.3) return "text-red-500";
  return "";
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
