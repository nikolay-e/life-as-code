import type {
  AnalyticsResponse,
  AuthResponse,
  CredentialsStatus,
  GarminActivityData,
  HealthData,
  SyncStatus,
  User,
  UserThresholds,
  VersionInfo,
  WorkoutExerciseDetail,
} from "../types/api";

const API_BASE = "/api";

class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function normalizeHeaders(
  headers: HeadersInit | undefined,
): Record<string, string> {
  if (!headers) return {};
  if (headers instanceof Headers) {
    return Object.fromEntries(headers.entries());
  }
  if (Array.isArray(headers)) {
    return Object.fromEntries(headers);
  }
  return headers;
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
      ...normalizeHeaders(options.headers),
    },
  });

  if (!response.ok) {
    const errorData = (await response.json().catch(() => ({}))) as {
      message?: string;
      error?: string;
    };
    throw new ApiError(
      response.status,
      errorData.message ??
        errorData.error ??
        `Request failed: ${response.statusText}`,
    );
  }

  return response.json() as Promise<T>;
}

export const api = {
  auth: {
    login: (username: string, password: string): Promise<AuthResponse> =>
      request("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      }),

    logout: (): Promise<{ message: string }> =>
      request("/auth/logout", { method: "POST" }),

    me: (): Promise<{ user: User }> => request("/auth/me"),
  },

  version: (): Promise<VersionInfo> => request("/version"),

  data: {
    getRange: (startDate: string, endDate: string): Promise<HealthData> =>
      request(`/data/range?start_date=${startDate}&end_date=${endDate}`),

    getDetailedWorkouts: (
      startDate: string,
      endDate: string,
    ): Promise<WorkoutExerciseDetail[]> =>
      request(
        `/data/workouts/detailed?start_date=${startDate}&end_date=${endDate}`,
      ),

    getGarminActivities: (
      startDate: string,
      endDate: string,
    ): Promise<GarminActivityData[]> =>
      request(
        `/data/activities/garmin?start_date=${startDate}&end_date=${endDate}`,
      ),
  },

  analytics: {
    get: (mode: string = "recent"): Promise<AnalyticsResponse> =>
      request(`/analytics?mode=${mode}`),
  },

  settings: {
    getThresholds: (): Promise<UserThresholds> =>
      request("/settings/thresholds"),

    updateThresholds: (
      thresholds: Partial<UserThresholds>,
    ): Promise<UserThresholds> =>
      request("/settings/thresholds", {
        method: "PUT",
        body: JSON.stringify(thresholds),
      }),

    getCredentials: (): Promise<CredentialsStatus> =>
      request("/settings/credentials"),
  },

  sync: {
    getStatus: (): Promise<SyncStatus[]> =>
      request<{
        items: SyncStatus[];
        total: number;
        limit: number;
        offset: number;
      }>("/sync/status").then((r) => r.items),

    garmin: (days?: number): Promise<{ message: string }> => {
      const query = days ? `?days=${String(days)}` : "?full=true";
      return request(`/sync/garmin${query}`, { method: "POST" });
    },

    hevy: (days?: number): Promise<{ message: string }> => {
      const query = days ? `?days=${String(days)}` : "?full=true";
      return request(`/sync/hevy${query}`, { method: "POST" });
    },

    whoop: (days?: number): Promise<{ message: string }> => {
      const query = days ? `?days=${String(days)}` : "?full=true";
      return request(`/sync/whoop${query}`, { method: "POST" });
    },
  },
};

export { ApiError };
