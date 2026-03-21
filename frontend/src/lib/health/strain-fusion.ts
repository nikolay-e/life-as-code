import type { WhoopCycleData, GarminTrainingStatusData } from "../../types/api";
import { toLocalDayKey } from "./date";

export function fuseStrainValues(
  whoopCycles: WhoopCycleData[],
  garminTraining: GarminTrainingStatusData[],
): { date: string; value: number | null }[] {
  const whoopByDay = new Map(
    whoopCycles
      .filter((d) => d.strain !== null)
      .map((d) => [toLocalDayKey(d.date), d.strain as number]),
  );

  const garminRaw = garminTraining
    .filter((d) => d.acute_training_load !== null)
    .map((d) => ({
      date: toLocalDayKey(d.date),
      value: d.acute_training_load as number,
    }));

  const overlapping = garminRaw.filter((g) => whoopByDay.has(g.date));
  const garminByDay = new Map<string, number>();

  if (overlapping.length >= 14) {
    const sortedGarmin = overlapping.map((g) => g.value).sort((a, b) => a - b);
    const sortedWhoop = overlapping
      .map((g) => whoopByDay.get(g.date))
      .filter((v): v is number => v !== undefined)
      .sort((a, b) => a - b);

    const normalize = (val: number): number => {
      const below = sortedGarmin.filter((v) => v < val).length;
      const equal = sortedGarmin.filter((v) => v === val).length;
      const p = (below + equal * 0.5) / sortedGarmin.length;
      const idx = p * (sortedWhoop.length - 1);
      const lo = Math.floor(idx);
      const hi = Math.ceil(idx);
      return lo === hi
        ? sortedWhoop[lo]
        : sortedWhoop[lo] * (1 - (idx - lo)) + sortedWhoop[hi] * (idx - lo);
    };

    for (const g of garminRaw) {
      garminByDay.set(g.date, Math.max(0, Math.min(21, normalize(g.value))));
    }
  } else {
    for (const g of garminRaw) {
      garminByDay.set(g.date, g.value);
    }
  }

  const allDates = new Set([...whoopByDay.keys(), ...garminByDay.keys()]);
  return [...allDates]
    .map((date) => ({
      date,
      value: whoopByDay.get(date) ?? garminByDay.get(date) ?? null,
    }))
    .sort((a, b) => a.date.localeCompare(b.date));
}
