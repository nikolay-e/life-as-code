import argparse
import json

import polars as pl

from src.loader import load, snapshot_path

LOGICAL_SOURCES: dict[str, list[str]] = {
    "garmin": ["_garmin", "_garmin_training", "_garmin_race", "n_activities_garmin"],
    "whoop": ["_whoop", "_whoop_cycle", "n_workouts_whoop"],
    "eight_sleep": ["_eight_sleep", "_eight"],
    "apple_health": ["_apple_health"],
    "google": ["_google"],
    "hevy": ["strength_"],
}

LOGICAL_SOURCE_MAP: dict[str, list[str]] = {
    "garmin_watch": [
        "garmin_sleep",
        "garmin_hrv",
        "garmin_hr",
        "garmin_steps",
        "garmin_energy",
        "garmin_stress",
        "garmin_weight",
        "garmin_activities",
        "garmin_training_status",
        "garmin_race_predictions",
    ],
    "whoop_band": [
        "whoop_recovery",
        "whoop_sleep_extended",
        "whoop_cycles",
        "whoop_workouts",
        "whoop_sleep_unified",
        "whoop_hr_unified",
        "whoop_hrv_unified",
    ],
    "eight_sleep_pod": [
        "eight_sleep_sessions",
        "eight_sleep_unified",
        "eight_hrv_unified",
    ],
    "apple_health": [
        "apple_health_sleep",
        "apple_health_hrv",
        "apple_health_hr",
        "apple_health_weight",
        "apple_health_steps",
        "apple_health_energy",
    ],
    "google_fit": ["google_sleep"],
    "hevy_app": ["hevy_sets"],
}

UNIFIED_SHORT_NAMES = {
    "total_sleep_min",
    "deep_sleep_min",
    "rem_sleep_min",
    "light_sleep_min",
    "sleep_score",
    "resting_hr",
    "max_hr",
    "weight_kg",
    "body_fat_pct",
    "total_steps",
    "active_energy",
    "avg_stress",
    "vo2_max",
    "hrv_garmin",
    "hrv_whoop_rmssd",
    "recovery_score_whoop",
    "strain_whoop",
    "training_load_garmin",
    "readiness_garmin",
    "strength_volume_kg",
    "strength_total_sets",
    "n_activities_garmin",
    "n_workouts_whoop",
}

CLAMPS: dict[str, tuple[float, float]] = {
    "resting_hr": (25, 120),
    "resting_heart_rate": (25, 120),
    "avg_hr": (25, 200),
    "max_hr": (25, 240),
    "avg_heart_rate": (25, 200),
    "max_heart_rate": (25, 240),
    "heart_rate": (25, 200),
    "hrv_avg": (1, 350),
    "hrv_rmssd": (1, 350),
    "hrv": (1, 350),
    "spo2_avg": (70, 100),
    "spo2_min": (70, 100),
    "spo2_percentage": (70, 100),
    "total_sleep_minutes": (0, 900),
    "total_sleep_duration_minutes": (0, 900),
    "deep_minutes": (0, 600),
    "light_minutes": (0, 800),
    "rem_minutes": (0, 400),
    "awake_minutes": (0, 600),
    "deep_sleep_minutes": (0, 600),
    "light_sleep_minutes": (0, 800),
    "rem_sleep_minutes": (0, 400),
    "respiratory_rate": (4, 40),
    "waking_respiratory_rate": (4, 40),
    "lowest_respiratory_rate": (4, 40),
    "highest_respiratory_rate": (4, 40),
    "body_fat_pct": (3, 60),
    "water_pct": (20, 80),
    "bmi": (10, 60),
    "skin_temp_celsius": (28, 42),
    "bed_temp_celsius": (10, 50),
    "room_temp_celsius": (10, 40),
    "vo2_max": (10, 90),
    "vo2_max_precise": (10, 90),
    "vo2_max_value": (10, 90),
    "strain": (0, 21),
    "recovery_score": (0, 100),
    "sleep_score": (0, 100),
    "sleep_performance_percentage": (0, 100),
    "sleep_consistency_percentage": (0, 100),
    "sleep_efficiency_percentage": (0, 100),
}

WEIGHT_DEVIATION = 0.30


