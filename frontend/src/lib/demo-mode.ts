import { useAuthStore } from "../features/auth/store";

interface MockBaseline {
  key: string;
  current_value: number | null;
  mean: number | null;
  std: number | null;
  z_score: number | null;
  shifted_z_score: number | null;
  trend_slope: number | null;
  percentile: number | null;
  quality_coverage: number;
  quality_confidence: number;
  short_term_mean: number | null;
  cv: number;
  valid_points: number;
  outlier_rate: number;
  latency_days: number | null;
}

function makeBaseline(
  key: string,
  current: number,
  mean: number,
  std: number,
): MockBaseline {
  const z = (current - mean) / Math.max(0.0001, std);
  return {
    key,
    current_value: current,
    mean,
    std,
    z_score: z,
    shifted_z_score: z,
    trend_slope: 0.05,
    percentile: 50 + z * 20,
    quality_coverage: 1,
    quality_confidence: 0.92,
    short_term_mean: (current + mean) / 2,
    cv: std / Math.max(0.0001, mean),
    valid_points: 84,
    outlier_rate: 0.01,
    latency_days: 0,
  };
}

function generateRange(days: number): Record<string, unknown> {
  const today = new Date();
  const hrv = [];
  const sleep = [];
  const heart_rate = [];
  const steps = [];
  const weight = [];
  const stress = [];
  const energy = [];
  const whoop_recovery = [];
  const whoop_cycle = [];
  const whoop_sleep = [];
  const garmin_training_status = [];

  for (let i = days; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().slice(0, 10);
    const hrvVal = 45 + Math.sin(i / 7) * 8 + (Math.random() - 0.5) * 5;
    const rhr = 56 + Math.cos(i / 9) * 4 + (Math.random() - 0.5) * 2;
    const sleepMin = 420 + Math.sin(i / 5) * 40 + (Math.random() - 0.5) * 30;
    const stepsTotal = Math.round(
      8000 + Math.sin(i / 4) * 2000 + (Math.random() - 0.5) * 1500,
    );
    const w = 78.5 + Math.sin(i / 30) * 0.8 + (Math.random() - 0.5) * 0.3;
    const stressVal = 28 + Math.sin(i / 6) * 8 + (Math.random() - 0.5) * 6;
    const recovery = Math.max(
      20,
      Math.min(95, 65 + Math.sin(i / 6) * 18 + (Math.random() - 0.5) * 8),
    );

    hrv.push({
      date: dateStr,
      source: "garmin",
      hrv_avg: hrvVal,
      hrv_status: "balanced",
    });
    sleep.push({
      date: dateStr,
      total_sleep_minutes: sleepMin,
      deep_sleep_minutes: sleepMin * 0.21,
      rem_sleep_minutes: sleepMin * 0.27,
      light_sleep_minutes: sleepMin * 0.49,
      awake_minutes: sleepMin * 0.03,
      sleep_score: 78 + (Math.random() - 0.5) * 12,
    });
    heart_rate.push({
      date: dateStr,
      resting_hr: rhr,
      max_hr: 178,
      avg_hr: 64,
    });
    steps.push({ date: dateStr, total_steps: stepsTotal });
    weight.push({ date: dateStr, weight_kg: w, bmi: 23.5, body_fat_pct: 14.8 });
    stress.push({
      date: dateStr,
      avg_stress: stressVal,
      max_stress: stressVal + 12,
      stress_level: "low",
    });
    energy.push({
      date: dateStr,
      total_calories: 2700 + Math.round(Math.random() * 200),
    });
    whoop_recovery.push({
      date: dateStr,
      recovery_score: recovery,
      hrv_rmssd: hrvVal,
    });
    whoop_cycle.push({
      date: dateStr,
      day_strain: 11 + Math.sin(i / 3) * 4,
      max_hr: 180,
      avg_hr: 78,
      kilojoules: 11000,
    });
    whoop_sleep.push({
      date: dateStr,
      sleep_performance: 86,
      sleep_efficiency: 0.95,
    });
    garmin_training_status.push({
      date: dateStr,
      training_status: "productive",
      acute_load: 420,
      chronic_load: 380,
    });
  }

  return {
    hrv,
    sleep,
    heart_rate,
    steps,
    weight,
    stress,
    energy,
    whoop_recovery,
    whoop_cycle,
    whoop_sleep,
    garmin_training_status,
  };
}

