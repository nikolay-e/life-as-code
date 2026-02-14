import { createReadStream } from "fs";
import { createGunzip } from "zlib";
import sax from "sax";
import { SleepData, BodyComposition, DailyAggregated } from "../schemas";

// Sleep stage type for timeline
type SleepStage = "deep" | "light" | "rem" | "awake" | null;

// Raw sleep record from Apple Health
interface SleepRecord {
  startTime: number; // Unix timestamp in minutes
  endTime: number;
  stage: SleepStage;
  source: string;
  priority: number;
}

// Source priority - higher number = higher priority
const SOURCE_PRIORITY: Record<string, number> = {
  "Nikolay's Apple Watch": 100,
  "Apple Watch": 90,
  "Eight Sleep": 80,
  "AutoSleep": 70,
  "Connect": 60,
  "WHOOP": 50,
  "Sleep Cycle": 40,
  "Nikolay's iPhone": 30,
  "iPhone": 20,
};

function getSourcePriority(source: string): number {
  for (const [key, priority] of Object.entries(SOURCE_PRIORITY)) {
    if (source.includes(key)) return priority;
  }
  return 10; // Default low priority for unknown sources
}

interface AppleHealthData {
  weight: Map<string, number[]>;
  steps: Map<string, Map<string, number>>;
  distance: Map<string, Map<string, number>>;
  activeEnergy: Map<string, Map<string, number>>;
  basalEnergy: Map<string, Map<string, number>>;
  hrv: Map<string, number[]>;
  rhr: Map<string, number[]>;
  sleepRecords: SleepRecord[];
}

const HK_TYPES = {
  BODY_MASS: "HKQuantityTypeIdentifierBodyMass",
  STEP_COUNT: "HKQuantityTypeIdentifierStepCount",
  DISTANCE: "HKQuantityTypeIdentifierDistanceWalkingRunning",
  ACTIVE_ENERGY: "HKQuantityTypeIdentifierActiveEnergyBurned",
  BASAL_ENERGY: "HKQuantityTypeIdentifierBasalEnergyBurned",
  HRV: "HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
  RESTING_HR: "HKQuantityTypeIdentifierRestingHeartRate",
  SLEEP: "HKCategoryTypeIdentifierSleepAnalysis",
} as const;

const SLEEP_VALUES = {
  DEEP: "HKCategoryValueSleepAnalysisAsleepDeep",
  CORE: "HKCategoryValueSleepAnalysisAsleepCore",
  REM: "HKCategoryValueSleepAnalysisAsleepREM",
  AWAKE: "HKCategoryValueSleepAnalysisAwake",
  UNSPECIFIED: "HKCategoryValueSleepAnalysisAsleepUnspecified",
  IN_BED: "HKCategoryValueSleepAnalysisInBed",
} as const;

function parseAppleDate(dateStr: string): Date | null {
  const match = dateStr.match(/^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) ([+-]\d{4})$/);
  if (!match) return null;

  const [, datePart, timePart, tzOffset] = match;
  const isoString = `${datePart}T${timePart}${tzOffset.slice(0, 3)}:${tzOffset.slice(3)}`;
  return new Date(isoString);
}

