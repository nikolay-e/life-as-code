import type {
  AnalyticsResponse,
  AuthResponse,
  BackoffStatus,
  BloodBiomarkerData,
  ClinicalAlertEvent,
  CredentialTestResult,
  CredentialsStatus,
  ExerciseTemplate,
  FunctionalTestData,
  GarminActivityData,
  GarminRacePredictionData,
  HealthData,
  InterventionData,
  LongevityGoalData,
  MLForecastMetric,
  SyncStatus,
  User,
  UserProfile,
  UserThresholds,
  VersionInfo,
  WorkoutExerciseDetail,
  WorkoutProgramCreatePayload,
  WorkoutProgramDetail,
  WorkoutProgramSummary,
  WorkoutProgramUpdatePayload,
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

    getRacePredictions: (
      startDate: string,
      endDate: string,
    ): Promise<GarminRacePredictionData[]> =>
      request(
        `/data/race-predictions?start_date=${startDate}&end_date=${endDate}`,
      ),
  },

  ml: {
    getForecasts: (
      metric?: string,
      horizon?: number,
    ): Promise<{ forecasts: MLForecastMetric[]; has_active: boolean }> => {
      const params = new URLSearchParams();
      if (metric) params.set("metric", metric);
      if (horizon) params.set("horizon", String(horizon));
      const qs = params.toString();
      const path = qs ? `/ml/forecasts?${qs}` : "/ml/forecasts";
      return request(path);
    },
  },

  clinicalAlerts: {
    list: (status?: string): Promise<ClinicalAlertEvent[]> => {
      const qs = status ? `?status=${status}` : "";
      return request(`/clinical-alerts${qs}`);
    },
    updateStatus: (
      id: number,
      status: "open" | "acknowledged" | "resolved",
    ): Promise<ClinicalAlertEvent> =>
      request(`/clinical-alerts/${String(id)}/status`, {
        method: "PUT",
        body: JSON.stringify({ status }),
      }),
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

    updateGarminCredentials: (
      email: string,
      password: string,
    ): Promise<CredentialsStatus> =>
      request("/settings/credentials/garmin", {
        method: "PUT",
        body: JSON.stringify({ email, password }),
      }),

    updateHevyCredentials: (apiKey: string): Promise<CredentialsStatus> =>
      request("/settings/credentials/hevy", {
        method: "PUT",
        body: JSON.stringify({ api_key: apiKey }),
      }),

    deleteGarminCredentials: (): Promise<{ deleted: boolean }> =>
      request("/settings/credentials/garmin", { method: "DELETE" }),

    deleteHevyCredentials: (): Promise<{ deleted: boolean }> =>
      request("/settings/credentials/hevy", { method: "DELETE" }),

    testGarminCredentials: (
      email: string,
      password: string,
    ): Promise<CredentialTestResult> =>
      request("/settings/credentials/garmin/test", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),

    testHevyCredentials: (apiKey: string): Promise<CredentialTestResult> =>
      request("/settings/credentials/hevy/test", {
        method: "POST",
        body: JSON.stringify({ api_key: apiKey }),
      }),

    updateEightSleepCredentials: (
      email: string,
      password: string,
    ): Promise<CredentialsStatus> =>
      request("/settings/credentials/eight_sleep", {
        method: "PUT",
        body: JSON.stringify({ email, password }),
      }),

    deleteEightSleepCredentials: (): Promise<{ deleted: boolean }> =>
      request("/settings/credentials/eight_sleep", { method: "DELETE" }),

    testEightSleepCredentials: (
      email: string,
      password: string,
    ): Promise<CredentialTestResult> =>
      request("/settings/credentials/eight_sleep/test", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),

    getProfile: (): Promise<UserProfile> => request("/settings/profile"),

    updateProfile: (data: Partial<UserProfile>): Promise<UserProfile> =>
      request("/settings/profile", {
        method: "PUT",
        body: JSON.stringify(data),
      }),
  },

  sync: {
    getStatus: (): Promise<SyncStatus[]> =>
      request<{
        items: SyncStatus[];
        total: number;
        limit: number;
        offset: number;
      }>("/sync/status").then((r) => r.items),

    getBackoffStatus: (): Promise<BackoffStatus> =>
      request<BackoffStatus>("/sync/backoff-status"),

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

    eightSleep: (days?: number): Promise<{ message: string }> => {
      const query = days ? `?days=${String(days)}` : "?full=true";
      return request(`/sync/eight_sleep${query}`, { method: "POST" });
    },
  },

  longevity: {
    getInterventions: (active?: boolean): Promise<InterventionData[]> => {
      const query = active ? "?active=true" : "";
      return request(`/longevity/interventions${query}`);
    },

    createIntervention: (data: {
      name: string;
      category: InterventionData["category"];
      start_date: string;
      end_date?: string | null;
      dosage?: string | null;
      frequency?: string | null;
      notes?: string | null;
    }): Promise<InterventionData> =>
      request("/longevity/interventions", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    updateIntervention: (
      id: number,
      data: Partial<{
        name: string;
        category: InterventionData["category"];
        end_date: string | null;
        dosage: string | null;
        frequency: string | null;
        notes: string | null;
        active: boolean;
      }>,
    ): Promise<InterventionData> =>
      request(`/longevity/interventions/${String(id)}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),

    deleteIntervention: (id: number): Promise<{ deleted: boolean }> =>
      request(`/longevity/interventions/${String(id)}`, { method: "DELETE" }),

    getBiomarkers: (marker?: string): Promise<BloodBiomarkerData[]> => {
      const query = marker ? `?marker=${encodeURIComponent(marker)}` : "";
      return request(`/longevity/biomarkers${query}`);
    },

    createBiomarker: (data: {
      date: string;
      marker_name: string;
      value: number;
      unit: string;
      reference_range_low?: number | null;
      reference_range_high?: number | null;
      longevity_optimal_low?: number | null;
      longevity_optimal_high?: number | null;
      lab_name?: string | null;
      notes?: string | null;
    }): Promise<BloodBiomarkerData> =>
      request("/longevity/biomarkers", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    deleteBiomarker: (id: number): Promise<{ deleted: boolean }> =>
      request(`/longevity/biomarkers/${String(id)}`, { method: "DELETE" }),

    getFunctionalTests: (testName?: string): Promise<FunctionalTestData[]> => {
      const qs = testName ? `?test_name=${encodeURIComponent(testName)}` : "";
      return request(`/longevity/functional-tests${qs}`);
    },

    createFunctionalTest: (data: {
      date: string;
      test_name: string;
      value: number;
      unit: string;
      notes?: string | null;
    }): Promise<FunctionalTestData> =>
      request("/longevity/functional-tests", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    deleteFunctionalTest: (id: number): Promise<{ deleted: boolean }> =>
      request(`/longevity/functional-tests/${String(id)}`, {
        method: "DELETE",
      }),

    getGoals: (): Promise<LongevityGoalData[]> => request("/longevity/goals"),

    createGoal: (data: {
      category: string;
      description: string;
      target_value?: number | null;
      current_value?: number | null;
      unit?: string | null;
      target_age?: number | null;
    }): Promise<LongevityGoalData> =>
      request("/longevity/goals", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    updateGoal: (
      id: number,
      data: Partial<{
        category: string;
        description: string;
        target_value: number | null;
        current_value: number | null;
        unit: string | null;
        target_age: number | null;
      }>,
    ): Promise<LongevityGoalData> =>
      request(`/longevity/goals/${String(id)}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),

    deleteGoal: (id: number): Promise<{ deleted: boolean }> =>
      request(`/longevity/goals/${String(id)}`, { method: "DELETE" }),
  },

  programs: {
    list: (): Promise<WorkoutProgramSummary[]> => request("/programs"),

    getActive: (): Promise<WorkoutProgramDetail | null> =>
      request("/programs/active"),

    get: (id: number): Promise<WorkoutProgramDetail> =>
      request(`/programs/${String(id)}`),

    create: (data: WorkoutProgramCreatePayload): Promise<WorkoutProgramDetail> =>
      request("/programs", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    update: (
      id: number,
      data: WorkoutProgramUpdatePayload,
    ): Promise<WorkoutProgramDetail> =>
      request(`/programs/${String(id)}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),

    activate: (id: number): Promise<WorkoutProgramDetail> =>
      request(`/programs/${String(id)}/activate`, { method: "POST" }),

    archive: (id: number): Promise<WorkoutProgramDetail> =>
      request(`/programs/${String(id)}/archive`, { method: "POST" }),

    delete: (id: number): Promise<{ deleted: boolean }> =>
      request(`/programs/${String(id)}`, { method: "DELETE" }),
  },

  exerciseTemplates: {
    list: (params?: {
      q?: string;
      muscle?: string;
      equipment?: string;
      limit?: number;
    }): Promise<ExerciseTemplate[]> => {
      const qs = new URLSearchParams();
      if (params?.q) qs.set("q", params.q);
      if (params?.muscle) qs.set("muscle", params.muscle);
      if (params?.equipment) qs.set("equipment", params.equipment);
      if (params?.limit) qs.set("limit", String(params.limit));
      const q = qs.toString();
      return request(`/exercise-templates${q ? `?${q}` : ""}`);
    },

    sync: (): Promise<{
      fetched: number;
      created: number;
      updated: number;
      synced_at: string;
    }> => request("/exercise-templates/sync", { method: "POST" }),
  },
};

export { ApiError };