def _clamp_column(df: pl.DataFrame, col: str, lo: float, hi: float) -> tuple[pl.DataFrame, int]:
    if col not in df.columns:
        return df, 0
    n_clamped = df.filter(pl.col(col).is_not_null() & ((pl.col(col) < lo) | (pl.col(col) > hi))).height
    if n_clamped == 0:
        return df, 0
    fixed = df.with_columns(
        pl.when((pl.col(col) < lo) | (pl.col(col) > hi)).then(None).otherwise(pl.col(col)).alias(col)
    )
    return fixed, n_clamped


def _clean_table(name: str, df: pl.DataFrame) -> tuple[pl.DataFrame, list[dict]]:
    log: list[dict] = []
    for col, (lo, hi) in CLAMPS.items():
        df, n = _clamp_column(df, col, lo, hi)
        if n:
            log.append(
                {
                    "table": name,
                    "column": col,
                    "action": "clamp",
                    "lo": lo,
                    "hi": hi,
                    "n": n,
                }
            )

    if name == "weight" and "weight_kg" in df.columns and df.height > 10:
        median = df["weight_kg"].drop_nulls().median()
        if median:
            lo = float(median) * (1 - WEIGHT_DEVIATION)
            hi = float(median) * (1 + WEIGHT_DEVIATION)
            df, n = _clamp_column(df, "weight_kg", lo, hi)
            if n:
                log.append(
                    {
                        "table": name,
                        "column": "weight_kg",
                        "action": "clamp_dynamic",
                        "lo": lo,
                        "hi": hi,
                        "n": n,
                    }
                )

    if name == "whoop_recovery" and "user_calibrating" in df.columns:
        before = df.height
        df = df.filter(~pl.col("user_calibrating").fill_null(False))
        dropped = before - df.height
        if dropped:
            log.append(
                {
                    "table": name,
                    "column": "user_calibrating",
                    "action": "drop_rows",
                    "lo": None,
                    "hi": None,
                    "n": dropped,
                }
            )

    return df, log


def _pivot_by_source(
    df: pl.DataFrame,
    metric_cols: list[str],
    table_prefix: str,
    date_col: str = "date",
) -> pl.DataFrame:
    if "source" not in df.columns or df.height == 0:
        return df.select([date_col, *(c for c in metric_cols if c in df.columns)])
    sources = df["source"].drop_nulls().unique().sort().to_list()
    available = [c for c in metric_cols if c in df.columns]
    parts: list[pl.DataFrame] = []
    for src in sources:
        sub = df.filter(pl.col("source") == src).group_by(date_col).agg([pl.col(c).last().alias(c) for c in available])
        sub = sub.rename({c: f"{table_prefix}_{c}_{src}" for c in available})
        sub = _drop_all_null(sub, date_col)
        parts.append(sub)
    if not parts:
        return pl.DataFrame({date_col: []})
    out = parts[0]
    for p in parts[1:]:
        out = out.join(p, on=date_col, how="full", coalesce=True)
    return out


def _rename_with_suffix(
    df: pl.DataFrame,
    suffix: str,
    metric_cols: list[str],
    table_prefix: str,
    date_col: str = "date",
) -> pl.DataFrame:
    available = [c for c in metric_cols if c in df.columns]
    rolled = (
        df.group_by(date_col)
        .agg([pl.col(c).last().alias(c) for c in available])
        .rename({c: f"{table_prefix}_{c}_{suffix}" for c in available})
    )
    return _drop_all_null(rolled, date_col)


def _drop_all_null(df: pl.DataFrame, date_col: str) -> pl.DataFrame:
    keep = [date_col]
    for c in df.columns:
        if c == date_col:
            continue
        if df[c].drop_nulls().len() > 0:
            keep.append(c)
    return df.select(keep)


def _aggregate_garmin_activities(df: pl.DataFrame) -> pl.DataFrame:
    if df.height == 0:
        return pl.DataFrame({"date": []})
    return df.group_by("date").agg(
        pl.col("duration_seconds").sum().alias("activity_duration_sec_garmin"),
        pl.col("calories").sum().alias("activity_kcal_garmin"),
        pl.col("elevation_gain_meters").sum().alias("activity_elevation_gain_m_garmin"),
        pl.col("distance_meters").sum().alias("activity_distance_m_garmin"),
        pl.col("max_heart_rate").max().alias("activity_max_hr_garmin"),
        pl.col("training_effect_aerobic").max().alias("activity_te_aerobic_garmin"),
        pl.col("training_effect_anaerobic").max().alias("activity_te_anaerobic_garmin"),
        pl.col("activity_id").count().alias("n_activities_garmin"),
    )


