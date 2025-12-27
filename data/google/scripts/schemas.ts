import { z } from "zod";

// Sleep stage codes from Google Fit API
export const SleepStageCode = {
  AWAKE: 1,
  SLEEP: 2,
  OUT_OF_BED: 3,
  LIGHT: 4,
  DEEP: 5,
  REM: 6,
} as const;

// Base schemas
export const PositiveNumber = z.number().positive();
export const NonNegativeNumber = z.number().nonnegative();
export const Percentage = z.number().min(0).max(100);
export const HeartRate = z.number().int().min(20).max(250);
export const SpO2 = z.number().min(50).max(100);
export const Weight = z.number().min(20).max(500);

// Daily aggregated data from CSV
export const DailyAggregatedSchema = z.object({
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  totalSteps: NonNegativeNumber,
  totalDistance: NonNegativeNumber,
  totalCalories: NonNegativeNumber,
  avgHeartRate: HeartRate.nullable(),
  maxHeartRate: HeartRate.nullable(),
  minHeartRate: HeartRate.nullable(),
  avgWeight: Weight.nullable(),
  avgSpO2: SpO2.nullable(),
  minSpO2: SpO2.nullable(),
  activeMinutes: NonNegativeNumber,
});

export type DailyAggregated = z.infer<typeof DailyAggregatedSchema>;

// Sleep data schema
export const SleepDataSchema = z.object({
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  totalSleepMinutes: NonNegativeNumber,
  deepSleepMinutes: NonNegativeNumber,
  lightSleepMinutes: NonNegativeNumber,
  remSleepMinutes: NonNegativeNumber,
  awakeMinutes: NonNegativeNumber,
  sleepScore: z.number().int().min(0).max(100).nullable(),
  avgSpO2: SpO2.nullable(),
  minSpO2: SpO2.nullable(),
  respiratoryRate: z.number().min(5).max(50).nullable(),
});

export type SleepData = z.infer<typeof SleepDataSchema>;

// Body composition schema (from JSON)
export const BodyCompositionSchema = z.object({
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  bodyFatPct: Percentage.nullable(),
  weight: Weight.nullable(),
});

export type BodyComposition = z.infer<typeof BodyCompositionSchema>;

// Session activity schema (from All Sessions JSON)
export const SessionActivitySchema = z.object({
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  activityType: z.string(),
  startTime: z.string(),
  endTime: z.string(),
  durationSeconds: NonNegativeNumber,
  calories: NonNegativeNumber.nullable(),
  steps: z.number().int().nonnegative().nullable(),
  distance: NonNegativeNumber.nullable(),
  heartMinutes: NonNegativeNumber.nullable(),
  activeMinutes: z.number().int().nonnegative().nullable(),
});

export type SessionActivity = z.infer<typeof SessionActivitySchema>;

// Google Fit JSON data point schema
export const FitDataPointSchema = z.object({
  fitValue: z.array(z.object({
    value: z.object({
      intVal: z.number().optional(),
      fpVal: z.number().optional(),
    }).optional(),
  })),
  startTimeNanos: z.number(),
  endTimeNanos: z.number(),
  dataTypeName: z.string(),
  originDataSourceId: z.string().optional(),
  modifiedTimeMillis: z.number().optional(),
});

export type FitDataPoint = z.infer<typeof FitDataPointSchema>;

// Google Fit All Data JSON file schema
export const FitDataFileSchema = z.object({
  "Data Source": z.string(),
  "Data Points": z.array(FitDataPointSchema),
});

export type FitDataFile = z.infer<typeof FitDataFileSchema>;

// Google Fit Session JSON schema
export const FitSessionSchema = z.object({
  fitnessActivity: z.string(),
  startTime: z.string(),
  endTime: z.string(),
  duration: z.string(),
  segment: z.array(z.object({
    fitnessActivity: z.string(),
    startTime: z.string(),
    endTime: z.string(),
  })).optional(),
  aggregate: z.array(z.object({
    metricName: z.string(),
    floatValue: z.number().optional(),
    intValue: z.number().optional(),
  })).optional(),
});

export type FitSession = z.infer<typeof FitSessionSchema>;

// Import result schema
export const ImportResultSchema = z.object({
  source: z.string(),
  dataType: z.string(),
  processed: z.number().int().nonnegative(),
  inserted: z.number().int().nonnegative(),
  updated: z.number().int().nonnegative(),
  skipped: z.number().int().nonnegative(),
  errors: z.array(z.string()),
});

export type ImportResult = z.infer<typeof ImportResultSchema>;
