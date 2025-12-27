import {
  getLocalDateString,
  getLocalToday,
  toLocalDayKey,
  toLocalDayDate,
} from "./date";

export function filterDataByWindow<T extends { date: string }>(
  data: T[],
  windowDays: number,
): T[] {
  const today = getLocalToday();
  const windowStart = new Date(today);
  windowStart.setDate(windowStart.getDate() - (windowDays - 1));

  return data.filter((d) => {
    const dayKey = toLocalDayKey(d.date);
    const date = toLocalDayDate(dayKey);
    return date >= windowStart && date <= today;
  });
}

export function filterDataByWindowRange<T extends { date: string }>(
  data: T[],
  daysBack: number,
  daysBackEnd: number,
): T[] {
  const today = getLocalToday();
  const windowStart = new Date(today);
  windowStart.setDate(windowStart.getDate() - (daysBack - 1));
  const windowEnd = new Date(today);
  windowEnd.setDate(windowEnd.getDate() - daysBackEnd);

  return data.filter((d) => {
    const dayKey = toLocalDayKey(d.date);
    const date = toLocalDayDate(dayKey);
    return date >= windowStart && date < windowEnd;
  });
}

export function getDatesInWindow(windowDays: number): Set<string> {
  const today = getLocalToday();
  const windowStart = new Date(today);
  windowStart.setDate(windowStart.getDate() - (windowDays - 1));

  const dates = new Set<string>();
  for (let d = new Date(windowStart); d <= today; d.setDate(d.getDate() + 1)) {
    dates.add(getLocalDateString(d));
  }
  return dates;
}
