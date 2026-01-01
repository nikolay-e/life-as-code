import pg from "pg";
import {
  DailyAggregated,
  SleepData,
  BodyComposition,
  SessionActivity,
  ImportResult,
} from "./schemas";

// Create empty import result
export function createImportResult(source: string, dataType: string): ImportResult {
  return {
    source,
    dataType,
    processed: 0,
    inserted: 0,
    updated: 0,
    skipped: 0,
    errors: [],
  };
}

// Transaction wrapper for batch operations
export async function withTransaction<T>(
  pool: pg.Pool,
  callback: (client: pg.PoolClient) => Promise<T>
): Promise<T> {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    const result = await callback(client);
    await client.query("COMMIT");
    return result;
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}

// Upsert steps data
export async function upsertSteps(
  client: pg.PoolClient,
  userId: number,
  data: DailyAggregated,
  result: ImportResult
): Promise<void> {
  // Skip only if all values are null/undefined (0 is valid data)
  if (
    (data.totalSteps === null || data.totalSteps === undefined || data.totalSteps === 0) &&
    (data.totalDistance === null || data.totalDistance === undefined || data.totalDistance === 0) &&
    (data.activeMinutes === null || data.activeMinutes === undefined || data.activeMinutes === 0)
  ) {
    result.skipped++;
    return;
  }

  try {
    const query = `
      INSERT INTO steps (user_id, date, total_steps, total_distance, active_minutes, created_at)
      VALUES ($1, $2, $3, $4, $5, NOW())
      ON CONFLICT (user_id, date) DO UPDATE SET
        total_steps = GREATEST(steps.total_steps, EXCLUDED.total_steps),
        total_distance = GREATEST(steps.total_distance, EXCLUDED.total_distance),
        active_minutes = GREATEST(steps.active_minutes, EXCLUDED.active_minutes)
      RETURNING (xmax = 0) AS inserted
    `;

    const res = await client.query(query, [
      userId,
      data.date,
      data.totalSteps,
      data.totalDistance,
      data.activeMinutes,
    ]);

    if (res.rows[0]?.inserted) {
      result.inserted++;
    } else {
      result.updated++;
    }
    result.processed++;
  } catch (error) {
    result.errors.push(`Steps ${data.date}: ${(error as Error).message}`);
  }
}

// Upsert heart rate data
export async function upsertHeartRate(
  client: pg.PoolClient,
  userId: number,
  data: DailyAggregated,
  result: ImportResult
): Promise<void> {
  if (data.avgHeartRate === null) {
    result.skipped++;
    return;
  }

  try {
    const restingHr = Math.round(data.minHeartRate ?? data.avgHeartRate);
    const maxHr = data.maxHeartRate ? Math.round(data.maxHeartRate) : null;
    const avgHr = Math.round(data.avgHeartRate);

    const query = `
      INSERT INTO heart_rate (user_id, date, resting_hr, max_hr, avg_hr, created_at)
      VALUES ($1, $2, $3, $4, $5, NOW())
      ON CONFLICT (user_id, date) DO UPDATE SET
        resting_hr = LEAST(COALESCE(heart_rate.resting_hr, EXCLUDED.resting_hr), EXCLUDED.resting_hr),
        max_hr = GREATEST(COALESCE(heart_rate.max_hr, EXCLUDED.max_hr), EXCLUDED.max_hr),
        avg_hr = COALESCE(EXCLUDED.avg_hr, heart_rate.avg_hr)
      RETURNING (xmax = 0) AS inserted
    `;

    const res = await client.query(query, [userId, data.date, restingHr, maxHr, avgHr]);

    if (res.rows[0]?.inserted) {
      result.inserted++;
    } else {
      result.updated++;
    }
    result.processed++;
  } catch (error) {
    result.errors.push(`HeartRate ${data.date}: ${(error as Error).message}`);
  }
}

// Upsert weight data (now includes body fat!)
export async function upsertWeight(
  client: pg.PoolClient,
  userId: number,
  date: string,
  weightKg: number | null,
  bodyFatPct: number | null,
  result: ImportResult
): Promise<void> {
  if (weightKg === null && bodyFatPct === null) {
    result.skipped++;
    return;
  }

  try {
    const query = `
      INSERT INTO weight (user_id, date, weight_kg, body_fat_pct, created_at)
      VALUES ($1, $2, $3, $4, NOW())
      ON CONFLICT (user_id, date) DO UPDATE SET
        weight_kg = COALESCE(EXCLUDED.weight_kg, weight.weight_kg),
        body_fat_pct = COALESCE(EXCLUDED.body_fat_pct, weight.body_fat_pct)
      RETURNING (xmax = 0) AS inserted
    `;

    const res = await client.query(query, [userId, date, weightKg, bodyFatPct]);

    if (res.rows[0]?.inserted) {
      result.inserted++;
    } else {
      result.updated++;
    }
    result.processed++;
  } catch (error) {
    result.errors.push(`Weight ${date}: ${(error as Error).message}`);
  }
}

