import { createReadStream } from "fs";
import { createGunzip } from "zlib";
import sax from "sax";
import { SleepData, BodyComposition, DailyAggregated } from "../schemas";

interface AppleHealthData {
  weight: Map<string, number[]>;
  steps: Map<string, number>;
  distance: Map<string, number>;
  activeEnergy: Map<string, number>;
  basalEnergy: Map<string, number>;
  hrv: Map<string, number[]>;
  rhr: Map<string, number[]>;
  sleep: Map<string, { deep: number; light: number; rem: number; awake: number }>;
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
  return date.toISOString().split("T")[0];
}

function durationMinutes(startDate: Date, endDate: Date): number {
  return (endDate.getTime() - startDate.getTime()) / 1000 / 60;
}

export async function parseAppleHealthExport(xmlPath: string): Promise<AppleHealthData> {
  const data: AppleHealthData = {
    weight: new Map(),
    steps: new Map(),
    distance: new Map(),
    activeEnergy: new Map(),
    basalEnergy: new Map(),
    hrv: new Map(),
    rhr: new Map(),
    sleep: new Map(),
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
            data.steps.set(dateKey, (data.steps.get(dateKey) || 0) + steps);
          }
          break;
        }

        case HK_TYPES.DISTANCE: {
          let meters = Number.parseFloat(value);
          if (unit === "km") meters *= 1000;
          else if (unit === "mi") meters *= 1609.34;
          if (meters > 0) {
            data.distance.set(dateKey, (data.distance.get(dateKey) || 0) + meters);
          }
          break;
        }

        case HK_TYPES.ACTIVE_ENERGY: {
          let kcal = Number.parseFloat(value);
          if (unit === "kJ") kcal /= 4.184;
          if (kcal > 0) {
            data.activeEnergy.set(dateKey, (data.activeEnergy.get(dateKey) || 0) + kcal);
          }
          break;
        }

        case HK_TYPES.BASAL_ENERGY: {
          let kcal = Number.parseFloat(value);
          if (unit === "kJ") kcal /= 4.184;
          if (kcal > 0) {
            data.basalEnergy.set(dateKey, (data.basalEnergy.get(dateKey) || 0) + kcal);
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
          const sleepValue = value;
          const minutes = durationMinutes(startDate, endDate);

          if (minutes <= 0 || minutes > 24 * 60) break;
          if (sleepValue === SLEEP_VALUES.IN_BED) break;

          if (!data.sleep.has(dateKey)) {
            data.sleep.set(dateKey, { deep: 0, light: 0, rem: 0, awake: 0 });
          }

          const sleepDay = data.sleep.get(dateKey)!;

          switch (sleepValue) {
            case SLEEP_VALUES.DEEP:
              sleepDay.deep += minutes;
              break;
            case SLEEP_VALUES.CORE:
            case SLEEP_VALUES.UNSPECIFIED:
              sleepDay.light += minutes;
              break;
            case SLEEP_VALUES.REM:
              sleepDay.rem += minutes;
              break;
            case SLEEP_VALUES.AWAKE:
              sleepDay.awake += minutes;
              break;
          }
          break;
        }
      }
    });

    parser.on("error", (err) => {
      reject(err);
    });

    parser.on("end", () => {
      console.log(`  Total records parsed: ${recordCount.toLocaleString()}`);
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
    const steps = data.steps.get(date) || 0;
    const distance = data.distance.get(date) || 0;
    const activeEnergy = data.activeEnergy.get(date) || 0;
    const basalEnergy = data.basalEnergy.get(date) || 0;
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

  for (const [date, sleepData] of data.sleep) {
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
      const min = Math.min(...values);
      rhrByDate.set(date, Math.round(min));
    }
  }

  return { daily, sleep, body, hrv: hrvByDate, rhr: rhrByDate };
}
