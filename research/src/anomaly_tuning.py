import argparse
from pathlib import Path

import numpy as np
import polars as pl
from scipy.stats import rankdata
from sklearn.ensemble import IsolationForest

from src.loader import load, snapshot_path, wide_daily

DEFAULT_FEATURES = [
    "total_sleep_min",
    "deep_sleep_min",
    "rem_sleep_min",
    "hrv_garmin",
    "resting_hr",
    "weight_kg",
    "total_steps",
    "active_energy",
    "avg_stress",
    "training_load_garmin",
    "strain_whoop",
]


def _build_feature_matrix(
    snapshot: str | None,
    features: list[str],
    coverage_threshold: float,
    date_from: str | None,
) -> tuple[np.ndarray, list, list[str]]:
    df = wide_daily(snapshot)
    available = [c for c in features if c in df.columns]
    cols = ["date", "coverage_pct", "n_sources_active", *available]
    selected = df.select(cols)

    if date_from:
        selected = selected.filter(pl.col("date") >= pl.lit(date_from).str.to_date())

    feature_cov = pl.sum_horizontal([pl.col(c).is_not_null().cast(pl.Int32) for c in available]) / len(available)
    selected = selected.with_columns(feature_cov.alias("_feature_cov"))
    selected = selected.filter(pl.col("_feature_cov") >= coverage_threshold)

    pdf = selected.select(available).to_pandas()
    medians = pdf.median(numeric_only=True)
    imputed = pdf.fillna(medians)
    return imputed.values, selected["date"].to_list(), available


def _contamination_sweep(X: np.ndarray, levels: list[float], random_state: int) -> dict[float, dict]:
    results: dict[float, dict] = {}
    for cont in levels:
        model = IsolationForest(n_estimators=200, contamination=cont, random_state=random_state)
        model.fit(X)
        raw = -model.decision_function(X)
        scores = rankdata(raw) / len(raw)
        n_anomalies = int((scores > (1 - cont)).sum())
        results[cont] = {"scores": scores, "n_anomalies": n_anomalies}
    return results


def _contributing_factors(
    X: np.ndarray,
    scores: np.ndarray,
    threshold: float,
    dates: list,
    cols: list[str],
) -> pl.DataFrame:
    mask = scores > threshold
    indices = np.nonzero(mask)[0]
    if len(indices) == 0:
        return pl.DataFrame()
    means = X.mean(axis=0)
    stds = X.std(axis=0)
    stds[stds == 0] = 1
    rows = []
    for idx in indices:
        z = (X[idx] - means) / stds
        order = np.argsort(np.abs(z))[::-1]
        top = {cols[i]: round(float(z[i]), 2) for i in order[:3]}
        keys = list(top.keys())
        vals = list(top.values())
        rows.append(
            {
                "date": str(dates[idx]),
                "score": round(float(scores[idx]), 3),
                "top_factor_1": keys[0] if keys else None,
                "top_factor_1_z": vals[0] if vals else None,
                "top_factor_2": keys[1] if len(keys) > 1 else None,
                "top_factor_2_z": vals[1] if len(vals) > 1 else None,
                "top_factor_3": keys[2] if len(keys) > 2 else None,
                "top_factor_3_z": vals[2] if len(vals) > 2 else None,
            }
        )
    return pl.DataFrame(rows)


def _compare_with_prod(local_dates: set[str], snapshot: str | None) -> None:
    try:
        prod = load("_prod_anomalies", snapshot)
    except FileNotFoundError:
        print("  no _prod_anomalies snapshot")
        return
    if prod.height == 0:
        print("  prod anomalies table empty")
        return
    prod_dates = set(prod["date"].cast(pl.Utf8).to_list())
    overlap = local_dates & prod_dates
    print(f"  prod={len(prod_dates)} local={len(local_dates)} overlap={len(overlap)}")
    print(f"  local-only: {len(local_dates - prod_dates)}")
    print(f"  prod-only: {len(prod_dates - local_dates)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Anomaly detection sweep on wide_daily")
    parser.add_argument("--snapshot", type=str, default=None)
    parser.add_argument("--contamination", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--features", type=str, default=None, help="Comma-separated")
    parser.add_argument("--coverage", type=float, default=0.5, help="Min feature coverage (0-1)")
    parser.add_argument("--date-from", type=str, default=None, help="YYYY-MM-DD")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()

    features = [f.strip() for f in args.features.split(",")] if args.features else DEFAULT_FEATURES
    X, dates, used_cols = _build_feature_matrix(args.snapshot, features, args.coverage, args.date_from)
    if X.shape[0] == 0:
        raise SystemExit(
            f"No rows with feature_coverage >= {args.coverage} (consider lowering --coverage or fewer --features)"
        )
    print(f"Feature matrix: {X.shape[0]} days x {X.shape[1]} cols")
    print(f"Features: {used_cols}")
    print(f"Effective date range: {dates[0]} .. {dates[-1]}")
    print(f"Coverage threshold: >={args.coverage}, NaN imputed with column median")
    print()

    levels = sorted({0.01, 0.03, 0.05, 0.07, 0.10, args.contamination})
    print(f"== Contamination sweep ({levels}) ==")
    results = _contamination_sweep(X, levels, args.seed)
    sweep_rows = [{"contamination": c, "n_anomalies": r["n_anomalies"]} for c, r in results.items()]
    print(pl.DataFrame(sweep_rows))

    cont = args.contamination
    scores = results[cont]["scores"]
    threshold = 1 - cont
    contributing = _contributing_factors(X, scores, threshold, dates, used_cols)

    print()
    print(f"== Anomalies at contamination={cont} ({contributing.height} dates) ==")
    if contributing.height > 0:
        print(contributing.tail(20))

    print()
    print("== Compare with production anomalies ==")
    local_dates = {row["date"] for row in contributing.iter_rows(named=True)}
    _compare_with_prod(local_dates, args.snapshot)

    if args.save:
        out_dir: Path = snapshot_path(args.snapshot) / "processed" / "analysis"
        out_dir.mkdir(parents=True, exist_ok=True)
        sweep_df = pl.DataFrame(sweep_rows)
        sweep_df.write_parquet(out_dir / "anomaly_sweep.parquet", compression="zstd")
        if contributing.height > 0:
            contributing.write_parquet(out_dir / f"anomalies_c{cont}.parquet", compression="zstd")
        print()
        print(f"  saved to {out_dir}")


if __name__ == "__main__":
    main()
