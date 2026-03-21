import { parseISO, startOfDay } from "date-fns";

import { toLocalDayKey, toTimeMs } from "./health";

export function dateToTimestamp(dateStr: string): number {
  return startOfDay(parseISO(dateStr)).getTime();
}

export function sortByDateAsc<T extends { date: string }>(items: T[]): T[] {
  return [...items].sort((a, b) => toTimeMs(a.date) - toTimeMs(b.date));
}

export interface MultiProviderDataPoint {
  date: string;
  garminValue: number | null;
  whoopValue: number | null;
}

export function mergeProviderData<
  G extends { date: string },
  W extends { date: string },
>(
  garminData: G[],
  whoopData: W[],
  getGarminValue: (item: G) => number | null,
  getWhoopValue: (item: W) => number | null,
): MultiProviderDataPoint[] {
  const garminMap = new Map(
    garminData.map((d) => [toLocalDayKey(d.date), getGarminValue(d)]),
  );
  const whoopMap = new Map(
    whoopData.map((d) => [toLocalDayKey(d.date), getWhoopValue(d)]),
  );

  const allDates = new Set([...garminMap.keys(), ...whoopMap.keys()]);
  const result: MultiProviderDataPoint[] = [];

  for (const date of allDates) {
    result.push({
      date,
      garminValue: garminMap.get(date) ?? null,
      whoopValue: whoopMap.get(date) ?? null,
    });
  }

  return result.sort((a, b) => toTimeMs(a.date) - toTimeMs(b.date));
}
