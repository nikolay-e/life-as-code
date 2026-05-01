import argparse
import math
import os

import polars as pl
from dotenv import load_dotenv

from src.loader import snapshot_path, wide_daily

load_dotenv()

# Canonical aliases: human-readable name → actual wide_daily column.
# Tests/scripts resolve through this registry instead of hardcoding raw column names.
# When schema changes, update here once.
CANONICAL_ALIASES: dict[str, str] = {
    # Training load (BLOCKED — source data null, see RESULTS.md Phase 0 TODO)
    "acute_training_load": "gts_acute_training_load_garmin_training",
    "training_load_7d": "gts_training_load_7_day_garmin_training",
    # HRV
    "hrv_garmin": "hrv_garmin",
    "hrv_whoop_rmssd": "hrv_whoop_rmssd",
    # Heart rate / body
    "resting_hr": "resting_hr",
    "weight_kg": "weight_kg",
    "body_fat_pct": "body_fat_pct",
    # Sleep
    "total_sleep_min": "total_sleep_min",
    "deep_sleep_min": "deep_sleep_min",
    "rem_sleep_min": "rem_sleep_min",
    "sleep_need_debt_whoop": "wsleep_sleep_need_debt_minutes_whoop",
    # Activity / load
    "total_steps": "total_steps",
    "active_energy": "active_energy",
    "avg_stress": "avg_stress",
    "strain_whoop": "strain_whoop",
    # Respiratory rate (5 sources actually present in wide_daily)
    "rr_whoop_sleep": "sleep_respiratory_rate_whoop",
    "rr_eight_sleep": "sleep_respiratory_rate_eight_sleep",
    "rr_google_sleep": "sleep_respiratory_rate_google",
    "rr_garmin_waking": "hr_waking_respiratory_rate_garmin",
    "rr_garmin_lowest": "hr_lowest_respiratory_rate_garmin",
    "rr_garmin_highest": "hr_highest_respiratory_rate_garmin",
    # Composites (DO NOT use as HRV predictors — tautological)
    "vo2_max": "vo2_max",  # also blocked (null in source)
    "recovery_score_whoop": "recovery_score_whoop",
    "training_load_garmin": "training_load_garmin",
    "readiness_garmin": "readiness_garmin",
    "strength_volume_kg": "strength_volume_kg",
    "sleep_score": "sleep_score",
    "max_hr": "max_hr",
    "light_sleep_min": "light_sleep_min",
}


# Source onset epochs — used for epoch dummies + epoch discontinuity detection.
# Configure per user via .env (which is gitignored). See .env.example for the template.
# All values are ISO dates (YYYY-MM-DD) or empty if the source is not used.
def _epoch(env_var: str, default: str = "") -> str:
    return os.environ.get(env_var, default).strip()


SOURCE_EPOCHS: dict[str, str] = {
    name: date
    for name, date in {
        "google_fit": _epoch("LAC_GOOGLE_FIT_EPOCH"),
        "apple_health": _epoch("LAC_APPLE_HEALTH_EPOCH"),
        "hevy": _epoch("LAC_HEVY_EPOCH"),
        "garmin_watch": _epoch("LAC_GARMIN_EPOCH"),
        "whoop_band": _epoch("LAC_WHOOP_EPOCH"),
        "eight_sleep": _epoch("LAC_EIGHT_SLEEP_EPOCH"),
    }.items()
    if date
}

# Multi-source epoch boundary dates for residualization dummies.
# Order matters: oldest first. Empty entries dropped automatically.
EPOCH_BOUNDARY_DATES: list[str] = [
    d
    for d in [
        _epoch("LAC_GARMIN_EPOCH"),
        _epoch("LAC_WHOOP_EPOCH"),
        _epoch("LAC_EIGHT_SLEEP_EPOCH"),
    ]
    if d
]


def resolve_column(canonical_name: str) -> str:
    return CANONICAL_ALIASES.get(canonical_name, canonical_name)


# Metrics that get derived feature columns (rolling means/std, z-scores, diff).
FEATURE_METRICS = [
    "total_sleep_min",
    "deep_sleep_min",
    "rem_sleep_min",
    "light_sleep_min",
    "sleep_score",
    "hrv_garmin",
    "hrv_whoop_rmssd",
    "resting_hr",
    "max_hr",
    "weight_kg",
    "body_fat_pct",
    "total_steps",
    "active_energy",
    "avg_stress",
    "vo2_max",
    "recovery_score_whoop",
    "strain_whoop",
    "training_load_garmin",
    "readiness_garmin",
    "strength_volume_kg",
]

