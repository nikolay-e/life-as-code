import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, basename } from "node:path";
import { parse } from "csv-parse/sync";
import {
  SleepStageCode,
  FitDataFile,
  FitSession,
  SleepData,
  BodyComposition,
  SessionActivity,
  DailyAggregated,
} from "../schemas";

// Nanoseconds to Date conversion
export function nanosToDate(nanos: number): Date {
  return new Date(nanos / 1_000_000);
}

export function nanosToDateString(nanos: number): string {
  const d = nanosToDate(nanos);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function durationNanosToMinutes(startNanos: number, endNanos: number): number {
  return (endNanos - startNanos) / 1_000_000_000 / 60;
}

const DURATION_RE = /^([\d.]+)s$/;

export function parseDurationString(duration: string): number {
  const match = DURATION_RE.exec(duration);
  return match ? Number.parseFloat(match[1]) : 0;
}

export function isoToDateString(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function safeParseFloat(value: string | undefined | null): number | null {
  if (!value || value.trim() === "") return null;
  const num = Number.parseFloat(value);
  return Number.isNaN(num) ? null : num;
}

interface DailyMetricsRow {
  "Start time": string;
  "End time": string;
  "Move Minutes count": string;
  "Calories (kcal)": string;
  "Distance (m)": string;
  "Average heart rate (bpm)": string;
  "Max heart rate (bpm)": string;
  "Min heart rate (bpm)": string;
  "Average oxygen saturation (%)": string;
  "Max oxygen saturation (%)": string;
  "Min oxygen saturation (%)": string;
  "Step count": string;
  "Average weight (kg)": string;
}

export function parseCSVFile(filePath: string): DailyMetricsRow[] {
  const content = readFileSync(filePath, "utf-8");
  return parse(content, {
    columns: true,
    skip_empty_lines: true,
    relax_column_count: true,
  }) as DailyMetricsRow[];
}

function accumulateHeartRateRow(
  row: DailyMetricsRow,
  readings: number[],
  maxHr: number | null,
  minHr: number | null
): { readings: number[]; maxHr: number | null; minHr: number | null } {
  const avg = safeParseFloat(row["Average heart rate (bpm)"]);
  if (avg !== null && avg > 20 && avg < 250) readings.push(avg);

  const max = safeParseFloat(row["Max heart rate (bpm)"]);
  if (max !== null && max > 20 && max < 250) {
    maxHr = maxHr === null ? max : Math.max(maxHr, max);
  }

  const min = safeParseFloat(row["Min heart rate (bpm)"]);
  if (min !== null && min > 20 && min < 250) {
    minHr = minHr === null ? min : Math.min(minHr, min);
  }

  return { readings, maxHr, minHr };
}

function accumulateSpo2Row(
  row: DailyMetricsRow,
  readings: number[],
  minSpO2: number | null
): { readings: number[]; minSpO2: number | null } {
  const spo2 = safeParseFloat(row["Average oxygen saturation (%)"]);
  if (spo2 !== null && spo2 >= 50 && spo2 <= 100) {
    readings.push(spo2);
    minSpO2 = minSpO2 === null ? spo2 : Math.min(minSpO2, spo2);
  }
  return { readings, minSpO2 };
}

export function aggregateDailyCSV(rows: DailyMetricsRow[], date: string): DailyAggregated {
  let heartRateReadings: number[] = [];
  const weightReadings: number[] = [];
  let spo2Readings: number[] = [];

  let totalSteps = 0;
  let totalDistance = 0;
  let totalCalories = 0;
  let maxHeartRate: number | null = null;
  let minHeartRate: number | null = null;
  let minSpO2: number | null = null;
  let activeMinutes = 0;

  for (const row of rows) {
    const steps = safeParseFloat(row["Step count"]);
    if (steps !== null) totalSteps += steps;

    const distance = safeParseFloat(row["Distance (m)"]);
    if (distance !== null) totalDistance += distance;

    const calories = safeParseFloat(row["Calories (kcal)"]);
    if (calories !== null) totalCalories += calories;

    const hrResult = accumulateHeartRateRow(row, heartRateReadings, maxHeartRate, minHeartRate);
    heartRateReadings = hrResult.readings;
    maxHeartRate = hrResult.maxHr;
    minHeartRate = hrResult.minHr;

    const weight = safeParseFloat(row["Average weight (kg)"]);
    if (weight !== null && weight > 20 && weight < 500) weightReadings.push(weight);

    const spo2Result = accumulateSpo2Row(row, spo2Readings, minSpO2);
    spo2Readings = spo2Result.readings;
    minSpO2 = spo2Result.minSpO2;

    const moveMinutes = safeParseFloat(row["Move Minutes count"]);
    if (moveMinutes !== null) activeMinutes += moveMinutes;
  }

  const avgHeartRate = heartRateReadings.length > 0
    ? Math.round(heartRateReadings.reduce((a, b) => a + b, 0) / heartRateReadings.length)
    : null;

  const avgWeight = weightReadings.length > 0
    ? weightReadings.reduce((a, b) => a + b, 0) / weightReadings.length
    : null;

  const avgSpO2 = spo2Readings.length > 0
    ? spo2Readings.reduce((a, b) => a + b, 0) / spo2Readings.length
    : null;

  return {
    date,
    totalSteps: Math.round(totalSteps),
    totalDistance: Math.round(totalDistance),
    totalCalories: Math.round(totalCalories),
    avgHeartRate,
    maxHeartRate,
    minHeartRate,
    avgWeight,
    avgSpO2,
    minSpO2,
    activeMinutes: Math.round(activeMinutes),
  };
}

export function loadFitDataFile(filePath: string): FitDataFile | null {
  try {
    const content = readFileSync(filePath, "utf-8");
    const data = JSON.parse(content);
    return {
      "Data Source": data["Data Source"] || "",
      "Data Points": data["Data Points"] || [],
    };
  } catch {
    return null;
  }
}

const STAGE_PRIORITY: Record<number, number> = {
  [SleepStageCode.DEEP]: 5,
  [SleepStageCode.REM]: 4,
  [SleepStageCode.LIGHT]: 3,
  [SleepStageCode.SLEEP]: 2,
  [SleepStageCode.AWAKE]: 1,
};

function nanosToMinuteTs(nanos: number): number {
  return Math.floor(nanos / 1_000_000 / 60_000);
}

function minuteTsToDateString(minuteTs: number): string {
  const d = new Date(minuteTs * 60_000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function buildSleepTimeline(dataDir: string): { timeline: Map<number, number>; sleepDates: Set<string> } {
  const files = readdirSync(dataDir).filter(f =>
    f.includes("sleep.segment") && f.endsWith(".json")
  );

  const timeline = new Map<number, number>();
  const sleepDates = new Set<string>();

  for (const file of files) {
    const fitData = loadFitDataFile(join(dataDir, file));
    if (!fitData) continue;

    for (const point of fitData["Data Points"]) {
      if (point.dataTypeName !== "com.google.sleep.segment") continue;

      const sleepType = point.fitValue?.[0]?.value?.intVal;
      if (sleepType === undefined || STAGE_PRIORITY[sleepType] === undefined) continue;
      if (point.endTimeNanos <= point.startTimeNanos) continue;

      const durationMinutes = durationNanosToMinutes(point.startTimeNanos, point.endTimeNanos);
      if (durationMinutes > 24 * 60) continue;

      const startMinute = nanosToMinuteTs(point.startTimeNanos);
      const endMinute = nanosToMinuteTs(point.endTimeNanos);

      for (let m = startMinute; m < endMinute; m++) {
        const existing = timeline.get(m);
        if (existing === undefined || STAGE_PRIORITY[sleepType] > STAGE_PRIORITY[existing]) {
          timeline.set(m, sleepType);
        }
      }

      sleepDates.add(nanosToDateString(point.endTimeNanos));
    }
  }

  return { timeline, sleepDates };
}

function loadSpo2ByDate(dataDir: string, sleepDates: Set<string>): Map<string, number[]> {
  const spo2ByDate = new Map<string, number[]>();
  const files = readdirSync(dataDir).filter(f =>
    f.includes("oxygen_saturation") && f.endsWith(".json")
  );

  for (const file of files) {
    const fitData = loadFitDataFile(join(dataDir, file));
    if (!fitData) continue;

    for (const point of fitData["Data Points"]) {
      const spo2 = point.fitValue?.[0]?.value?.fpVal;
      if (spo2 === undefined || spo2 < 50 || spo2 > 100) continue;

      const date = nanosToDateString(point.endTimeNanos);
      if (!sleepDates.has(date)) continue;

      if (!spo2ByDate.has(date)) spo2ByDate.set(date, []);
      spo2ByDate.get(date)!.push(spo2);
    }
  }

  return spo2ByDate;
}

function loadRespirationByDate(dataDir: string, sleepDates: Set<string>): Map<string, number[]> {
  const respirationByDate = new Map<string, number[]>();
  const files = readdirSync(dataDir).filter(f =>
    f.includes("respiratory_rate") && f.endsWith(".json")
  );

  for (const file of files) {
    const fitData = loadFitDataFile(join(dataDir, file));
    if (!fitData) continue;

    for (const point of fitData["Data Points"]) {
      const rate = point.fitValue?.[0]?.value?.fpVal;
      if (rate === undefined || rate < 5 || rate > 50) continue;

      const date = nanosToDateString(point.endTimeNanos);
      if (!sleepDates.has(date)) continue;

      if (!respirationByDate.has(date)) respirationByDate.set(date, []);
      respirationByDate.get(date)!.push(rate);
    }
  }

  return respirationByDate;
}

function aggregateTimelineByDate(
  timeline: Map<number, number>
): Map<string, { deep: number; light: number; rem: number; awake: number }> {
  const byDate = new Map<string, { deep: number; light: number; rem: number; awake: number }>();

  for (const [minuteTs, stage] of timeline) {
    const date = minuteTsToDateString(minuteTs);

    if (!byDate.has(date)) byDate.set(date, { deep: 0, light: 0, rem: 0, awake: 0 });

    const day = byDate.get(date)!;
    switch (stage) {
      case SleepStageCode.AWAKE:
        day.awake++;
        break;
      case SleepStageCode.DEEP:
        day.deep++;
        break;
      case SleepStageCode.REM:
        day.rem++;
        break;
      case SleepStageCode.LIGHT:
      case SleepStageCode.SLEEP:
        day.light++;
        break;
    }
  }

  return byDate;
}

function buildSleepRecord(
  date: string,
  counts: { deep: number; light: number; rem: number; awake: number },
  spo2Values: number[],
  respirationValues: number[]
): SleepData {
  const avgSpO2 = spo2Values.length > 0
    ? spo2Values.reduce((a, b) => a + b, 0) / spo2Values.length
    : null;

  const minSpO2 = spo2Values.length > 0
    ? spo2Values.reduce((a, b) => Math.min(a, b), Infinity)
    : null;

  const respiratoryRate = respirationValues.length > 0
    ? respirationValues.reduce((a, b) => a + b, 0) / respirationValues.length
    : null;

  return {
    date,
    totalSleepMinutes: counts.deep + counts.light + counts.rem,
    deepSleepMinutes: counts.deep,
    lightSleepMinutes: counts.light,
    remSleepMinutes: counts.rem,
    awakeMinutes: counts.awake,
    sleepScore: null,
    avgSpO2,
    minSpO2,
    respiratoryRate,
  };
}

export function parseSleepSegments(dataDir: string): Map<string, SleepData> {
  const { timeline, sleepDates } = buildSleepTimeline(dataDir);
  const spo2ByDate = loadSpo2ByDate(dataDir, sleepDates);
  const respirationByDate = loadRespirationByDate(dataDir, sleepDates);
  const byDate = aggregateTimelineByDate(timeline);

  const result = new Map<string, SleepData>();

  for (const [date, counts] of byDate) {
    const totalSleep = counts.deep + counts.light + counts.rem;
    if (totalSleep < 30) continue;

    result.set(date, buildSleepRecord(
      date,
      counts,
      spo2ByDate.get(date) ?? [],
      respirationByDate.get(date) ?? []
    ));
  }

  return result;
}

export function parseBodyComposition(dataDir: string): Map<string, BodyComposition> {
  const result = new Map<string, BodyComposition>();
  const bodyFatByDate = loadBodyFatByDate(dataDir);
  const weightByDate = loadWeightByDate(dataDir);

  const allDates = new Set([...bodyFatByDate.keys(), ...weightByDate.keys()]);

  for (const date of allDates) {
    const bodyFatValues = bodyFatByDate.get(date);
    const weightValues = weightByDate.get(date);

    const avgBodyFat = bodyFatValues && bodyFatValues.length > 0
      ? bodyFatValues.reduce((a, b) => a + b, 0) / bodyFatValues.length
      : null;

    const avgWeight = weightValues && weightValues.length > 0
      ? weightValues.reduce((a, b) => a + b, 0) / weightValues.length
      : null;

    if (avgBodyFat !== null || avgWeight !== null) {
      result.set(date, { date, bodyFatPct: avgBodyFat, weight: avgWeight });
    }
  }

  return result;
}

function loadBodyFatByDate(dataDir: string): Map<string, number[]> {
  const bodyFatByDate = new Map<string, number[]>();
  const files = readdirSync(dataDir).filter(f =>
    f.includes("body.fat.percentage") && f.endsWith(".json")
  );

  for (const file of files) {
    const fitData = loadFitDataFile(join(dataDir, file));
    if (!fitData) continue;

    for (const point of fitData["Data Points"]) {
      const bodyFat = point.fitValue?.[0]?.value?.fpVal;
      if (bodyFat === undefined || bodyFat < 1 || bodyFat > 70) continue;

      const date = nanosToDateString(point.endTimeNanos);
      if (!bodyFatByDate.has(date)) bodyFatByDate.set(date, []);
      bodyFatByDate.get(date)!.push(bodyFat);
    }
  }

  return bodyFatByDate;
}

function loadWeightByDate(dataDir: string): Map<string, number[]> {
  const weightByDate = new Map<string, number[]>();
  const files = readdirSync(dataDir).filter(f =>
    f.includes("weight") && !f.includes("body.fat") && f.endsWith(".json")
  );

  for (const file of files) {
    const fitData = loadFitDataFile(join(dataDir, file));
    if (!fitData) continue;

    for (const point of fitData["Data Points"]) {
      const weight = point.fitValue?.[0]?.value?.fpVal;
      if (weight === undefined || weight < 20 || weight > 500) continue;

      const date = nanosToDateString(point.endTimeNanos);
      if (!weightByDate.has(date)) weightByDate.set(date, []);
      weightByDate.get(date)!.push(weight);
    }
  }

  return weightByDate;
}

function extractSessionMetrics(
  session: FitSession
): { calories: number | null; steps: number | null; distance: number | null; heartMinutes: number | null; activeMinutes: number | null } {
  let calories: number | null = null;
  let steps: number | null = null;
  let distance: number | null = null;
  let heartMinutes: number | null = null;
  let activeMinutes: number | null = null;

  for (const agg of session.aggregate || []) {
    switch (agg.metricName) {
      case "com.google.calories.expended":
        calories = agg.floatValue ?? null;
        break;
      case "com.google.step_count.delta":
        steps = agg.intValue ?? null;
        break;
      case "com.google.distance.delta":
        distance = agg.floatValue ?? null;
        break;
      case "com.google.heart_minutes.summary":
        heartMinutes = agg.floatValue ?? null;
        break;
      case "com.google.active_minutes":
        activeMinutes = agg.intValue ?? null;
        break;
    }
  }

  return { calories, steps, distance, heartMinutes, activeMinutes };
}

export function parseSessionActivities(sessionsDir: string): SessionActivity[] {
  if (!existsSync(sessionsDir)) return [];

  const activities: SessionActivity[] = [];
  const files = readdirSync(sessionsDir).filter(f => f.endsWith(".json"));

  for (const file of files) {
    try {
      const content = readFileSync(join(sessionsDir, file), "utf-8");
      const session: FitSession = JSON.parse(content);

      if (session.fitnessActivity === "sleep") continue;

      const date = isoToDateString(session.endTime);
      const durationSeconds = parseDurationString(session.duration);
      const metrics = extractSessionMetrics(session);

      activities.push({
        date,
        activityType: session.fitnessActivity,
        startTime: session.startTime,
        endTime: session.endTime,
        durationSeconds,
        ...metrics,
      });
    } catch {
      // Skip malformed files
    }
  }

  return activities;
}

export function getCSVFilesWithDates(dirPath: string): { filePath: string; date: string }[] {
  if (!existsSync(dirPath)) return [];

  const files = readdirSync(dirPath).filter(f => f.endsWith(".csv"));
  const result: { filePath: string; date: string }[] = [];

  for (const file of files) {
    const match = basename(file).match(/^(\d{4}-\d{2}-\d{2})\.csv$/);
    if (match) {
      result.push({ filePath: join(dirPath, file), date: match[1] });
    }
  }

  return result;
}
