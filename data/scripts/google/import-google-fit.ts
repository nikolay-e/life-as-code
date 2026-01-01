import { config } from "dotenv";
import { join } from "path";
import { existsSync } from "fs";
import pg from "pg";
import {
  parseCSVFile,
  aggregateDailyCSV,
  parseSleepSegments,
  parseBodyComposition,
  parseSessionActivities,
  getCSVFilesWithDates,
} from "./parsers";
import {
  importDailyMetrics,
  importSleepData,
  importBodyComposition,
  importSessionActivities,
  ImportResult,
} from "../importers";
import { DailyAggregated } from "../schemas";

config();

const { Pool } = pg;

interface ImportOptions {
  userId: number;
  dryRun: boolean;
  skipCsv: boolean;
  skipSleep: boolean;
  skipBodyComp: boolean;
  skipSessions: boolean;
}

function parseArgs(): ImportOptions {
  const args = process.argv.slice(2);
  return {
    userId: Number.parseInt(args.find((a) => !a.startsWith("--")) ?? "1", 10),
    dryRun: args.includes("--dry-run"),
    skipCsv: args.includes("--skip-csv"),
    skipSleep: args.includes("--skip-sleep"),
    skipBodyComp: args.includes("--skip-body"),
    skipSessions: args.includes("--skip-sessions"),
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

async function main(): Promise<void> {
  const options = parseArgs();

  console.log("╔════════════════════════════════════════════╗");
  console.log("║     Google Fit Data Import (v2.0)          ║");
  console.log("╠════════════════════════════════════════════╣");
  console.log(`║ User ID:    ${options.userId.toString().padEnd(30)}║`);
  console.log(`║ Dry Run:    ${options.dryRun.toString().padEnd(30)}║`);
  console.log(`║ Skip CSV:   ${options.skipCsv.toString().padEnd(30)}║`);
  console.log(`║ Skip Sleep: ${options.skipSleep.toString().padEnd(30)}║`);
  console.log(`║ Skip Body:  ${options.skipBodyComp.toString().padEnd(30)}║`);
  console.log(`║ Skip Sess:  ${options.skipSessions.toString().padEnd(30)}║`);
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

  const baseDir = join(process.cwd(), "..", "google");
  const takeoutDirs = [
    join(baseDir, "Takeout"),
    join(baseDir, "Takeout 2"),
  ].filter(existsSync);

  const results: ImportResult[] = [];

  try {
    // 1. Import Daily Metrics from CSV
    if (!options.skipCsv) {
      console.log("═══ Importing Daily Metrics (CSV) ═══");
      const allDailyData: DailyAggregated[] = [];

      for (const takeoutDir of takeoutDirs) {
        const csvDir = join(takeoutDir, "Fit", "Daily activity metrics");
        const csvFiles = getCSVFilesWithDates(csvDir);

        console.log(`  Found ${csvFiles.length} CSV files in ${csvDir}`);

        for (const { filePath, date } of csvFiles) {
          try {
            const rows = parseCSVFile(filePath);
            const aggregated = aggregateDailyCSV(rows, date);
            allDailyData.push(aggregated);
          } catch (error) {
            console.error(`  Error parsing ${filePath}: ${(error as Error).message}`);
          }
        }
      }

      console.log(`  Total daily records: ${allDailyData.length}`);
      const csvResult = await importDailyMetrics(pool, options.userId, allDailyData, options.dryRun);
      results.push(csvResult);
      printResult(csvResult);
      console.log("");
    }

    // 2. Import Sleep Data from JSON
    if (!options.skipSleep) {
      console.log("═══ Importing Sleep Data (JSON) ═══");

      for (const takeoutDir of takeoutDirs) {
        const allDataDir = join(takeoutDir, "Fit", "All Data");
        if (!existsSync(allDataDir)) continue;

        console.log(`  Parsing sleep segments from ${allDataDir}`);
        const sleepData = parseSleepSegments(allDataDir);
        console.log(`  Found ${sleepData.size} days with sleep data`);

        if (sleepData.size > 0) {
          const sleepResult = await importSleepData(pool, options.userId, sleepData, options.dryRun);
          results.push(sleepResult);
          printResult(sleepResult);
        }
      }
      console.log("");
    }

    // 3. Import Body Composition from JSON
    if (!options.skipBodyComp) {
      console.log("═══ Importing Body Composition (JSON) ═══");

      for (const takeoutDir of takeoutDirs) {
        const allDataDir = join(takeoutDir, "Fit", "All Data");
        if (!existsSync(allDataDir)) continue;

        console.log(`  Parsing body composition from ${allDataDir}`);
        const bodyData = parseBodyComposition(allDataDir);
        console.log(`  Found ${bodyData.size} days with body composition data`);

        if (bodyData.size > 0) {
          const bodyResult = await importBodyComposition(pool, options.userId, bodyData, options.dryRun);
          results.push(bodyResult);
          printResult(bodyResult);
        }
      }
      console.log("");
    }

    // 4. Import Session Activities from JSON
    if (!options.skipSessions) {
      console.log("═══ Importing Session Activities (JSON) ═══");

      for (const takeoutDir of takeoutDirs) {
        const sessionsDir = join(takeoutDir, "Fit", "All Sessions");
        if (!existsSync(sessionsDir)) continue;

        console.log(`  Parsing sessions from ${sessionsDir}`);
        const activities = parseSessionActivities(sessionsDir);
        console.log(`  Found ${activities.length} activity sessions`);

        // Count by type
        const byType = new Map<string, number>();
        for (const act of activities) {
          byType.set(act.activityType, (byType.get(act.activityType) || 0) + 1);
        }
        console.log("  Activity types:");
        for (const [type, count] of [...byType.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10)) {
          console.log(`    ${type}: ${count}`);
        }

        if (activities.length > 0) {
          const sessResult = await importSessionActivities(pool, options.userId, activities, options.dryRun);
          results.push(sessResult);
          printResult(sessResult);
        }
      }
      console.log("");
    }

    // Summary
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
  }
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