export function installDemoMode(): void {
  const origFetch = globalThis.fetch.bind(globalThis);

  globalThis.fetch = async (
    input: Request | string | URL,
    init?: RequestInit,
  ) => {
    const url =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.href
          : input.url;

    if (url.includes("/api/auth/me")) {
      return new Response(
        JSON.stringify({ user: { id: 1, username: "demo" } }),
        {
          status: 200,
          headers: { "content-type": "application/json" },
        },
      );
    }
    if (url.includes("/api/auth/login")) {
      return new Response(
        JSON.stringify({ user: { id: 1, username: "demo" } }),
        {
          status: 200,
          headers: { "content-type": "application/json" },
        },
      );
    }
    if (url.includes("/api/data/range")) {
      return new Response(JSON.stringify(generateRange(60)), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (
      url.includes("/api/data/detailed-workouts") ||
      url.includes("/api/data/workouts/detailed")
    ) {
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (
      url.includes("/api/data/garmin-activities") ||
      url.includes("/api/data/activities")
    ) {
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (
      url.includes("/api/longevity/interventions") ||
      url.includes("/api/longevity/biomarkers")
    ) {
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (url.includes("/api/longevity")) {
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (url.includes("/api/analytics")) {
      const baselines = {
        hrv: makeBaseline("hrv", 52, 48, 6),
        rhr: makeBaseline("rhr", 54, 56, 3),
        sleep: makeBaseline("sleep", 458, 442, 35),
        steps: makeBaseline("steps", 9842, 8420, 2100),
        recovery: makeBaseline("recovery", 78, 65, 12),
        weight: makeBaseline("weight", 78.2, 78.5, 0.4),
        stress: makeBaseline("stress", 28, 32, 8),
        calories: makeBaseline("calories", 2830, 2700, 250),
        strain: makeBaseline("strain", 11.4, 12, 3),
        sleep_score: makeBaseline("sleep_score", 84, 80, 6),
        sleep_deep: makeBaseline("sleep_deep", 95, 90, 12),
        sleep_rem: makeBaseline("sleep_rem", 122, 115, 18),
        sleep_latency: makeBaseline("sleep_latency", 12, 14, 4),
        respiratory_rate: makeBaseline("respiratory_rate", 14.1, 14, 0.6),
        bed_temp: makeBaseline("bed_temp", 21.5, 21.8, 1.2),
        room_temp: makeBaseline("room_temp", 19.5, 19, 1.4),
        dailyStrain: makeBaseline("dailyStrain", 11.4, 12, 3),
        toss_and_turn: makeBaseline("toss_and_turn", 6, 7, 2),
        sleep_fitness: makeBaseline("sleep_fitness", 78, 76, 4),
        sleep_routine: makeBaseline("sleep_routine", 84, 82, 5),
        sleep_quality_es: makeBaseline("sleep_quality_es", 86, 84, 4),
      };
      return new Response(
        JSON.stringify({
          mode: "recent",
          mode_config: {
            range_days: 42,
            short_term: 7,
            long_term: 84,
            baseline: 84,
            trend_window: 7,
            use_shifted_z_score: false,
          },
          metric_baselines: baselines,
          health_score: {
            overall: 82,
            recovery_core: 78,
            training_load: 84,
            behavior_support: 80,
            contributors: [],
            steps_status: { use_today: false },
            data_confidence: 0.92,
          },
          recovery_metrics: {
            avg_recovery_short: 72,
            avg_recovery_long: 68,
            recovery_score: 78,
            hrv_avg: 52,
            hrv_status: "balanced",
            avg_hrv_short: 52,
            avg_hrv_long: 48,
            avg_hrv: 50,
            avg_rhr_short: 54,
            avg_rhr_long: 56,
            stress_level: "low",
            avg_stress: 28,
            recovery_debt: 0.2,
            recovery_half_life_days: 1.4,
          },
          sleep_metrics: {
            avg_sleep_short: 7.6,
            avg_sleep_long: 7.4,
            avg_sleep: 7.5,
            avg_deep_short: 95,
            avg_deep_long: 92,
            avg_rem_short: 122,
            avg_rem_long: 118,
            avg_score_short: 84,
            avg_score_long: 81,
            avg_efficiency_short: 0.94,
            avg_efficiency_long: 0.93,
            avg_latency_short: 12,
            avg_latency_long: 14,
            avg_resp_short: 14.1,
            avg_resp_long: 14,
            avg_bed_temp_short: 21.5,
            avg_bed_temp_long: 21.8,
            avg_room_temp_short: 19.5,
            avg_room_temp_long: 19,
            sleep_debt: 0.4,
            target_hours: 8,
            consistency_score: 82,
          },
          activity_metrics: {
            avg_steps_short: 9842,
            avg_steps_long: 8420,
            avg_strain_short: 11.4,
            avg_strain_long: 12,
            avg_calories_short: 2830,
            avg_calories_long: 2700,
            sessions_per_week: 5.2,
            tonnage_week: 38420,
          },
          weight_metrics: {
            avg_weight_short: 78.2,
            avg_weight_long: 78.5,
            trend_slope: -0.04,
          },
          calories_metrics: { avg_short: 2830, avg_long: 2700 },
          energy_balance: { surplus_deficit: -180, tdee: 2900 },
          clinical_alerts: { alerts: [] },
          overreaching: { acwr: 1.18, status: "sweet" },
          illness_risk: { signal: null, score: 0 },
          decorrelation: { alert: null },
          correlations: {},
          velocity: {},
          recovery_capacity: {},
          anomalies: { items: [] },
          day_over_day: {},
          recent_days: [],
          day_completeness: 1,
          data_source_summary: [],
          raw_series: {},
          advanced_insights: { insights: [] },
          ml_insights: { insights: [] },
          longevity_insights: { interventions: [], biomarkers: [] },
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    }
    if (url.includes("/api/sync/status") || url.includes("/api/sync")) {
      const now = new Date().toISOString();
      return new Response(
        JSON.stringify({
          garmin: { last_sync: now, status: "connected" },
          hevy: { last_sync: now, status: "connected" },
          whoop: { last_sync: now, status: "connected" },
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    }
    if (url.includes("/api/settings")) {
      return new Response(JSON.stringify({ credentials: {}, thresholds: {} }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (url.includes("/api/")) {
      return new Response(JSON.stringify({}), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    return origFetch(input, init);
  };

  useAuthStore.setState({
    user: { id: 1, username: "demo" },
    isInitialized: true,
    isLoading: false,
    error: null,
  });
}
