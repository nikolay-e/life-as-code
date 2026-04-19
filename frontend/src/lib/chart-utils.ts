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
  eightSleepValue?: number | null;
}

export function mergeProviderData<
  G extends { date: string },
  W extends { date: string },
  E extends { date: string } = { date: string },
>(
  garminData: G[],
  whoopData: W[],
  getGarminValue: (item: G) => number | null,
  getWhoopValue: (item: W) => number | null,
  eightSleepData?: E[],
  getEightSleepValue?: (item: E) => number | null,
): MultiProviderDataPoint[] {
  const garminMap = new Map(
    garminData.map((d) => [toLocalDayKey(d.date), getGarminValue(d)]),
  );
  const whoopMap = new Map(
    whoopData.map((d) => [toLocalDayKey(d.date), getWhoopValue(d)]),
  );
  const esMap =
    eightSleepData && getEightSleepValue
      ? new Map(
          eightSleepData.map((d) => [
            toLocalDayKey(d.date),
            getEightSleepValue(d),
          ]),
        )
      : new Map<string, number | null>();

  const allDates = new Set([
    ...garminMap.keys(),
    ...whoopMap.keys(),
    ...esMap.keys(),
  ]);
  const result: MultiProviderDataPoint[] = [];

  for (const date of allDates) {
    result.push({
      date,
      garminValue: garminMap.get(date) ?? null,
      whoopValue: whoopMap.get(date) ?? null,
      eightSleepValue: esMap.get(date) ?? null,
    });
  }

  return result.sort((a, b) => toTimeMs(a.date) - toTimeMs(b.date));
}

export function splitBySource<T extends { date: string; source?: string }>(
  data: T[],
  getValue: (item: T) => number | null,
): MultiProviderDataPoint[] {
  const garminMap = new Map<string, number | null>();
  const whoopMap = new Map<string, number | null>();
  const esMap = new Map<string, number | null>();

  for (const item of data) {
    const key = toLocalDayKey(item.date);
    const val = getValue(item);
    if (item.source === "whoop") whoopMap.set(key, val);
    else if (item.source === "eight_sleep") esMap.set(key, val);
    else garminMap.set(key, val);
  }

  const allDates = new Set([
    ...garminMap.keys(),
    ...whoopMap.keys(),
    ...esMap.keys(),
  ]);
  const result: MultiProviderDataPoint[] = [];

  for (const date of allDates) {
    result.push({
      date,
      garminValue: garminMap.get(date) ?? null,
      whoopValue: whoopMap.get(date) ?? null,
      eightSleepValue: esMap.get(date) ?? null,
    });
  }

  return result.sort((a, b) => toTimeMs(a.date) - toTimeMs(b.date));
}