// Upsert energy data
export async function upsertEnergy(
  client: pg.PoolClient,
  userId: number,
  data: DailyAggregated,
  result: ImportResult
): Promise<void> {
  // Always insert energy data - 0 calories is valid (rest day)
  // Only skip if there's truly no activity data at all for this day
  if (data.totalCalories === 0 && data.totalSteps === 0 && data.totalDistance === 0) {
    result.skipped++;
    return;
  }

  try {
    // Insert if no data exists, otherwise take the maximum value
    const query = `
      INSERT INTO energy (user_id, date, active_energy, created_at)
      VALUES ($1, $2, $3, NOW())
      ON CONFLICT (user_id, date) DO UPDATE SET
        active_energy = GREATEST(COALESCE(energy.active_energy, 0), EXCLUDED.active_energy)
      RETURNING (xmax = 0) AS inserted
    `;

    const res = await client.query(query, [userId, data.date, data.totalCalories]);

    if (res.rows[0]?.inserted) {
      result.inserted++;
    } else {
      result.updated++;
    }
    result.processed++;
  } catch (error) {
    result.errors.push(`Energy ${data.date}: ${(error as Error).message}`);
  }
}

// Upsert sleep data (NEW - includes SpO2 and respiratory rate!)
export async function upsertSleep(
  client: pg.PoolClient,
  userId: number,
  data: SleepData,
  result: ImportResult
): Promise<void> {
  if (data.totalSleepMinutes < 30) {
    result.skipped++;
    return;
  }

  try {
    const query = `
      INSERT INTO sleep (
        user_id, date,
        deep_minutes, light_minutes, rem_minutes, awake_minutes, total_sleep_minutes,
        sleep_score, spo2_avg, spo2_min, respiratory_rate,
        created_at
      )
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
      ON CONFLICT (user_id, date) DO UPDATE SET
        deep_minutes = COALESCE(EXCLUDED.deep_minutes, sleep.deep_minutes),
        light_minutes = COALESCE(EXCLUDED.light_minutes, sleep.light_minutes),
        rem_minutes = COALESCE(EXCLUDED.rem_minutes, sleep.rem_minutes),
        awake_minutes = COALESCE(EXCLUDED.awake_minutes, sleep.awake_minutes),
        total_sleep_minutes = GREATEST(COALESCE(sleep.total_sleep_minutes, 0), EXCLUDED.total_sleep_minutes),
        sleep_score = COALESCE(EXCLUDED.sleep_score, sleep.sleep_score),
        spo2_avg = COALESCE(EXCLUDED.spo2_avg, sleep.spo2_avg),
        spo2_min = LEAST(COALESCE(sleep.spo2_min, EXCLUDED.spo2_min), COALESCE(EXCLUDED.spo2_min, sleep.spo2_min)),
        respiratory_rate = COALESCE(EXCLUDED.respiratory_rate, sleep.respiratory_rate)
      RETURNING (xmax = 0) AS inserted
    `;

    const res = await client.query(query, [
      userId,
      data.date,
      data.deepSleepMinutes,
      data.lightSleepMinutes,
      data.remSleepMinutes,
      data.awakeMinutes,
      data.totalSleepMinutes,
      data.sleepScore,
      data.avgSpO2,
      data.minSpO2,
      data.respiratoryRate,
    ]);

    if (res.rows[0]?.inserted) {
      result.inserted++;
    } else {
      result.updated++;
    }
    result.processed++;
  } catch (error) {
    result.errors.push(`Sleep ${data.date}: ${(error as Error).message}`);
  }
}

// Aggregate session activities by date for daily summary import
export function aggregateSessionsByDate(
  activities: SessionActivity[]
): Map<string, { calories: number; steps: number; distance: number; activeMinutes: number }> {
  const byDate = new Map<string, { calories: number; steps: number; distance: number; activeMinutes: number }>();

  for (const activity of activities) {
    if (!byDate.has(activity.date)) {
      byDate.set(activity.date, { calories: 0, steps: 0, distance: 0, activeMinutes: 0 });
    }

    const daily = byDate.get(activity.date)!;
    if (activity.calories) daily.calories += activity.calories;
    if (activity.steps) daily.steps += activity.steps;
    if (activity.distance) daily.distance += activity.distance;
    if (activity.activeMinutes) daily.activeMinutes += activity.activeMinutes;
  }

  return byDate;
}