def _aggregate_whoop_workouts(df: pl.DataFrame) -> pl.DataFrame:
    if df.height == 0:
        return pl.DataFrame({"date": []})
    return df.group_by("date").agg(
        pl.col("strain").sum().alias("workout_strain_total_whoop"),
        pl.col("strain").max().alias("workout_strain_max_whoop"),
        pl.col("kilojoules").sum().alias("workout_kj_whoop"),
        pl.col("max_heart_rate").max().alias("workout_max_hr_whoop"),
        pl.col("id").count().alias("n_workouts_whoop"),
    )


def _aggregate_workout_sets(df: pl.DataFrame) -> pl.DataFrame:
    if df.height == 0:
        return pl.DataFrame({"date": []})
    return df.group_by("date").agg(
        (pl.col("weight_kg") * pl.col("reps")).sum().alias("strength_volume_kg"),
        pl.col("set_index").count().alias("strength_total_sets"),
        pl.col("weight_kg").max().alias("strength_max_weight_kg"),
        pl.col("rpe").mean().alias("strength_avg_rpe"),
        pl.col("exercise").n_unique().alias("strength_n_exercises"),
    )


SLEEP_METRICS = [
    "deep_minutes",
    "light_minutes",
    "rem_minutes",
    "awake_minutes",
    "total_sleep_minutes",
    "sleep_score",
    "skin_temp_celsius",
    "spo2_avg",
    "spo2_min",
    "respiratory_rate",
    "sleep_quality_score",
    "sleep_recovery_score",
    "body_battery_change",
    "awake_count",
    "sleep_start_time",
    "sleep_end_time",
]
HRV_METRICS = ["hrv_avg", "baseline_low_ms", "baseline_high_ms"]
HEART_RATE_METRICS = [
    "resting_hr",
    "max_hr",
    "avg_hr",
    "spo2_avg",
    "spo2_min",
    "waking_respiratory_rate",
    "lowest_respiratory_rate",
    "highest_respiratory_rate",
]
WEIGHT_METRICS = [
    "weight_kg",
    "bmi",
    "body_fat_pct",
    "muscle_mass_kg",
    "bone_mass_kg",
    "water_pct",
]
STEPS_METRICS = ["total_steps", "total_distance", "active_minutes", "floors_climbed"]
ENERGY_METRICS = ["active_energy", "basal_energy"]
STRESS_METRICS = ["avg_stress", "max_stress", "rest_stress", "activity_stress"]

WHOOP_SLEEP_METRICS = [
    "sleep_performance_percentage",
    "sleep_consistency_percentage",
    "sleep_efficiency_percentage",
    "total_sleep_duration_minutes",
    "deep_sleep_minutes",
    "light_sleep_minutes",
    "rem_sleep_minutes",
    "awake_minutes",
    "respiratory_rate",
    "sleep_need_baseline_minutes",
    "sleep_need_debt_minutes",
    "sleep_need_strain_minutes",
    "sleep_cycle_count",
    "disturbance_count",
    "sleep_start_time",
    "sleep_end_time",
]
WHOOP_RECOVERY_METRICS = [
    "recovery_score",
    "resting_heart_rate",
    "hrv_rmssd",
    "spo2_percentage",
    "skin_temp_celsius",
]
WHOOP_CYCLES_METRICS = ["strain", "kilojoules", "avg_heart_rate", "max_heart_rate"]
EIGHT_SLEEP_METRICS = [
    "score",
    "sleep_duration_seconds",
    "light_duration_seconds",
    "deep_duration_seconds",
    "rem_duration_seconds",
    "tnt",
    "heart_rate",
    "hrv",
    "respiratory_rate",
    "latency_asleep_seconds",
    "bed_temp_celsius",
    "room_temp_celsius",
    "sleep_fitness_score",
    "sleep_routine_score",
    "sleep_quality_score",
    "sleep_start_time",
    "sleep_end_time",
]
TRAINING_STATUS_METRICS = [
    "vo2_max",
    "vo2_max_precise",
    "fitness_age",
    "training_load_7_day",
    "acute_training_load",
    "training_status",
    "primary_training_effect",
    "anaerobic_training_effect",
    "endurance_score",
    "training_readiness_score",
    "total_kilocalories",
    "active_kilocalories",
]
RACE_PRED_METRICS = [
    "prediction_5k_seconds",
    "prediction_10k_seconds",
    "prediction_half_marathon_seconds",
    "prediction_marathon_seconds",
    "vo2_max_value",
]