# Multi-scale rolling: 7d (acute), 14d (training-load tertiles), 28d (default), 90d (chronic).
ROLLING_WINDOWS = (7, 14, 28, 90)

# Metrics that need first-difference (non-stationary per Phase 0)
DIFF_METRICS = ("hrv_garmin", "weight_kg", "active_energy")


def _ensure_continuous_dates(df: pl.DataFrame) -> pl.DataFrame:
    if df.height == 0:
        return df
    full = pl.DataFrame({"date": pl.date_range(df["date"].min(), df["date"].max(), interval="1d", eager=True)})
    return full.join(df, on="date", how="left").sort("date")


def _add_features(df: pl.DataFrame, metrics: list[str]) -> pl.DataFrame:
    available = [m for m in metrics if m in df.columns]

    # Rolling mean/std for each window (trailing only).
    out_cols: list[pl.Expr] = []
    for metric in available:
        out_cols.append(pl.col(metric).diff().alias(f"{metric}_diff"))
        out_cols.append(pl.col(metric).diff().alias(f"{metric}_delta_1d"))  # legacy alias
        for win in ROLLING_WINDOWS:
            min_p = max(2, math.ceil(win * 0.6))
            out_cols.append(
                pl.col(metric).rolling_mean(window_size=win, min_samples=min_p).alias(f"{metric}_roll{win}_mean")
            )
            out_cols.append(
                pl.col(metric).rolling_std(window_size=win, min_samples=min_p).alias(f"{metric}_roll{win}_std")
            )

    enriched = df.with_columns(out_cols)

    # z-scores per window: (x - rolling_mean) / rolling_std. If std==0 → 0.
    z_cols: list[pl.Expr] = []
    for metric in available:
        for win in ROLLING_WINDOWS:
            mean_col = f"{metric}_roll{win}_mean"
            std_col = f"{metric}_roll{win}_std"
            z_cols.append(
                pl.when(pl.col(std_col) > 1e-9)
                .then((pl.col(metric) - pl.col(mean_col)) / pl.col(std_col))
                .otherwise(0.0)
                .alias(f"{metric}_z{win}")
            )
    return enriched.with_columns(z_cols)


def _add_temporal_and_epoch(df: pl.DataFrame) -> pl.DataFrame:
    epoch_expr = pl.lit(0)
    for boundary in EPOCH_BOUNDARY_DATES:
        epoch_expr = epoch_expr + (pl.col("date") >= pl.lit(boundary).str.to_date()).cast(pl.Int32)
    return df.with_columns(
        pl.col("date").dt.weekday().alias("weekday"),
        pl.col("date").dt.month().alias("month"),
        epoch_expr.alias("epoch_id"),
    )


def build_features(snapshot: str | None) -> pl.DataFrame:
    wide = wide_daily(snapshot)
    per_source_cov = [
        c for c in wide.columns if c.startswith("coverage_") and c.endswith("_pct") and c != "coverage_pct"
    ]
    keep_cols = [
        "date",
        "coverage_pct",
        "n_sources_active",
        "sources_active",
        *per_source_cov,
        *[m for m in FEATURE_METRICS if m in wide.columns],
    ]
    base = wide.select(keep_cols).pipe(_ensure_continuous_dates)
    base = _add_temporal_and_epoch(base)
    return _add_features(base, FEATURE_METRICS).sort("date")


def _print_summary(features: pl.DataFrame) -> None:
    print(f"wide_daily_features: {features.height} days x {features.width} cols")
    print(f"date range: {features['date'].min()} .. {features['date'].max()}")
    print()
    feature_cols = [c for c in features.columns if c.endswith(("_z7", "_z28", "_z90", "_diff"))]
    print(f"Derived feature columns: {len(feature_cols)}")
    print()
    print("== Sample (last 7 days, key metrics) ==")
    sample_cols = [
        "date",
        "hrv_garmin",
        "hrv_garmin_z28",
        "hrv_garmin_z90",
        "hrv_garmin_diff",
        "weight_kg_diff",
        "epoch_id",
    ]
    available = [c for c in sample_cols if c in features.columns]
    print(features.select(available).tail(7))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build wide_daily_features.parquet (rolling means, deltas, z-scores, epoch_id)"
    )
    parser.add_argument("--snapshot", type=str, default=None)
    args = parser.parse_args()

    base = snapshot_path(args.snapshot)
    out_dir = base / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Snapshot: {base.name}")
    print()

    features = build_features(args.snapshot)
    out_path = out_dir / "wide_daily_features.parquet"
    features.write_parquet(out_path, compression="zstd")
    print(f"Wrote {out_path}")
    print()
    _print_summary(features)


if __name__ == "__main__":
    main()
