import { describe, it, expect } from "vitest";
import { fuseStrainValues } from "@/lib/health/strain-fusion";
import type { WhoopCycleData, GarminTrainingStatusData } from "@/types/api";

function makeWhoopCycle(date: string, strain: number | null): WhoopCycleData {
  return {
    date,
    strain,
    kilojoules: null,
    avg_heart_rate: null,
    max_heart_rate: null,
  };
}

function makeGarminTraining(
  date: string,
  acuteTrainingLoad: number | null,
): GarminTrainingStatusData {
  return {
    date,
    vo2_max: null,
    vo2_max_precise: null,
    fitness_age: null,
    training_load_7_day: null,
    acute_training_load: acuteTrainingLoad,
    training_status: null,
    training_status_description: null,
    primary_training_effect: null,
    anaerobic_training_effect: null,
    endurance_score: null,
    training_readiness_score: null,
    total_kilocalories: null,
    active_kilocalories: null,
  };
}

function makeDateStr(dayOffset: number): string {
  const d = new Date(2025, 0, 1 + dayOffset);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${String(year)}-${month}-${day}`;
}

describe("fuseStrainValues", () => {
  it("returns empty array for no data", () => {
    const result = fuseStrainValues([], []);
    expect(result).toEqual([]);
  });

  it("returns empty array when all values are null", () => {
    const whoop = [makeWhoopCycle("2025-01-01", null)];
    const garmin = [makeGarminTraining("2025-01-01", null)];
    const result = fuseStrainValues(whoop, garmin);
    expect(result).toEqual([]);
  });

  it("returns whoop values when no garmin data", () => {
    const whoop = [
      makeWhoopCycle("2025-01-01", 12.5),
      makeWhoopCycle("2025-01-02", 8.3),
      makeWhoopCycle("2025-01-03", 15.1),
    ];
    const result = fuseStrainValues(whoop, []);
    expect(result).toHaveLength(3);
    expect(result[0]).toEqual({ date: "2025-01-01", value: 12.5 });
    expect(result[1]).toEqual({ date: "2025-01-02", value: 8.3 });
    expect(result[2]).toEqual({ date: "2025-01-03", value: 15.1 });
  });

  it("returns garmin values when no whoop data", () => {
    const garmin = [
      makeGarminTraining("2025-01-01", 150),
      makeGarminTraining("2025-01-02", 200),
    ];
    const result = fuseStrainValues([], garmin);
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ date: "2025-01-01", value: 150 });
    expect(result[1]).toEqual({ date: "2025-01-02", value: 200 });
  });

  it("prefers whoop values on overlapping dates", () => {
    const whoop = [makeWhoopCycle("2025-01-05", 10.0)];
    const garmin = [makeGarminTraining("2025-01-05", 300)];
    const result = fuseStrainValues(whoop, garmin);
    expect(result).toHaveLength(1);
    expect(result[0].value).toBe(10.0);
  });

  it("uses raw garmin values when insufficient overlap (< 14 days)", () => {
    const whoop = Array.from({ length: 10 }, (_, i) =>
      makeWhoopCycle(makeDateStr(i), 5 + i),
    );
    const garmin = Array.from({ length: 20 }, (_, i) =>
      makeGarminTraining(makeDateStr(i), 100 + i * 20),
    );
    const result = fuseStrainValues(whoop, garmin);

    const garminOnlyDate = makeDateStr(15);
    const garminOnlyPoint = result.find((r) => r.date === garminOnlyDate);
    expect(garminOnlyPoint).toBeDefined();
    expect(garminOnlyPoint!.value).toBe(100 + 15 * 20);
  });

  it("clamps normalized values to [0, 21]", () => {
    const whoop = Array.from({ length: 20 }, (_, i) =>
      makeWhoopCycle(makeDateStr(i), Math.min(21, 1 + i)),
    );
    const garmin = [
      ...Array.from({ length: 20 }, (_, i) =>
        makeGarminTraining(makeDateStr(i), 50 + i * 10),
      ),
      makeGarminTraining(makeDateStr(20), 999),
      makeGarminTraining(makeDateStr(21), 0),
    ];

    const result = fuseStrainValues(whoop, garmin);
    for (const point of result) {
      if (point.value !== null) {
        expect(point.value).toBeGreaterThanOrEqual(0);
        expect(point.value).toBeLessThanOrEqual(21);
      }
    }
  });

  it("normalizes garmin ATL to whoop scale with sufficient overlap", () => {
    const whoop = Array.from({ length: 20 }, (_, i) =>
      makeWhoopCycle(makeDateStr(i), 3 + i * 0.9),
    );
    const garmin = Array.from({ length: 30 }, (_, i) =>
      makeGarminTraining(makeDateStr(i), 50 + i * 15),
    );

    const result = fuseStrainValues(whoop, garmin);

    const garminOnlyDate = makeDateStr(25);
    const garminOnlyPoint = result.find((r) => r.date === garminOnlyDate);
    expect(garminOnlyPoint).toBeDefined();
    expect(garminOnlyPoint!.value).not.toBe(50 + 25 * 15);
    expect(garminOnlyPoint!.value).toBeGreaterThanOrEqual(0);
    expect(garminOnlyPoint!.value).toBeLessThanOrEqual(21);
  });

  it("returns results sorted by date", () => {
    const whoop = [
      makeWhoopCycle("2025-01-10", 12.0),
      makeWhoopCycle("2025-01-01", 8.0),
    ];
    const garmin = [makeGarminTraining("2025-01-05", 200)];
    const result = fuseStrainValues(whoop, garmin);
    for (let i = 1; i < result.length; i++) {
      expect(result[i].date >= result[i - 1].date).toBe(true);
    }
  });

  it("handles mixed null and valid data across sources", () => {
    const whoop = [
      makeWhoopCycle("2025-01-01", null),
      makeWhoopCycle("2025-01-02", 10.0),
    ];
    const garmin = [
      makeGarminTraining("2025-01-01", 200),
      makeGarminTraining("2025-01-03", null),
    ];
    const result = fuseStrainValues(whoop, garmin);
    expect(result).toHaveLength(2);
    const dates = result.map((r) => r.date);
    expect(dates).toContain("2025-01-01");
    expect(dates).toContain("2025-01-02");
  });
});