UNIFIED_PRIORITIES: dict[str, list[str]] = {
    "total_sleep_min": [
        "sleep_total_sleep_minutes_garmin",
        "sleep_total_sleep_minutes_whoop",
        "sleep_total_sleep_minutes_apple_health",
        "sleep_total_sleep_minutes_eight_sleep",
        "sleep_total_sleep_minutes_google",
    ],
    "deep_sleep_min": [
        "sleep_deep_minutes_garmin",
        "sleep_deep_minutes_whoop",
    ],
    "rem_sleep_min": [
        "sleep_rem_minutes_garmin",
        "sleep_rem_minutes_whoop",
    ],
    "light_sleep_min": [
        "sleep_light_minutes_garmin",
        "sleep_light_minutes_whoop",
    ],
    "sleep_score": [
        "sleep_sleep_score_garmin",
        "sleep_sleep_score_whoop",
    ],
    "resting_hr": [
        "hr_resting_hr_garmin",
        "hr_resting_hr_apple_health",
        "wrec_resting_heart_rate_whoop",
        "hr_resting_hr_google",
    ],
    "max_hr": ["hr_max_hr_garmin", "hr_max_hr_apple_health"],
    "weight_kg": [
        "body_weight_kg_apple_health",
        "body_weight_kg_garmin",
        "body_weight_kg_google",
    ],
    "body_fat_pct": [
        "body_body_fat_pct_apple_health",
        "body_body_fat_pct_garmin",
        "body_body_fat_pct_google",
    ],
    "total_steps": [
        "steps_total_steps_apple_health",
        "steps_total_steps_garmin",
        "steps_total_steps_google",
    ],
    "active_energy": [
        "energy_active_energy_apple_health",
        "energy_active_energy_garmin",
        "energy_active_energy_google",
    ],
    "avg_stress": ["stress_avg_stress_garmin"],
    "vo2_max": ["gts_vo2_max_garmin_training", "gts_vo2_max_precise_garmin_training"],
    "hrv_garmin": ["hrv_hrv_avg_garmin"],
    "hrv_whoop_rmssd": ["wrec_hrv_rmssd_whoop"],
    "recovery_score_whoop": ["wrec_recovery_score_whoop"],
    "strain_whoop": ["wcycle_strain_whoop_cycle"],
    "training_load_garmin": ["gts_acute_training_load_garmin_training"],
    "readiness_garmin": ["gts_training_readiness_score_garmin_training"],
    "strength_volume_kg": ["strength_volume_kg"],
    "strength_total_sets": ["strength_total_sets"],
    "n_activities_garmin": ["n_activities_garmin"],
    "n_workouts_whoop": ["n_workouts_whoop"],
}


def _add_unified_columns(wide: pl.DataFrame) -> pl.DataFrame:
    add_cols = []
    for unified_name, priorities in UNIFIED_PRIORITIES.items():
        present = [c for c in priorities if c in wide.columns]
        if not present:
            continue
        if len(present) == 1:
            add_cols.append(pl.col(present[0]).alias(unified_name))
        else:
            add_cols.append(pl.coalesce(*[pl.col(c) for c in present]).alias(unified_name))
    if not add_cols:
        return wide
    return wide.with_columns(add_cols)


def _logical_source_columns(wide: pl.DataFrame) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {src: [] for src in LOGICAL_SOURCES}
    candidate_cols = [c for c in wide.columns if c != "date" and c not in UNIFIED_SHORT_NAMES]
    for c in candidate_cols:
        for src, patterns in LOGICAL_SOURCES.items():
            if any(p in c for p in patterns):
                out[src].append(c)
                break
    return out


