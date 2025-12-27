import type {
  AuthResponse,
  CredentialsStatus,
  HealthData,
  SyncStatus,
  User,
  UserThresholds,
  VersionInfo,
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

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      errorData.message || `Request failed: ${response.statusText}`,
    );
  }

  return response.json();
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
    getStatus: (): Promise<SyncStatus[]> => request("/sync/status"),

    garmin: (days?: number): Promise<{ message: string }> =>
      request(`/sync/garmin${days ? `?days=${days}` : "?full=true"}`, {
        method: "POST",
      }),

    hevy: (days?: number): Promise<{ message: string }> =>
      request(`/sync/hevy${days ? `?days=${days}` : "?full=true"}`, {
        method: "POST",
      }),

    whoop: (days?: number): Promise<{ message: string }> =>
      request(`/sync/whoop${days ? `?days=${days}` : "?full=true"}`, {
        method: "POST",
      }),
  },
};

export { ApiError };
