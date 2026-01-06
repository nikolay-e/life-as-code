import { config } from "dotenv";
import { join } from "path";
import { existsSync, mkdtempSync, rmSync } from "fs";
import { execSync } from "child_process";
import { tmpdir } from "os";
import pg from "pg";
import { parseAppleHealthExport, aggregateAppleHealthData } from "./parsers";
import {
  importDailyMetrics,
  importSleepData,
  importBodyComposition,
  createImportResult,
  withTransaction,
  ImportResult,
} from "../importers";

config({ path: join(process.cwd(), ".env") });

const { Pool } = pg;

interface ImportOptions {
  userId: number;
  dryRun: boolean;
  exportPath: string;
}

function parseArgs(): ImportOptions {
  const args = process.argv.slice(2);
  const exportPath = args.find((a) => !a.startsWith("--")) ?? "../apple/export.xml";

  return {
    userId: Number.parseInt(args.find((a) => a.startsWith("--user="))?.split("=")[1] ?? "1", 10),
    dryRun: args.includes("--dry-run"),
    exportPath,
  };
}

function printResult(result: ImportResult): void {
  console.log(`  ${result.dataType}:`);
  console.log(`    Processed: ${result.processed}`);
  console.log(`    Inserted: ${result.inserted}`);
  console.log(`    Updated: ${result.updated}`);
  console.log(`    Skipped: ${result.skipped}`);
  if (result.errors.length > 0) {
    console.log(`    Errors: ${result.errors.length}`);
    for (const err of result.errors.slice(0, 5)) {
      console.log(`      - ${err}`);
    }
    if (result.errors.length > 5) {
      console.log(`      ... and ${result.errors.length - 5} more`);
    }
  }
}

async function importHRVData(
  pool: pg.Pool,
  userId: number,
  hrvData: Map<string, number>,
  dryRun: boolean,
  source: string = "apple_health"
): Promise<ImportResult> {
  const result = createImportResult(source, "hrv");
  const entries = Array.from(hrvData.entries());

  if (dryRun) {
    for (const [date, hrv] of entries) {
      console.log(`[DRY-RUN] HRV: ${date} - ${hrv}ms`);
      result.processed++;
    }
    return result;
  }

  const batchSize = 100;
  for (let i = 0; i < entries.length; i += batchSize) {
    const batch = entries.slice(i, i + batchSize);

    await withTransaction(pool, async (client) => {
      for (const [date, hrv] of batch) {
        try {
          const query = `
            INSERT INTO hrv (user_id, date, source, hrv_avg, created_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (user_id, date, source) DO UPDATE SET
              hrv_avg = COALESCE(EXCLUDED.hrv_avg, hrv.hrv_avg)
            RETURNING (xmax = 0) AS inserted
          `;

          const res = await client.query(query, [userId, date, source, hrv]);

          if (res.rows[0]?.inserted) {
            result.inserted++;
          } else {
            result.updated++;
          }
          result.processed++;
        } catch (error) {
          result.errors.push(`HRV ${date}: ${(error as Error).message}`);
        }
      }
    });
  }

  return result;
}

async function importRHRData(
  pool: pg.Pool,
  userId: number,
  rhrData: Map<string, number>,
  dryRun: boolean,
  source: string = "apple_health"
): Promise<ImportResult> {
  const result = createImportResult(source, "rhr");
  const entries = Array.from(rhrData.entries());

  if (dryRun) {
    for (const [date, rhr] of entries) {
      console.log(`[DRY-RUN] RHR: ${date} - ${rhr}bpm`);
      result.processed++;
    }
    return result;
  }

  const batchSize = 100;
  for (let i = 0; i < entries.length; i += batchSize) {
    const batch = entries.slice(i, i + batchSize);

    await withTransaction(pool, async (client) => {
      for (const [date, rhr] of batch) {
        try {
          const query = `
            INSERT INTO heart_rate (user_id, date, source, resting_hr, created_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (user_id, date, source) DO UPDATE SET
              resting_hr = LEAST(COALESCE(heart_rate.resting_hr, EXCLUDED.resting_hr), EXCLUDED.resting_hr)
            RETURNING (xmax = 0) AS inserted
          `;

          const res = await client.query(query, [userId, date, source, rhr]);

          if (res.rows[0]?.inserted) {
            result.inserted++;
          } else {
            result.updated++;
          }
          result.processed++;
        } catch (error) {
          result.errors.push(`RHR ${date}: ${(error as Error).message}`);
        }
      }
    });
  }

  return result;
}

