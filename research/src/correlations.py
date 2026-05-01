import argparse
from pathlib import Path
from typing import cast

import polars as pl
from scipy import stats
from statsmodels.stats.multitest import multipletests

from src.loader import snapshot_path, wide_daily, wide_daily_features

NUMERIC_DTYPES = (pl.Float32, pl.Float64, pl.Int32, pl.Int64)

CORE_METRICS = [
    "total_sleep_min",
    "deep_sleep_min",
    "rem_sleep_min",
    "light_sleep_min",
    "sleep_score",
    "hrv_garmin",
    "hrv_whoop_rmssd",
    "resting_hr",
    "max_hr",
    "avg_stress",
    "total_steps",
    "active_energy",
    "weight_kg",
    "body_fat_pct",
    "vo2_max",
    "recovery_score_whoop",
    "strain_whoop",
    "training_load_garmin",
    "readiness_garmin",
    "strength_volume_kg",
]


def _correlation_matrix(df: pl.DataFrame, cols: list[str]) -> pl.DataFrame:
    available = [c for c in cols if c in df.columns and df[c].dtype in NUMERIC_DTYPES]
    if not available:
        return pl.DataFrame()
    corr = df.select(available).to_pandas().corr().round(3).reset_index()
    corr.columns = ["metric", *corr.columns[1:]]
    return pl.from_pandas(corr)


def _next_day_lag(df: pl.DataFrame, feature: str, target: str) -> tuple[float, float, int] | None:
    if feature not in df.columns or target not in df.columns:
        return None
    paired = df.filter(pl.col(feature).is_not_null() & pl.col(target).is_not_null()).sort("date")
    if paired.height <= 14:
        return None
    feat = paired[feature].to_list()[:-1]
    tgt = paired[target].to_list()[1:]
    r, p = cast(tuple[float, float], stats.pearsonr(feat, tgt))
    return r, p, len(feat)


def _multi_lag_sweep(df: pl.DataFrame, target: str, features: list[str], max_lag: int) -> pl.DataFrame:
    rows = []
    if target not in df.columns:
        return pl.DataFrame()
    for feat in features:
        if feat not in df.columns:
            continue
        paired = df.filter(pl.col(feat).is_not_null() & pl.col(target).is_not_null()).sort("date")
        if paired.height < 14:
            continue
        feat_vals = paired[feat].to_list()
        target_vals = paired[target].to_list()
        for lag in range(max_lag + 1):
            n = len(feat_vals) - lag
            if n < 14:
                continue
            x = feat_vals[:n]
            y = target_vals[lag : lag + n]
            r, p = cast(tuple[float, float], stats.pearsonr(x, y))
            rows.append(
                {
                    "feature": feat,
                    "target": target,
                    "lag_days": lag,
                    "n": n,
                    "r": round(r, 3),
                    "p": p,
                }
            )
    if not rows:
        return pl.DataFrame()
    df_out = pl.DataFrame(rows)
    pvals = df_out["p"].to_list()
    _, p_bonf, _, _ = multipletests(pvals, alpha=0.05, method="bonferroni")
    _, p_fdr, _, _ = multipletests(pvals, alpha=0.05, method="fdr_bh")
    return df_out.with_columns(
        pl.Series("p_bonferroni", p_bonf).round(5),
        pl.Series("p_fdr", p_fdr).round(5),
        pl.col("p").round(5),
    )


def _day_of_week(df: pl.DataFrame, metrics: list[str]) -> pl.DataFrame:
    enriched = df.with_columns(pl.col("date").cast(pl.Date).dt.weekday().alias("weekday"))
    rows = []
    for metric in metrics:
        if metric not in enriched.columns:
            continue
        agg = (
            enriched.filter(pl.col(metric).is_not_null())
            .group_by("weekday")
            .agg(
                pl.col(metric).mean().alias("mean"),
                pl.col(metric).std().alias("std"),
                pl.col(metric).count().alias("n"),
            )
            .sort("weekday")
        )
        for row in agg.iter_rows(named=True):
            rows.append({"metric": metric, **row})
    return pl.DataFrame(rows)