def _add_coverage_and_sources(wide: pl.DataFrame) -> pl.DataFrame:
    raw_cols = [c for c in wide.columns if c != "date" and c not in UNIFIED_SHORT_NAMES]
    numeric_raw_cols = [c for c in raw_cols if wide[c].dtype.is_numeric()]
    n_numeric = max(len(numeric_raw_cols), 1)

    non_null_count = pl.sum_horizontal([pl.col(c).is_not_null().cast(pl.Int32) for c in numeric_raw_cols])
    wide = wide.with_columns(
        (non_null_count.cast(pl.Float64) / n_numeric).round(3).alias("coverage_pct"),
    )

    source_cols = _logical_source_columns(wide)

    per_source_coverage = []
    for src, cols in source_cols.items():
        if not cols:
            per_source_coverage.append(pl.lit(0.0).alias(f"coverage_{src}_pct"))
            continue
        non_null = pl.sum_horizontal([pl.col(c).is_not_null().cast(pl.Int32) for c in cols])
        per_source_coverage.append((non_null.cast(pl.Float64) / len(cols)).round(3).alias(f"coverage_{src}_pct"))
    wide = wide.with_columns(per_source_coverage)

    flag_exprs = []
    for src, cols in source_cols.items():
        flag_name = f"_has_{src}"
        if not cols:
            flag_exprs.append(pl.lit(False).alias(flag_name))
            continue
        flag_exprs.append(pl.any_horizontal([pl.col(c).is_not_null() for c in cols]).alias(flag_name))
    wide = wide.with_columns(flag_exprs)

    sources_active = (
        pl.concat_str(
            [pl.when(pl.col(f"_has_{src}")).then(pl.lit(src)).otherwise(pl.lit("")) for src in LOGICAL_SOURCES],
            separator=",",
        )
        .str.replace_all(r",+", ",")
        .str.strip_chars(",")
        .alias("sources_active")
    )
    n_sources = pl.sum_horizontal([pl.col(f"_has_{src}").cast(pl.Int32) for src in LOGICAL_SOURCES]).alias(
        "n_sources_active"
    )
    wide = wide.with_columns([sources_active, n_sources])
    return wide.drop([f"_has_{src}" for src in LOGICAL_SOURCES])


def _detect_source_starts(snapshot: str | None) -> list[dict]:
    rows: list[dict] = []
    raw_tables = [
        ("garmin_sleep", "sleep", "garmin"),
        ("apple_health_sleep", "sleep", "apple_health"),
        ("google_sleep", "sleep", "google"),
        ("whoop_sleep_unified", "sleep", "whoop"),
        ("eight_sleep_unified", "sleep", "eight_sleep"),
        ("garmin_hrv", "hrv", "garmin"),
        ("apple_health_hrv", "hrv", "apple_health"),
        ("whoop_hrv_unified", "hrv", "whoop"),
        ("eight_hrv_unified", "hrv", "eight_sleep"),
        ("garmin_hr", "heart_rate", "garmin"),
        ("apple_health_hr", "heart_rate", "apple_health"),
        ("whoop_hr_unified", "heart_rate", "whoop"),
        ("garmin_weight", "weight", "garmin"),
        ("apple_health_weight", "weight", "apple_health"),
        ("garmin_steps", "steps", "garmin"),
        ("apple_health_steps", "steps", "apple_health"),
        ("garmin_energy", "energy", "garmin"),
        ("apple_health_energy", "energy", "apple_health"),
        ("garmin_stress", "stress", "garmin"),
    ]
    for label, table, source in raw_tables:
        try:
            df = load(table, snapshot)
        except FileNotFoundError:
            continue
        if df.height == 0 or "source" not in df.columns:
            continue
        sub = df.filter(pl.col("source") == source)
        if sub.height == 0:
            continue
        rows.append({"source": label, "start": str(sub["date"].min()), "n_days": sub.height})

    standalone = [
        ("whoop_recovery", "whoop_recovery"),
        ("whoop_sleep_extended", "whoop_sleep"),
        ("whoop_cycles", "whoop_cycles"),
        ("whoop_workouts", "whoop_workouts"),
        ("eight_sleep_sessions", "eight_sleep_sessions"),
        ("garmin_training_status", "garmin_training_status"),
        ("garmin_activities", "garmin_activities"),
        ("garmin_race_predictions", "garmin_race_predictions"),
        ("hevy_sets", "workout_sets"),
    ]
    for label, table in standalone:
        try:
            df = load(table, snapshot)
        except FileNotFoundError:
            continue
        if df.height == 0:
            continue
        rows.append({"source": label, "start": str(df["date"].min()), "n_days": df.height})

    rows.sort(key=lambda r: r["start"])
    return rows


