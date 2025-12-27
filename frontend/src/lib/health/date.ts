export function getLocalDateString(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function extractDatePart(dateStr: string): string {
  if (dateStr.includes("T")) {
    return dateStr.split("T")[0];
  }
  if (dateStr.includes(" ")) {
    return dateStr.split(" ")[0];
  }
  return dateStr;
}

export function getLocalToday(): Date {
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  return now;
}

export function normalizeDateTimeString(s: string): string {
  return s.includes(" ") && !s.includes("T") ? s.replace(" ", "T") : s;
}

export function toLocalDayKey(dateStr: string): string {
  const s = normalizeDateTimeString(dateStr);

  if (s.includes("T")) {
    const d = new Date(s);
    if (!Number.isNaN(d.getTime())) return getLocalDateString(d);
  }

  return extractDatePart(dateStr);
}

export function toLocalDayDate(dayKey: string): Date {
  const d = extractDatePart(dayKey);
  return new Date(`${d}T00:00:00`);
}

export function toTimeMs(dateStr: string): number {
  const s = normalizeDateTimeString(dateStr);

  if (s.includes("T")) {
    return new Date(s).getTime();
  }

  return toLocalDayDate(dateStr).getTime();
}

export function toDayNumber(dateStr: string): number {
  const d = toLocalDayDate(toLocalDayKey(dateStr));
  return Math.floor(d.getTime() / (1000 * 60 * 60 * 24));
}