def _save(df: pl.DataFrame, path: Path) -> None:
    if df.is_empty():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path, compression="zstd")
    print(f"  wrote {path}")


def _effective_range(df: pl.DataFrame, cols: list[str]) -> tuple[str, str, int]:
    available = [c for c in cols if c in df.columns]
    if not available:
        return ("none", "none", 0)
    sub = df.filter(pl.all_horizontal([pl.col(c).is_not_null() for c in available]))
    if sub.height == 0:
        return ("none", "none", 0)
    return (str(sub["date"].min()), str(sub["date"].max()), sub.height)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-metric correlation report")
    parser.add_argument("--snapshot", type=str, default=None)
    parser.add_argument("--target", type=str, default="hrv_garmin")
    parser.add_argument("--max-lag", type=int, default=7)
    parser.add_argument("--date-from", type=str, default=None, help="YYYY-MM-DD")
    parser.add_argument(
        "--detrend",
        action="store_true",
        help="Use _z28 detrended versions from wide_daily_features (removes trend confound)",
    )
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()

    if args.detrend:
        feat = wide_daily_features(args.snapshot)
        z_cols = {c.replace("_z28", ""): c for c in feat.columns if c.endswith("_z28")}
        rename_map = {z_cols[k]: k for k in z_cols}
        df = feat.select(["date", *list(z_cols.values())]).rename(rename_map)
        print("DETRENDED mode: using _z28 columns from wide_daily_features")
    else:
        df = wide_daily(args.snapshot)
    if args.date_from:
        df = df.filter(pl.col("date") >= pl.lit(args.date_from).str.to_date())
    print(f"data: {df.height} days x {df.width} cols")
    print(f"date range: {df['date'].min()} .. {df['date'].max()}")
    print()

    print("== Correlation matrix (core metrics) ==")
    corr = _correlation_matrix(df, CORE_METRICS)
    print(corr)
    print()

    s_start, s_end, s_n = _effective_range(df, ["total_sleep_min", args.target])
    print(f"== Sleep -> next-day {args.target} (effective: {s_start}..{s_end}, n={s_n}) ==")
    lag_result = _next_day_lag(df, "total_sleep_min", args.target)
    if lag_result:
        r, p, n = lag_result
        print(f"  n_pairs={n}, r={r:.3f}, p={p:.4f}")
    else:
        print("  insufficient data")
    print()

    features = [
        "total_sleep_min",
        "deep_sleep_min",
        "total_steps",
        "avg_stress",
        "active_energy",
        "strain_whoop",
        "training_load_garmin",
    ]
    print(f"== Multi-lag sweep -> {args.target} (lag 0..{args.max_lag}) ==")
    lag_df = _multi_lag_sweep(df, args.target, features, args.max_lag)
    if lag_df.height > 0:
        n_tests = lag_df.height
        bonf_survivors = lag_df.filter(pl.col("p_bonferroni") < 0.05).height
        fdr_survivors = lag_df.filter(pl.col("p_fdr") < 0.05).height
        print(f"  n_tests={n_tests}, bonferroni_survivors_0.05={bonf_survivors}, fdr_survivors_0.05={fdr_survivors}")
        print(lag_df.sort(["feature", "lag_days"]))
        print()
        print("  Top correlations passing FDR<0.05 (sorted by |r|):")
        sig = (
            lag_df.filter(pl.col("p_fdr") < 0.05)
            .with_columns(pl.col("r").abs().alias("abs_r"))
            .sort("abs_r", descending=True)
            .drop("abs_r")
        )
        print(sig.head(10))
    else:
        print("  no overlap")
    print()

    print("== Day-of-week patterns ==")
    dow_df = _day_of_week(df, ["total_sleep_min", "hrv_garmin", "total_steps"])
    print(dow_df)

    if args.save:
        out_dir = snapshot_path(args.snapshot) / "processed" / "analysis"
        print()
        print("== Saving outputs ==")
        _save(corr, out_dir / "correlation_matrix.parquet")
        _save(lag_df, out_dir / "lag_sweep.parquet")
        _save(dow_df, out_dir / "day_of_week.parquet")


if __name__ == "__main__":
    main()