def _build_epochs(source_starts: list[dict]) -> list[dict]:
    epochs: list[dict] = []
    seen: set[str] = set()
    for entry in source_starts:
        seen.add(entry["source"])
        if epochs and epochs[-1]["start"] == entry["start"]:
            epochs[-1]["active"] = sorted(seen)
            continue
        epochs.append({"epoch": len(epochs) + 1, "start": entry["start"], "active": sorted(seen)})
    return epochs


def _build_logical_sources(source_starts: list[dict]) -> list[dict]:
    raw_to_start: dict[str, str] = {s["source"]: s["start"] for s in source_starts}
    out: list[dict] = []
    for logical, raw_list in LOGICAL_SOURCE_MAP.items():
        active_raw = [r for r in raw_list if r in raw_to_start]
        if not active_raw:
            continue
        starts = [raw_to_start[r] for r in active_raw]
        out.append(
            {
                "name": logical,
                "start": min(starts),
                "raw_sources": sorted(active_raw),
            }
        )
    out.sort(key=lambda x: x["start"])
    return out


def _build_logical_epochs(logical_sources: list[dict]) -> list[dict]:
    epochs: list[dict] = []
    seen: set[str] = set()
    for entry in sorted(logical_sources, key=lambda x: x["start"]):
        seen.add(entry["name"])
        if epochs and epochs[-1]["start"] == entry["start"]:
            epochs[-1]["active"] = sorted(seen)
            continue
        epochs.append({"epoch": len(epochs) + 1, "start": entry["start"], "active": sorted(seen)})
    return epochs


def _load_clean(name: str, snapshot: str | None, log: list[dict]) -> pl.DataFrame:
    df = load(name, snapshot)
    cleaned, table_log = _clean_table(name, df)
    log.extend(table_log)
    return cleaned


def build_wide_daily(snapshot: str | None) -> tuple[pl.DataFrame, pl.DataFrame]:
    log: list[dict] = []
    sleep = _pivot_by_source(_load_clean("sleep", snapshot, log), SLEEP_METRICS, "sleep")
    hrv = _pivot_by_source(_load_clean("hrv", snapshot, log), HRV_METRICS, "hrv")
    heart_rate = _pivot_by_source(_load_clean("heart_rate", snapshot, log), HEART_RATE_METRICS, "hr")
    weight = _pivot_by_source(_load_clean("weight", snapshot, log), WEIGHT_METRICS, "body")
    steps = _pivot_by_source(_load_clean("steps", snapshot, log), STEPS_METRICS, "steps")
    energy = _pivot_by_source(_load_clean("energy", snapshot, log), ENERGY_METRICS, "energy")
    stress = _pivot_by_source(_load_clean("stress", snapshot, log), STRESS_METRICS, "stress")

    whoop_sleep = _rename_with_suffix(
        _load_clean("whoop_sleep", snapshot, log),
        "whoop",
        WHOOP_SLEEP_METRICS,
        "wsleep",
    )
    whoop_recovery = _rename_with_suffix(
        _load_clean("whoop_recovery", snapshot, log),
        "whoop",
        WHOOP_RECOVERY_METRICS,
        "wrec",
    )
    whoop_cycles = _rename_with_suffix(
        _load_clean("whoop_cycles", snapshot, log),
        "whoop_cycle",
        WHOOP_CYCLES_METRICS,
        "wcycle",
    )
    eight_sleep = _rename_with_suffix(
        _load_clean("eight_sleep_sessions", snapshot, log),
        "eight",
        EIGHT_SLEEP_METRICS,
        "esleep",
    )
    training_status = _rename_with_suffix(
        _load_clean("garmin_training_status", snapshot, log),
        "garmin_training",
        TRAINING_STATUS_METRICS,
        "gts",
    )
    race_pred = _rename_with_suffix(
        _load_clean("garmin_race_predictions", snapshot, log),
        "garmin_race",
        RACE_PRED_METRICS,
        "race",
    )

    garmin_activities = _aggregate_garmin_activities(_load_clean("garmin_activities", snapshot, log))
    whoop_workouts = _aggregate_whoop_workouts(_load_clean("whoop_workouts", snapshot, log))
    workout_sets = _aggregate_workout_sets(_load_clean("workout_sets", snapshot, log))

    daily_tables = [
        sleep,
        hrv,
        heart_rate,
        weight,
        steps,
        energy,
        stress,
        whoop_sleep,
        whoop_recovery,
        whoop_cycles,
        eight_sleep,
        training_status,
        race_pred,
        garmin_activities,
        whoop_workouts,
        workout_sets,
    ]
    non_empty = [t for t in daily_tables if t.height > 0 and "date" in t.columns]
    wide = non_empty[0]
    for t in non_empty[1:]:
        wide = wide.join(t, on="date", how="full", coalesce=True)
    wide = _add_unified_columns(wide)
    wide = _add_coverage_and_sources(wide)
    wide = wide.sort("date")

    log_df = (
        pl.DataFrame(log)
        if log
        else pl.DataFrame(
            schema={
                "table": pl.String,
                "column": pl.String,
                "action": pl.String,
                "lo": pl.Float64,
                "hi": pl.Float64,
                "n": pl.Int64,
            }
        )
    )
    return wide, log_df


