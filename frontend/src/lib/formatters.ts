export interface ValueUnit {
  readonly value: string;
  readonly unit: string | undefined;
}

const UNIT_CHARS = new Set(
  "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ%/".split(""),
);

export function splitValueUnit(formatted: string): ValueUnit {
  if (formatted.length === 0) return { value: formatted, unit: undefined };
  let i = formatted.length;
  while (i > 0 && UNIT_CHARS.has(formatted[i - 1])) i--;
  if (i === formatted.length) return { value: formatted, unit: undefined };
  const unit = formatted.slice(i);
  const valueRaw = formatted.slice(0, i);
  const value = valueRaw.trimEnd();
  if (value.length === 0) return { value: formatted, unit: undefined };
  return { value, unit };
}

export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  if (hours > 0) {
    return `${String(hours)}h ${String(minutes)}m`;
  }
  if (minutes > 0) {
    return `${String(minutes)}m ${String(secs)}s`;
  }
  return `${String(secs)}s`;
}

export function formatPace(speedMps: number): string | null {
  if (speedMps <= 0) return null;
  const paceSecondsPerKm = 1000 / speedMps;
  const paceMinutes = Math.floor(paceSecondsPerKm / 60);
  const paceSeconds = Math.round(paceSecondsPerKm % 60);
  return `${String(paceMinutes)}:${String(paceSeconds).padStart(2, "0")} /km`;
}

export function formatPaceForReport(speedMps: number): string {
  const pace = formatPace(speedMps);
  return pace ?? "N/A";
}

export function shouldShowPace(
  speedMps: number | null,
  distanceMeters: number | null,
): boolean {
  if (speedMps === null || speedMps <= 0) return false;
  if (distanceMeters === null || distanceMeters <= 100) return false;
  return true;
}

export function formatVolume(kg: number): string {
  if (kg >= 1000) {
    return `${(kg / 1000).toFixed(1)}t`;
  }
  return `${String(Math.round(kg))}kg`;
}