function getDateString(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function getSleepStage(value: string): SleepStage {
  switch (value) {
    case SLEEP_VALUES.DEEP:
      return "deep";
    case SLEEP_VALUES.CORE:
    case SLEEP_VALUES.UNSPECIFIED:
      return "light";
    case SLEEP_VALUES.REM:
      return "rem";
    case SLEEP_VALUES.AWAKE:
      return "awake";
    default:
      return null;
  }
}

export async function parseAppleHealthExport(xmlPath: string): Promise<AppleHealthData> {
  const data: AppleHealthData = {
    weight: new Map(),
    steps: new Map(),       // date -> source -> total
    distance: new Map(),    // date -> source -> total
    activeEnergy: new Map(),// date -> source -> total
    basalEnergy: new Map(), // date -> source -> total
    hrv: new Map(),
    rhr: new Map(),
    sleepRecords: [],
  };

  let recordCount = 0;

  return new Promise((resolve, reject) => {
    const parser = sax.createStream(true, {});

    parser.on("opentag", (node) => {
      if (node.name !== "Record") return;

      const type = node.attributes.type as string;
      const value = node.attributes.value as string;
      const startDateStr = node.attributes.startDate as string;
      const endDateStr = node.attributes.endDate as string;
      const unit = node.attributes.unit as string;
      const sourceName = node.attributes.sourceName as string;

      if (!type || !startDateStr) return;

      const startDate = parseAppleDate(startDateStr);
      const endDate = endDateStr ? parseAppleDate(endDateStr) : startDate;
      if (!startDate || !endDate) return;

      const dateKey = getDateString(endDate);
      recordCount++;

      if (recordCount % 500000 === 0) {
        console.log(`  Parsed ${recordCount.toLocaleString()} records...`);
      }

      switch (type) {
        case HK_TYPES.BODY_MASS: {
          let weightKg = Number.parseFloat(value);
          if (unit === "lb") weightKg *= 0.453592;
          if (weightKg > 20 && weightKg < 500) {
            if (!data.weight.has(dateKey)) data.weight.set(dateKey, []);
            data.weight.get(dateKey)!.push(weightKg);
          }
          break;
        }

        case HK_TYPES.STEP_COUNT: {
          const steps = Number.parseInt(value, 10);
          if (steps > 0) {
            const src = sourceName || "Unknown";
            if (!data.steps.has(dateKey)) data.steps.set(dateKey, new Map());
            const m = data.steps.get(dateKey)!;
            m.set(src, (m.get(src) || 0) + steps);
          }
          break;
        }

        case HK_TYPES.DISTANCE: {
          let meters = Number.parseFloat(value);
          if (unit === "km") meters *= 1000;
          else if (unit === "mi") meters *= 1609.34;
          if (meters > 0) {
            const src = sourceName || "Unknown";
            if (!data.distance.has(dateKey)) data.distance.set(dateKey, new Map());
            const m = data.distance.get(dateKey)!;
            m.set(src, (m.get(src) || 0) + meters);
          }
          break;
        }

        case HK_TYPES.ACTIVE_ENERGY: {
          let kcal = Number.parseFloat(value);
          if (unit === "kJ") kcal /= 4.184;
          if (kcal > 0) {
            const src = sourceName || "Unknown";
            if (!data.activeEnergy.has(dateKey)) data.activeEnergy.set(dateKey, new Map());
            const m = data.activeEnergy.get(dateKey)!;
            m.set(src, (m.get(src) || 0) + kcal);
          }
          break;
        }

        case HK_TYPES.BASAL_ENERGY: {
          let kcal = Number.parseFloat(value);
          if (unit === "kJ") kcal /= 4.184;
          if (kcal > 0) {
            const src = sourceName || "Unknown";
            if (!data.basalEnergy.has(dateKey)) data.basalEnergy.set(dateKey, new Map());
            const m = data.basalEnergy.get(dateKey)!;
            m.set(src, (m.get(src) || 0) + kcal);
          }
          break;
        }

        case HK_TYPES.HRV: {
          const hrvMs = Number.parseFloat(value);
          if (hrvMs > 0 && hrvMs < 300) {
            if (!data.hrv.has(dateKey)) data.hrv.set(dateKey, []);
            data.hrv.get(dateKey)!.push(hrvMs);
          }
          break;
        }

        case HK_TYPES.RESTING_HR: {
          const rhr = Number.parseFloat(value);
          if (rhr > 20 && rhr < 200) {
            if (!data.rhr.has(dateKey)) data.rhr.set(dateKey, []);
            data.rhr.get(dateKey)!.push(rhr);
          }
          break;
        }

        case HK_TYPES.SLEEP: {
          const stage = getSleepStage(value);
          if (stage === null) break; // Skip embed and unknown

          const startMinutes = Math.floor(startDate.getTime() / 60000);
          const endMinutes = Math.floor(endDate.getTime() / 60000);
          const duration = endMinutes - startMinutes;

          if (duration <= 0 || duration > 24 * 60) break;

          data.sleepRecords.push({
            startTime: startMinutes,
            endTime: endMinutes,
            stage,
            source: sourceName || "Unknown",
            priority: getSourcePriority(sourceName || ""),
          });
          break;
        }
      }
    });

    parser.on("error", (err) => {
      reject(err);
    });

    parser.on("end", () => {
      console.log(`  Total records parsed: ${recordCount.toLocaleString()}`);
      console.log(`  Sleep records: ${data.sleepRecords.length.toLocaleString()}`);
      resolve(data);
    });

    const stream = createReadStream(xmlPath);

    if (xmlPath.endsWith(".gz")) {
      stream.pipe(createGunzip()).pipe(parser);
    } else {
      stream.pipe(parser);
    }
  });
}

// Group sleep records into nights and deduplicate by timeline
function aggregateSleepData(
  sleepRecords: SleepRecord[]
): Map<string, { deep: number; light: number; rem: number; awake: number }> {
  if (sleepRecords.length === 0) return new Map();

  // Sort by start time
  const sorted = [...sleepRecords].sort((a, b) => a.startTime - b.startTime);

  // Create a timeline map: minute -> { stage, priority }
  const timeline = new Map<number, { stage: SleepStage; priority: number }>();

  for (const record of sorted) {
    for (let minute = record.startTime; minute < record.endTime; minute++) {
      const existing = timeline.get(minute);
      // Only update if this source has higher priority
      if (!existing || record.priority > existing.priority) {
        timeline.set(minute, { stage: record.stage, priority: record.priority });
      }
    }
  }

  // Group timeline by wake-up date (date when sleep ends)
  // Sleep that ends between 00:00 and 18:00 belongs to that date
  // Sleep that ends between 18:00 and 24:00 belongs to next date
  const byDate = new Map<string, { deep: number; light: number; rem: number; awake: number }>();

  for (const [minute, { stage }] of timeline) {
    if (stage === null) continue;

    const date = new Date(minute * 60000);
    const hour = date.getHours();

    // Determine which date this sleep belongs to
    let sleepDate: string;
    if (hour >= 18) {
      // Evening sleep - belongs to next day
      const nextDay = new Date(date);
      nextDay.setDate(nextDay.getDate() + 1);
      sleepDate = getDateString(nextDay);
    } else {
      sleepDate = getDateString(date);
    }

    if (!byDate.has(sleepDate)) {
      byDate.set(sleepDate, { deep: 0, light: 0, rem: 0, awake: 0 });
    }

    const day = byDate.get(sleepDate)!;
    day[stage]++;
  }

  return byDate;
}

function maxAcrossSources(sourceMap: Map<string, number> | undefined): number {
  if (!sourceMap || sourceMap.size === 0) return 0;
  let max = 0;
  for (const val of sourceMap.values()) {
    if (val > max) max = val;
  }
  return max;
}

export function aggregateAppleHealthData(data: AppleHealthData): {
  daily: DailyAggregated[];
  sleep: Map<string, SleepData>;
  body: Map<string, BodyComposition>;
  hrv: Map<string, number>;
  rhr: Map<string, number>;
} {
  const daily: DailyAggregated[] = [];
  const sleep = new Map<string, SleepData>();
  const body = new Map<string, BodyComposition>();
  const hrvByDate = new Map<string, number>();
  const rhrByDate = new Map<string, number>();

  const allDates = new Set([
    ...data.steps.keys(),
    ...data.distance.keys(),
    ...data.activeEnergy.keys(),
    ...data.weight.keys(),
  ]);

  for (const date of allDates) {
    const steps = maxAcrossSources(data.steps.get(date));
    const distance = maxAcrossSources(data.distance.get(date));
    const activeEnergy = maxAcrossSources(data.activeEnergy.get(date));
    const basalEnergy = maxAcrossSources(data.basalEnergy.get(date));
    const totalCalories = Math.round(activeEnergy + basalEnergy);

    const weightValues = data.weight.get(date);
    const avgWeight = weightValues && weightValues.length > 0
      ? weightValues.reduce((a, b) => a + b, 0) / weightValues.length
      : null;

    daily.push({
      date,
      totalSteps: steps,
      totalDistance: Math.round(distance),
      totalCalories,
      avgHeartRate: null,
      maxHeartRate: null,
      minHeartRate: null,
      avgWeight,
      avgSpO2: null,
      minSpO2: null,
      activeMinutes: 0,
    });

    if (avgWeight !== null) {
      body.set(date, { date, weight: avgWeight, bodyFatPct: null });
    }
  }

  // Aggregate sleep with deduplication
  const aggregatedSleep = aggregateSleepData(data.sleepRecords);

  for (const [date, sleepData] of aggregatedSleep) {
    const total = sleepData.deep + sleepData.light + sleepData.rem;
    if (total < 30) continue;

    sleep.set(date, {
      date,
      totalSleepMinutes: Math.round(total),
      deepSleepMinutes: Math.round(sleepData.deep),
      lightSleepMinutes: Math.round(sleepData.light),
      remSleepMinutes: Math.round(sleepData.rem),
      awakeMinutes: Math.round(sleepData.awake),
      sleepScore: null,
      avgSpO2: null,
      minSpO2: null,
      respiratoryRate: null,
    });
  }

  for (const [date, values] of data.hrv) {
    if (values.length > 0) {
      const avg = values.reduce((a, b) => a + b, 0) / values.length;
      hrvByDate.set(date, Math.round(avg));
    }
  }

  for (const [date, values] of data.rhr) {
    if (values.length > 0) {
      const min = values.reduce((a, b) => Math.min(a, b), Infinity);
      rhrByDate.set(date, Math.round(min));
    }
  }

  return { daily, sleep, body, hrv: hrvByDate, rhr: rhrByDate };
}