// Batch import CSV daily metrics
export async function importDailyMetrics(
  pool: pg.Pool,
  userId: number,
  dailyData: DailyAggregated[],
  dryRun: boolean
): Promise<ImportResult> {
  const result = createImportResult("google-fit", "daily-metrics");

  if (dryRun) {
    for (const data of dailyData) {
      console.log(`[DRY-RUN] Daily: ${data.date} - ${data.totalSteps} steps, ${data.totalCalories} kcal`);
      result.processed++;
    }
    return result;
  }

  // Process in batches of 100
  const batchSize = 100;
  for (let i = 0; i < dailyData.length; i += batchSize) {
    const batch = dailyData.slice(i, i + batchSize);

    await withTransaction(pool, async (client) => {
      for (const data of batch) {
        await upsertSteps(client, userId, data, result);
        await upsertHeartRate(client, userId, data, result);
        await upsertWeight(client, userId, data.date, data.avgWeight, null, result);
        await upsertEnergy(client, userId, data, result);
      }
    });

    if ((i + batchSize) % 500 === 0) {
      console.log(`  Processed ${Math.min(i + batchSize, dailyData.length)}/${dailyData.length} daily records...`);
    }
  }

  return result;
}

// Batch import sleep data
export async function importSleepData(
  pool: pg.Pool,
  userId: number,
  sleepData: Map<string, SleepData>,
  dryRun: boolean
): Promise<ImportResult> {
  const result = createImportResult("google-fit", "sleep");
  const sleepArray = Array.from(sleepData.values());

  if (dryRun) {
    for (const data of sleepArray) {
      console.log(`[DRY-RUN] Sleep: ${data.date} - ${data.totalSleepMinutes}min total, ${data.deepSleepMinutes}min deep`);
      result.processed++;
    }
    return result;
  }

  const batchSize = 100;
  for (let i = 0; i < sleepArray.length; i += batchSize) {
    const batch = sleepArray.slice(i, i + batchSize);

    await withTransaction(pool, async (client) => {
      for (const data of batch) {
        await upsertSleep(client, userId, data, result);
      }
    });
  }

  return result;
}

// Batch import body composition data
export async function importBodyComposition(
  pool: pg.Pool,
  userId: number,
  bodyData: Map<string, BodyComposition>,
  dryRun: boolean
): Promise<ImportResult> {
  const result = createImportResult("google-fit", "body-composition");
  const bodyArray = Array.from(bodyData.values());

  if (dryRun) {
    for (const data of bodyArray) {
      console.log(`[DRY-RUN] Body: ${data.date} - ${data.bodyFatPct?.toFixed(1)}% fat, ${data.weight?.toFixed(1)}kg`);
      result.processed++;
    }
    return result;
  }

  const batchSize = 100;
  for (let i = 0; i < bodyArray.length; i += batchSize) {
    const batch = bodyArray.slice(i, i + batchSize);

    await withTransaction(pool, async (client) => {
      for (const data of batch) {
        await upsertWeight(client, userId, data.date, data.weight, data.bodyFatPct, result);
      }
    });
  }

  return result;
}

// Import session activities as additional steps/energy data
export async function importSessionActivities(
  pool: pg.Pool,
  userId: number,
  activities: SessionActivity[],
  dryRun: boolean
): Promise<ImportResult> {
  const result = createImportResult("google-fit", "sessions");
  const aggregated = aggregateSessionsByDate(activities);

  if (dryRun) {
    for (const [date, data] of aggregated) {
      console.log(`[DRY-RUN] Sessions: ${date} - ${data.steps} steps, ${data.calories} kcal from sessions`);
      result.processed++;
    }
    return result;
  }

  const entries = Array.from(aggregated.entries());
  const batchSize = 100;

  for (let i = 0; i < entries.length; i += batchSize) {
    const batch = entries.slice(i, i + batchSize);

    await withTransaction(pool, async (client) => {
      for (const [date, data] of batch) {
        // Update steps if session has step data
        if (data.steps > 0 || data.distance > 0) {
          const dailyData: DailyAggregated = {
            date,
            totalSteps: data.steps,
            totalDistance: Math.round(data.distance),
            totalCalories: 0,
            avgHeartRate: null,
            maxHeartRate: null,
            minHeartRate: null,
            avgWeight: null,
            avgSpO2: null,
            minSpO2: null,
            activeMinutes: data.activeMinutes,
          };
          await upsertSteps(client, userId, dailyData, result);
        }

        // Update energy if session has calorie data
        if (data.calories > 0) {
          const dailyData: DailyAggregated = {
            date,
            totalSteps: 0,
            totalDistance: 0,
            totalCalories: Math.round(data.calories),
            avgHeartRate: null,
            maxHeartRate: null,
            minHeartRate: null,
            avgWeight: null,
            avgSpO2: null,
            minSpO2: null,
            activeMinutes: 0,
          };
          await upsertEnergy(client, userId, dailyData, result);
        }

        result.processed++;
      }
    });
  }

  return result;
}
