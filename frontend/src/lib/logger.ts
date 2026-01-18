type LogLevel = "debug" | "info" | "warn" | "error" | "silent";

interface LogContext {
  [key: string]: unknown;
}

interface Logger {
  debug(message: string, context?: LogContext): void;
  info(message: string, context?: LogContext): void;
  warn(message: string, context?: LogContext): void;
  error(message: string, error?: unknown, context?: LogContext): void;
}

const LOG_LEVEL_PRIORITY: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
  silent: 4,
};

const VALID_LOG_LEVELS: LogLevel[] = [
  "debug",
  "info",
  "warn",
  "error",
  "silent",
];

function isValidLogLevel(level: unknown): level is LogLevel {
  return (
    typeof level === "string" && VALID_LOG_LEVELS.includes(level as LogLevel)
  );
}

function detectEnvironment(): { isDev: boolean; logLevel: LogLevel } {
  const env = import.meta.env;
  const isDev = env.DEV === true || env.MODE === "development";
  const envLevel: unknown = env.VITE_LOG_LEVEL;
  if (isValidLogLevel(envLevel)) {
    return { isDev, logLevel: envLevel };
  }
  return { isDev, logLevel: isDev ? "debug" : "error" };
}

const environment = detectEnvironment();

function shouldLog(level: LogLevel): boolean {
  const configuredLevel = environment.logLevel;
  return LOG_LEVEL_PRIORITY[level] >= LOG_LEVEL_PRIORITY[configuredLevel];
}

function sanitizeValue(value: unknown): unknown {
  if (typeof value === "string") {
    return value
      .replace(/api_key=[^&\s]+/gi, "api_key=[REDACTED]")
      .replace(/token=[^&\s]+/gi, "token=[REDACTED]")
      .replace(/password=[^&\s]+/gi, "password=[REDACTED]")
      .replace(/Bearer\s+[^\s]+/gi, "Bearer [REDACTED]");
  }
  return value;
}

function sanitizeContext(context?: LogContext): LogContext | undefined {
  if (!context) return undefined;

  const sanitized: LogContext = {};
  for (const [key, value] of Object.entries(context)) {
    sanitized[key] = sanitizeValue(value);
  }
  return sanitized;
}

function formatMessage(namespace: string, message: string): string {
  return `[${namespace}] ${message}`;
}

function formatErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return sanitizeValue(error.message) as string;
  }
  if (typeof error === "string") {
    return sanitizeValue(error) as string;
  }
  return String(error);
}

export function createLogger(namespace: string): Logger {
  return {
    debug(message: string, context?: LogContext): void {
      if (shouldLog("debug")) {
        const formatted = formatMessage(namespace, message);
        if (context) {
          // eslint-disable-next-line no-console
          console.log(formatted, sanitizeContext(context));
        } else {
          // eslint-disable-next-line no-console
          console.log(formatted);
        }
      }
    },

    info(message: string, context?: LogContext): void {
      if (shouldLog("info")) {
        const formatted = formatMessage(namespace, message);
        if (context) {
          console.info(formatted, sanitizeContext(context));
        } else {
          console.info(formatted);
        }
      }
    },

    warn(message: string, context?: LogContext): void {
      if (shouldLog("warn")) {
        const formatted = formatMessage(namespace, message);
        if (context) {
          console.warn(formatted, sanitizeContext(context));
        } else {
          console.warn(formatted);
        }
      }
    },

    error(message: string, error?: unknown, context?: LogContext): void {
      if (shouldLog("error")) {
        const formatted = formatMessage(namespace, message);
        const errorMsg = error ? formatErrorMessage(error) : undefined;

        if (errorMsg && context) {
          console.error(formatted, errorMsg, sanitizeContext(context));
        } else if (errorMsg) {
          console.error(formatted, errorMsg);
        } else if (context) {
          console.error(formatted, sanitizeContext(context));
        } else {
          console.error(formatted);
        }
      }
    },
  };
}

export const log = {
  auth: createLogger("Auth"),
  api: createLogger("API"),
  sync: createLogger("Sync"),
  health: createLogger("Health"),
  dashboard: createLogger("Dashboard"),
};

export type { Logger, LogContext, LogLevel };
