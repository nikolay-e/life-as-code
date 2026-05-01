import argparse
import json

import numpy as np
import polars as pl
from scipy import stats
from scipy.stats import norm
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import acf, adfuller, kpss, pacf

from src.features import EPOCH_BOUNDARY_DATES
from src.loader import snapshot_path, wide_daily

CORE_METRICS = [
    "total_sleep_min",
    "deep_sleep_min",
    "rem_sleep_min",
    "hrv_garmin",
    "hrv_whoop_rmssd",
    "resting_hr",
    "total_steps",
    "active_energy",
    "weight_kg",
    "strain_whoop",
    "training_load_garmin",
]


def _series_with_dates(df: pl.DataFrame, metric: str) -> pl.DataFrame:
    if metric not in df.columns:
        return pl.DataFrame()
    sub = df.select(["date", metric]).filter(pl.col(metric).is_not_null()).sort("date")
    return sub


def _acf_pacf(values: np.ndarray, n_lags: int) -> tuple[np.ndarray, np.ndarray]:
    n_lags = min(n_lags, max(1, len(values) // 4))
    a = acf(values, nlags=n_lags, fft=False)
    p = pacf(values, nlags=n_lags, method="ols")
    return a, p


def _stationarity(values: np.ndarray) -> dict:
    if len(values) < 30:
        return {"adf_p": None, "kpss_p": None, "verdict": "insufficient_data"}
    try:
        _, adf_p, *_ = adfuller(values, autolag="AIC")
    except Exception:
        adf_p = None
    try:
        _, kpss_p, *_ = kpss(values, regression="c", nlags="auto")
    except Exception:
        kpss_p = None

    if adf_p is None or kpss_p is None:
        verdict = "test_failed"
    elif adf_p < 0.05 and kpss_p > 0.05:
        verdict = "stationary"
    elif adf_p >= 0.05 and kpss_p <= 0.05:
        verdict = "non_stationary"
    elif adf_p < 0.05 and kpss_p <= 0.05:
        verdict = "trend_stationary_or_difference_stationary"
    else:
        verdict = "inconclusive"
    return {
        "adf_p": float(adf_p) if adf_p is not None else None,
        "kpss_p": float(kpss_p) if kpss_p is not None else None,
        "verdict": verdict,
    }


def _ljung_box(values: np.ndarray, lags: int = 10) -> float | None:
    if len(values) < lags + 5:
        return None
    try:
        result = acorr_ljungbox(values, lags=[lags], return_df=True)
        return float(result["lb_pvalue"].iloc[0])
    except Exception:
        return None


def _effective_n(n: int, rho1: float) -> int:
    rho1 = max(min(rho1, 0.999), -0.999)
    factor = (1 - rho1) / (1 + rho1)
    return max(1, int(round(n * factor)))


def _power_for_r(n_eff: int, r: float, alpha: float = 0.05) -> float:
    if n_eff < 4 or abs(r) < 1e-6:
        return 0.0
    z_r = 0.5 * np.log((1 + abs(r)) / (1 - abs(r)))
    se = 1.0 / np.sqrt(n_eff - 3)
    z_alpha = float(norm.ppf(1 - alpha / 2))
    power = 1 - float(norm.cdf(z_alpha - z_r / se)) + float(norm.cdf(-z_alpha - z_r / se))
    return float(np.clip(power, 0.0, 1.0))


def _dow_month_anova(df: pl.DataFrame, metric: str, has_epoch: bool = True) -> dict:
    if metric not in df.columns:
        return {}
    sub = df.select(["date", metric]).filter(pl.col(metric).is_not_null())
    if sub.height < 30:
        return {"n": sub.height, "skipped": "too_few"}

    enriched = sub.with_columns(
        pl.col("date").dt.weekday().alias("weekday"),
        pl.col("date").dt.month().alias("month"),
        pl.col("date").dt.year().alias("year"),
    )

    pdf = enriched.to_pandas()
    y = pdf[metric].astype(float).values
    total_var = float(np.var(y, ddof=0))
    if total_var < 1e-12:
        return {"n": int(len(y)), "skipped": "constant"}

    out: dict = {"n": int(len(y))}
    for factor in ["weekday", "month"]:
        groups = pdf.groupby(factor)[metric].mean()
        overall = float(np.mean(y))
        between_ss = float(
            sum(pdf.groupby(factor)[metric].count()[g] * (groups[g] - overall) ** 2 for g in groups.index)
        )
        eta_sq = between_ss / (total_var * len(y))
        out[f"eta_sq_{factor}"] = round(eta_sq, 4)
        out[f"unique_{factor}"] = int(pdf[factor].nunique())
    return out


def analyze_metric(df: pl.DataFrame, metric: str, lags: int = 14) -> dict:
    sub = _series_with_dates(df, metric)
    if sub.height < 30:
        return {"metric": metric, "n": sub.height, "skipped": "too_few"}

    values = sub[metric].to_numpy().astype(float)
    n = len(values)

    a, p = _acf_pacf(values, lags)
    rho1 = float(a[1]) if len(a) > 1 else 0.0
    rho7 = float(a[7]) if len(a) > 7 else 0.0
    n_eff = _effective_n(n, rho1)

    stat = _stationarity(values)
    lb_p = _ljung_box(values, lags=10)
    anova = _dow_month_anova(df, metric)

    return {
        "metric": metric,
        "n": n,
        "date_min": str(sub["date"].min()),
        "date_max": str(sub["date"].max()),
        "rho1": round(rho1, 3),
        "rho7": round(rho7, 3),
        "n_effective": n_eff,
        "adf_p": stat["adf_p"],
        "kpss_p": stat["kpss_p"],
        "stationarity": stat["verdict"],
        "ljung_box_p_lag10": lb_p,
        "eta_sq_weekday": anova.get("eta_sq_weekday"),
        "eta_sq_month": anova.get("eta_sq_month"),
        "power_r_0.10": round(_power_for_r(n_eff, 0.10), 3),
        "power_r_0.15": round(_power_for_r(n_eff, 0.15), 3),
        "power_r_0.20": round(_power_for_r(n_eff, 0.20), 3),
    }


METRIC_CONFOUNDS = {
    "total_sleep_min": {"month": False, "weekday": False},
    "deep_sleep_min": {"month": True, "weekday": False},
    "rem_sleep_min": {"month": False, "weekday": False},
    "hrv_garmin": {"month": True, "weekday": False},
    "hrv_whoop_rmssd": {"month": True, "weekday": True},
    "resting_hr": {"month": True, "weekday": False},
    "total_steps": {"month": False, "weekday": True},
    "active_energy": {"month": False, "weekday": False},
    "weight_kg": {"month": True, "weekday": False},
    "strain_whoop": {"month": True, "weekday": False},
}


def compute_residualized_acf(
    df: pl.DataFrame,
    metric_col: str,
    include_month: bool,
    include_weekday: bool,
    include_epoch: bool = True,
    epoch_dates: list[str] | None = None,
    max_lag: int = 21,
) -> dict:
    work = df.filter(pl.col(metric_col).is_not_null()).sort("date")
    if work.height < 30:
        return {"metric": metric_col, "skipped": "too_few", "n_raw": work.height}

    y = work[metric_col].to_numpy().astype(float)
    n = len(y)

    confounds: list[str] = []
    X_parts: list[np.ndarray] = []

    if include_month:
        m = work["date"].dt.month().to_numpy()
        dummies = np.zeros((n, 11))
        for i, mi in enumerate(m):
            if mi > 1:
                dummies[i, mi - 2] = 1
        X_parts.append(dummies)
        confounds.append("month")

    if include_weekday:
        wd = work["date"].dt.weekday().to_numpy()
        dummies = np.zeros((n, 6))
        for i, wi in enumerate(wd):
            if wi > 1:
                dummies[i, wi - 2] = 1
        X_parts.append(dummies)
        confounds.append("weekday")

    if include_epoch and epoch_dates:
        dates = work["date"].to_numpy()
        epoch_ids = np.zeros(n, dtype=int)
        for boundary in sorted(np.datetime64(d) for d in epoch_dates):
            epoch_ids[dates >= boundary] += 1
        n_epochs = int(epoch_ids.max())
        if n_epochs > 0:
            dummies = np.zeros((n, n_epochs))
            for i, e in enumerate(epoch_ids):
                if e > 0:
                    dummies[i, e - 1] = 1
            X_parts.append(dummies)
            confounds.append("epoch")

    if X_parts:
        X = np.column_stack([np.ones(n)] + X_parts)
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        residuals = y - X @ beta
    else:
        residuals = y - np.mean(y)

    a = acf(residuals, nlags=min(max_lag, n // 4), fft=True)

    rho1 = float(a[1]) if len(a) > 1 else 0.0
    rho7 = float(a[7]) if len(a) > 7 else 0.0
    n_eff = _effective_n(n, rho1)

    lb_p = _ljung_box(residuals, lags=10)

    try:
        _, adf_p, *_ = adfuller(residuals, autolag="AIC")
    except Exception:
        adf_p = None
    try:
        _, kpss_p, *_ = kpss(residuals, regression="c", nlags="auto")
    except Exception:
        kpss_p = None

    return {
        "metric": metric_col,
        "n_raw": n,
        "confounds_removed": ",".join(confounds) or "none",
        "rho1": round(rho1, 3),
        "rho7": round(rho7, 3),
        "n_eff": n_eff,
        "ljung_box_p_lag10": lb_p,
        "adf_p_residuals": float(adf_p) if adf_p is not None else None,
        "kpss_p_residuals": float(kpss_p) if kpss_p is not None else None,
        "power_r_0.10": round(_power_for_r(n_eff, 0.10), 3),
        "power_r_0.15": round(_power_for_r(n_eff, 0.15), 3),
        "power_r_0.25": round(_power_for_r(n_eff, 0.25), 3),
    }


def detect_epoch_discontinuities(
    df: pl.DataFrame,
    metric_col: str,
    window: int = 28,
    step: int = 7,
    threshold_sigma: float = 1.0,
    p_threshold: float = 0.01,
    min_observations: int = 14,
) -> list[dict]:
    work = df.filter(pl.col(metric_col).is_not_null()).sort("date")
    dates = work["date"].to_numpy()
    values = work[metric_col].to_numpy().astype(float)
    n = len(values)
    if n < 2 * min_observations:
        return []

    out: list[dict] = []
    for i in range(window, n - window, step):
        left = values[max(0, i - window) : i]
        right = values[i : min(n, i + window)]
        if len(left) < min_observations or len(right) < min_observations:
            continue
        t_stat, p_value = stats.ttest_ind(left, right, equal_var=False)
        pooled_std = np.sqrt((np.var(left) + np.var(right)) / 2)
        if pooled_std == 0:
            continue
        diff_sigma = (np.mean(right) - np.mean(left)) / pooled_std
        if abs(diff_sigma) > threshold_sigma and p_value < p_threshold:
            out.append(
                {
                    "date": str(dates[i])[:10],
                    "metric": metric_col,
                    "mean_left": round(float(np.mean(left)), 2),
                    "mean_right": round(float(np.mean(right)), 2),
                    "diff_sigma": round(float(diff_sigma), 2),
                    "t_stat": round(float(t_stat), 2),
                    "p_value": float(p_value),
                }
            )

    if len(out) > 1:
        merged = [out[0]]
        for d in out[1:]:
            prev = np.datetime64(merged[-1]["date"])
            curr = np.datetime64(d["date"])
            if (curr - prev) < np.timedelta64(2 * step, "D"):
                if abs(d["diff_sigma"]) > abs(merged[-1]["diff_sigma"]):
                    merged[-1] = d
            else:
                merged.append(d)
        out = merged
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 0 calibration: ACF/PACF, ADF/KPSS, DOW+month ANOVA, effective-n, "
            "power, residualized ACF, epoch discontinuity"
        )
    )
    parser.add_argument("--snapshot", type=str, default=None)
    parser.add_argument("--metrics", type=str, default=None, help="Comma-separated")
    parser.add_argument("--lags", type=int, default=14)
    parser.add_argument(
        "--extended",
        action="store_true",
        help="Run residualized ACF + epoch discontinuity detection",
    )
    args = parser.parse_args()

    df = wide_daily(args.snapshot)
    metrics = [m.strip() for m in args.metrics.split(",")] if args.metrics else CORE_METRICS
    available = [m for m in metrics if m in df.columns]
    skipped = [m for m in metrics if m not in df.columns]

    print(f"Snapshot: {snapshot_path(args.snapshot).name}")
    print(f"Metrics: {len(available)} ({skipped=} skipped)")
    print()

    rows = [analyze_metric(df, m, args.lags) for m in available]
    report = pl.DataFrame(rows)

    out_dir = snapshot_path(args.snapshot) / "processed" / "baseline"
    out_dir.mkdir(parents=True, exist_ok=True)
    report.write_parquet(out_dir / "calibration_report.parquet", compression="zstd")

    summary = {
        "snapshot": snapshot_path(args.snapshot).name,
        "metrics_analyzed": available,
        "metrics_skipped": skipped,
        "n_metrics": len(available),
    }
    (out_dir / "calibration_summary.json").write_text(json.dumps(summary, indent=2))

    print("== Calibration report ==")
    print(report)
    print()
    print(f"Wrote {out_dir / 'calibration_report.parquet'}")
    print(f"Wrote {out_dir / 'calibration_summary.json'}")
    print()
    print("== Decision rules per H spec ==")
    for row in report.iter_rows(named=True):
        flags = []
        if row.get("eta_sq_weekday") is not None and row["eta_sq_weekday"] > 0.05:
            flags.append("DOW dummy required (η²>0.05)")
        if row.get("eta_sq_month") is not None and row["eta_sq_month"] > 0.03:
            flags.append("month dummy required (η²>0.03)")
        if row.get("stationarity") == "non_stationary":
            flags.append("first-difference required")
        if row.get("rho1") is not None and abs(row["rho1"]) > 0.3:
            flags.append(f"prewhitening required (rho1={row['rho1']})")
        power = row.get("power_r_0.10", 0)
        if power < 0.6:
            flags.append(f"underpowered for r=0.10 (power={power:.2f})")
        if flags:
            print(f"  {row['metric']}: {' | '.join(flags)}")

    if args.extended:
        print()
        print("== Residualized ACF (after month/DOW/epoch removal) ==")
        resid_rows = []
        for m in available:
            cf = METRIC_CONFOUNDS.get(m, {"month": True, "weekday": False})
            r = compute_residualized_acf(
                df,
                m,
                include_month=cf["month"],
                include_weekday=cf["weekday"],
                include_epoch=True,
                epoch_dates=EPOCH_BOUNDARY_DATES,
            )
            resid_rows.append(r)
        resid_df = pl.DataFrame([{k: v for k, v in r.items() if not isinstance(v, list)} for r in resid_rows])
        resid_df.write_parquet(out_dir / "residualized_acf.parquet", compression="zstd")
        print(resid_df)
        print(f"Wrote {out_dir / 'residualized_acf.parquet'}")

        print()
        print("== Epoch discontinuities (sliding Welch t-test, window=28d, step=7d, threshold 1σ + p<0.01) ==")
        disc_rows: list[dict] = []
        for m in available:
            disc_rows.extend(detect_epoch_discontinuities(df, m))
        if disc_rows:
            disc_df = pl.DataFrame(disc_rows).sort(["metric", "date"])
            disc_df.write_parquet(out_dir / "epoch_discontinuities.parquet", compression="zstd")
            print(disc_df)
            print(f"Wrote {out_dir / 'epoch_discontinuities.parquet'}")
        else:
            print("No discontinuities detected at threshold.")


if __name__ == "__main__":
    main()
