import { config } from "dotenv";
import { spawn } from "node:child_process";
import { join } from "node:path";

config();

type Source = "google" | "apple" | "all";

interface ImportOptions {
  source: Source;
  userId: number;
  dryRun: boolean;
  extraArgs: string[];
}

function parseArgs(): ImportOptions {
  const args = process.argv.slice(2);

  let source: Source = "all";
  if (args.includes("--google") || args.includes("-g")) {
    source = "google";
  } else if (args.includes("--apple") || args.includes("-a")) {
    source = "apple";
  }

  const userArg = args.find((a) => a.startsWith("--user="));
  const userId = userArg ? Number.parseInt(userArg.split("=")[1], 10) : 1;

  const dryRun = args.includes("--dry-run");

  const extraArgs = args.filter(
    (a) => !["--google", "-g", "--apple", "-a", "--dry-run"].includes(a) && !a.startsWith("--user=")
  );

  return { source, userId, dryRun, extraArgs };
}

function runScript(scriptPath: string, args: string[]): Promise<number> {
  return new Promise((resolve) => {
    const proc = spawn("npx", ["tsx", scriptPath, ...args], {
      stdio: "inherit",
      cwd: process.cwd(),
      env: process.env,
    });

    proc.on("close", (code) => {
      resolve(code ?? 0);
    });
  });
}

async function main(): Promise<void> {
  const options = parseArgs();

  console.log("╔════════════════════════════════════════════╗");
  console.log("║   Health Data Import (Unified CLI)         ║");
  console.log("╠════════════════════════════════════════════╣");
  console.log(`║ Source:     ${options.source.padEnd(30)}║`);
  console.log(`║ User ID:    ${options.userId.toString().padEnd(30)}║`);
  console.log(`║ Dry Run:    ${options.dryRun.toString().padEnd(30)}║`);
  console.log("╚════════════════════════════════════════════╝");
  console.log("");

  const baseArgs = [`--user=${options.userId}`];
  if (options.dryRun) baseArgs.push("--dry-run");
  baseArgs.push(...options.extraArgs);

  let exitCode = 0;

  if (options.source === "google" || options.source === "all") {
    console.log("═══════════════════════════════════════════════");
    console.log("  Running Google Fit Import");
    console.log("═══════════════════════════════════════════════");
    console.log("");

    const googleScript = join(process.cwd(), "google", "import-google-fit.ts");
    const code = await runScript(googleScript, baseArgs);
    if (code !== 0) exitCode = code;
    console.log("");
  }

  if (options.source === "apple" || options.source === "all") {
    console.log("═══════════════════════════════════════════════");
    console.log("  Running Apple Health Import");
    console.log("═══════════════════════════════════════════════");
    console.log("");

    const appleScript = join(process.cwd(), "apple", "import-apple-health.ts");
    const code = await runScript(appleScript, baseArgs);
    if (code !== 0) exitCode = code;
    console.log("");
  }

  if (exitCode !== 0) {
    process.exit(exitCode);
  }

  console.log("╔════════════════════════════════════════════╗");
  console.log("║   All imports completed successfully!      ║");
  console.log("╚════════════════════════════════════════════╝");
}

await main();