async function main(): Promise<void> {
  const options = parseArgs();

  console.log("╔════════════════════════════════════════════╗");
  console.log("║   Apple Health Data Import (v1.0)          ║");
  console.log("╠════════════════════════════════════════════╣");
  console.log(`║ User ID:    ${options.userId.toString().padEnd(30)}║`);
  console.log(`║ Dry Run:    ${options.dryRun.toString().padEnd(30)}║`);
  console.log(`║ Export:     ${options.exportPath.slice(0, 30).padEnd(30)}║`);
  console.log("╚════════════════════════════════════════════╝");
  console.log("");

  const databaseUrl = process.env.DATABASE_URL;
  if (!databaseUrl && !options.dryRun) {
    console.error("ERROR: DATABASE_URL environment variable is required");
    console.error("Example: DATABASE_URL=postgresql://user:pass@localhost:5432/life_as_code"); // pragma: allowlist secret
    process.exit(1);
  }

  const pool = options.dryRun
    ? (null as unknown as pg.Pool)
    : new Pool({ connectionString: databaseUrl });

  const baseDir = join(process.cwd(), "..", "apple");
  let xmlPath = join(baseDir, options.exportPath);

  if (!existsSync(xmlPath)) {
    xmlPath = options.exportPath;
  }

  if (!existsSync(xmlPath)) {
    console.error(`ERROR: Export file not found: ${xmlPath}`);
    process.exit(1);
  }

  let tempDir: string | null = null;
  let actualXmlPath = xmlPath;

  if (xmlPath.endsWith(".zip")) {
    console.log("═══ Extracting ZIP archive ═══");
    tempDir = mkdtempSync(join(tmpdir(), "apple-health-"));
    execSync(`unzip -o "${xmlPath}" -d "${tempDir}"`, { stdio: "inherit" });

    const extractedXml = join(tempDir, "apple_health_export", "export.xml");
    if (existsSync(extractedXml)) {
      actualXmlPath = extractedXml;
    } else {
      const altXml = join(tempDir, "export.xml");
      if (existsSync(altXml)) {
        actualXmlPath = altXml;
      } else {
        console.error("ERROR: Could not find export.xml in ZIP archive");
        if (tempDir) rmSync(tempDir, { recursive: true, force: true });
        process.exit(1);
      }
    }
    console.log(`  Extracted to: ${actualXmlPath}`);
    console.log("");
  }

  const results: ImportResult[] = [];

  try {
    console.log("═══ Parsing Apple Health Export ═══");
    const rawData = await parseAppleHealthExport(actualXmlPath);
    const aggregated = aggregateAppleHealthData(rawData);

    console.log(`  Daily records: ${aggregated.daily.length}`);
    console.log(`  Sleep records: ${aggregated.sleep.size}`);
    console.log(`  Body records: ${aggregated.body.size}`);
    console.log(`  HRV records: ${aggregated.hrv.size}`);
    console.log(`  RHR records: ${aggregated.rhr.size}`);
    console.log("");

    console.log("═══ Importing Daily Metrics ═══");
    const dailyResult = await importDailyMetrics(pool, options.userId, aggregated.daily, options.dryRun, "apple_health");
    results.push(dailyResult);
    printResult(dailyResult);
    console.log("");

    console.log("═══ Importing Sleep Data ═══");
    const sleepResult = await importSleepData(pool, options.userId, aggregated.sleep, options.dryRun, "apple_health");
    results.push(sleepResult);
    printResult(sleepResult);
    console.log("");

    console.log("═══ Importing Body Composition ═══");
    const bodyResult = await importBodyComposition(pool, options.userId, aggregated.body, options.dryRun, "apple_health");
    results.push(bodyResult);
    printResult(bodyResult);
    console.log("");

    console.log("═══ Importing HRV Data ═══");
    const hrvResult = await importHRVData(pool, options.userId, aggregated.hrv, options.dryRun, "apple_health");
    results.push(hrvResult);
    printResult(hrvResult);
    console.log("");

    console.log("═══ Importing RHR Data ═══");
    const rhrResult = await importRHRData(pool, options.userId, aggregated.rhr, options.dryRun, "apple_health");
    results.push(rhrResult);
    printResult(rhrResult);
    console.log("");

    console.log("╔════════════════════════════════════════════╗");
    console.log("║           Import Summary                   ║");
    console.log("╠════════════════════════════════════════════╣");

    let totalProcessed = 0;
    let totalInserted = 0;
    let totalUpdated = 0;
    let totalSkipped = 0;
    let totalErrors = 0;

    for (const r of results) {
      totalProcessed += r.processed;
      totalInserted += r.inserted;
      totalUpdated += r.updated;
      totalSkipped += r.skipped;
      totalErrors += r.errors.length;
    }

    console.log(`║ Total Processed: ${totalProcessed.toString().padEnd(24)}║`);
    console.log(`║ Total Inserted:  ${totalInserted.toString().padEnd(24)}║`);
    console.log(`║ Total Updated:   ${totalUpdated.toString().padEnd(24)}║`);
    console.log(`║ Total Skipped:   ${totalSkipped.toString().padEnd(24)}║`);
    console.log(`║ Total Errors:    ${totalErrors.toString().padEnd(24)}║`);
    console.log("╚════════════════════════════════════════════╝");

  } finally {
    if (pool) {
      await pool.end();
    }
    if (tempDir) {
      rmSync(tempDir, { recursive: true, force: true });
    }
  }
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
