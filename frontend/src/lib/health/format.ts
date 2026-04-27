export function formatZScore(z: number | null): string {
  if (z === null) return "—";
  const sign = z >= 0 ? "+" : "";
  return `${sign}${z.toFixed(2)}σ`;
}

export function getZScoreColor(z: number | null): string {
  if (z === null) return "text-muted-foreground";
  if (z >= 1) return "text-green-700 dark:text-green-400";
  if (z >= 0.5) return "text-green-500 dark:text-green-500";
  if (z <= -1) return "text-red-700 dark:text-red-400";
  if (z <= -0.5) return "text-orange-500 dark:text-orange-400";
  return "text-blue-600 dark:text-blue-400";
}

export function getHealthScoreLabel(score: number | null): string {
  if (score === null) return "Insufficient data";
  if (score >= 1.5) return "Excellent";
  if (score >= 0.5) return "Good";
  if (score >= -0.5) return "Normal";
  if (score >= -1.5) return "Below Average";
  return "Poor";
}

export function getHealthScoreColor(score: number | null): string {
  if (score === null) return "text-muted-foreground";
  if (score >= 1.5) return "text-green-700 dark:text-green-400";
  if (score >= 0.5) return "text-green-500 dark:text-green-500";
  if (score >= -0.5) return "text-blue-600 dark:text-blue-400";
  if (score >= -1.5) return "text-orange-500 dark:text-orange-400";
  return "text-red-700 dark:text-red-400";
}