def _fill_rates(wide: pl.DataFrame) -> pl.DataFrame:
    n = wide.height
    rates = [
        {
            "column": c,
            "filled": wide[c].drop_nulls().len(),
            "pct": round(wide[c].drop_nulls().len() / n * 100, 1),
        }
        for c in wide.columns
        if c != "date"
    ]
    return pl.DataFrame(rates).sort("pct")


def _print_summary(wide: pl.DataFrame, log_df: pl.DataFrame) -> None:
    print(f"wide_daily: {wide.height} days x {wide.width} cols")
    print(f"date range: {wide['date'].min()} .. {wide['date'].max()}")
    print()
    rate_df = _fill_rates(wide)
    empty = rate_df.filter(pl.col("filled") == 0)
    print(f"Empty columns ({empty.height}): {empty['column'].to_list()}")
    print()
    print("== Fill rate (non-empty columns, lowest 30) ==")
    print(rate_df.filter(pl.col("filled") > 0).head(30))
    print()
    print("== Fill rate (non-empty columns, highest 30) ==")
    print(rate_df.filter(pl.col("filled") > 0).tail(30))
    print()
    if log_df.height > 0:
        print("== Cleaning log ==")
        print(log_df.sort("n", descending=True))
    else:
        print("Cleaning log: empty")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build wide_daily.parquet from raw snapshot")
    parser.add_argument("--snapshot", type=str, default=None)
    args = parser.parse_args()

    base = snapshot_path(args.snapshot)
    out_dir = base / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Snapshot: {base.name}")
    print()

    wide, log_df = build_wide_daily(args.snapshot)
    source_starts = _detect_source_starts(args.snapshot)
    raw_epochs = _build_epochs(source_starts)
    logical_sources = _build_logical_sources(source_starts)
    logical_epochs = _build_logical_epochs(logical_sources)
    epochs_payload = {
        "raw_sources": source_starts,
        "raw_epochs": raw_epochs,
        "logical_sources": logical_sources,
        "logical_epochs": logical_epochs,
    }

    wide.write_parquet(out_dir / "wide_daily.parquet", compression="zstd")
    log_df.write_parquet(out_dir / "cleaning_log.parquet", compression="zstd")
    (out_dir / "epochs.json").write_text(json.dumps(epochs_payload, indent=2))
    print(f"Wrote {out_dir / 'wide_daily.parquet'}")
    print(f"Wrote {out_dir / 'cleaning_log.parquet'}")
    print(f"Wrote {out_dir / 'epochs.json'}")
    print()
    _print_summary(wide, log_df)
    print()
    print(f"== Logical epochs ({len(logical_epochs)}) ==")
    seen_logical: set[str] = set()
    for e in logical_epochs:
        new_sources = sorted(set(e["active"]) - seen_logical)
        seen_logical.update(e["active"])
        print(f"  epoch {e['epoch']} from {e['start']}: {len(e['active'])} active (+{len(new_sources)} new)")
        for s in new_sources:
            print(f"    + {s}")


if __name__ == "__main__":
    main()
