export interface UserFriendlyError {
  title: string;
  message: string;
  suggestions: string[];
  action?: string;
}

type ErrorMatcher = (errorMessage: string) => boolean;

interface ErrorMapping {
  matcher: ErrorMatcher;
  getError: (errorMessage: string) => UserFriendlyError;
}

const errorMappings: ErrorMapping[] = [
  {
    matcher: (msg) =>
      msg.toLowerCase().includes("network") ||
      msg.toLowerCase().includes("fetch"),
    getError: () => ({
      title: "Connection error",
      message: "Unable to connect to the server.",
      suggestions: [
        "Check your internet connection",
        "Verify the server is running",
        "Try refreshing the page",
      ],
      action: "Retry",
    }),
  },
  {
    matcher: (msg) => msg.toLowerCase().includes("timeout"),
    getError: () => ({
      title: "Request timed out",
      message: "The server took too long to respond.",
      suggestions: [
        "Check your internet connection stability",
        "The server may be under heavy load, try again later",
        "Contact support if the problem persists",
      ],
      action: "Retry",
    }),
  },
  {
    matcher: (msg) =>
      msg.toLowerCase().includes("401") ||
      msg.toLowerCase().includes("unauthorized"),
    getError: () => ({
      title: "Authentication required",
      message: "Your session has expired or you are not logged in.",
      suggestions: [
        "Log in again with your credentials",
        "Clear your browser cache and cookies",
        "Contact support if you cannot access your account",
      ],
      action: "Log in",
    }),
  },
  {
    matcher: (msg) =>
      msg.toLowerCase().includes("403") ||
      msg.toLowerCase().includes("forbidden"),
    getError: () => ({
      title: "Access denied",
      message: "You do not have permission to perform this action.",
      suggestions: [
        "Verify you are logged in with the correct account",
        "Contact your administrator for access",
      ],
      action: "Check permissions",
    }),
  },
  {
    matcher: (msg) =>
      msg.toLowerCase().includes("sync") && msg.toLowerCase().includes("fail"),
    getError: () => ({
      title: "Sync failed",
      message: "Unable to synchronize your health data.",
      suggestions: [
        "Check that your service credentials are correct in Settings",
        "Verify the external service (Garmin, Hevy) is accessible",
        "Try syncing again in a few minutes",
      ],
      action: "Check settings",
    }),
  },
  {
    matcher: (msg) => msg.toLowerCase().includes("garmin"),
    getError: () => ({
      title: "Garmin sync issue",
      message: "Unable to connect to Garmin Connect.",
      suggestions: [
        "Verify your Garmin credentials are correct",
        "Check if Garmin Connect is accessible",
        "Try logging into Garmin Connect web manually first",
      ],
      action: "Check Garmin settings",
    }),
  },
  {
    matcher: (msg) => msg.toLowerCase().includes("hevy"),
    getError: () => ({
      title: "Hevy sync issue",
      message: "Unable to connect to Hevy.",
      suggestions: [
        "Verify your Hevy API key is correct",
        "Check if Hevy service is accessible",
        "Regenerate your API key in the Hevy app",
      ],
      action: "Check Hevy settings",
    }),
  },
  {
    matcher: (msg) => msg.toLowerCase().includes("whoop"),
    getError: () => ({
      title: "Whoop sync issue",
      message: "Unable to connect to Whoop.",
      suggestions: [
        "Re-authorize Whoop connection",
        "Check if Whoop service is accessible",
        "Verify OAuth credentials are valid",
      ],
      action: "Reconnect Whoop",
    }),
  },
  {
    matcher: (msg) =>
      msg.toLowerCase().includes("database") ||
      msg.toLowerCase().includes("postgres"),
    getError: () => ({
      title: "Database error",
      message: "Unable to access the database.",
      suggestions: [
        "This is likely a temporary issue",
        "Wait a moment and try again",
        "Contact support if the problem persists",
      ],
    }),
  },
];

export function mapTechnicalError(errorMessage: string): UserFriendlyError {
  for (const mapping of errorMappings) {
    if (mapping.matcher(errorMessage)) {
      return mapping.getError(errorMessage);
    }
  }

  return {
    title: "Unexpected error",
    message: sanitizeErrorMessage(errorMessage),
    suggestions: [
      "Try refreshing the page",
      "Clear your browser cache",
      "Contact support if the problem persists",
    ],
  };
}

function sanitizeErrorMessage(message: string): string {
  const sanitized = message
    .replace(/password=[^&\s]+/gi, "password=[REDACTED]")
    .replace(/api_key=[^&\s]+/gi, "api_key=[REDACTED]")
    .replace(/token=[^&\s]+/gi, "token=[REDACTED]");

  return sanitized.length > 200
    ? `${sanitized.substring(0, 200)}...`
    : sanitized;
}
