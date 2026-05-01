"""lac-test: hypothesis testing engine.

Reads HypothesisSpec from registry, applies correct method stack:
- prewhitened CCF (Box-Jenkins) for lag correlations
- ICC + Bland-Altman for measurement validation
- quadrant chi-square for categorical decoupling
- Kruskal-Wallis for DOW/month calibration
- partial correlation for nested controls

Output: processed/results/<HID>_result.json + RESULTS.md fragment.
"""

import argparse
import json
import math
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import numpy as np
import polars as pl
from scipy.stats import (
    chi2_contingency,
    fisher_exact,
    kruskal,
    pearsonr,
    spearmanr,
)
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.stats.multitest import multipletests
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import acf

from src.features import (
    EPOCH_BOUNDARY_DATES,
    SOURCE_EPOCHS,
    resolve_column,
)
from src.loader import snapshot_path, wide_daily, wide_daily_features


def _src_epoch(name: str) -> str | None:
    """Return ISO start date for a logical source, or None if not configured."""
    return SOURCE_EPOCHS.get(name) or None


# ── Specs ──────────────────────────────────────────────────────────────


class Method(Enum):
    PREWHITENED_CCF = "prewhitened_ccf"
    ICC_BLAND_ALTMAN = "icc_bland_altman"
    QUADRANT_CHI2 = "quadrant_chi2"
    KRUSKAL_WALLIS = "kruskal_wallis"
    PARTIAL_CORRELATION = "partial_corr"


class Tier(Enum):
    CONFIRMATORY = "confirmatory"
    EXPLORATORY = "exploratory"
    REPORT_ONLY = "report_only"
    BLOCKED = "blocked"


@dataclass
class ResidualizeSpec:
    month: bool = False
    weekday: bool = False
    epoch: bool = True


@dataclass
class AttenuationSpec:
    feature_reliability: float
    target_reliability: float

    @property
    def factor(self) -> float:
        return math.sqrt(self.feature_reliability * self.target_reliability)


@dataclass
class HypothesisSpec:
    id: str
    name: str
    tier: Tier
    method: Method
    feature: str = ""
    target: str = ""
    control_variables: list[str] = field(default_factory=list)
    feature_transform: str = "z_28"  # raw / z_7 / z_28 / z_90 / diff
    target_transform: str = "z_28"
    lags: list[int] = field(default_factory=lambda: [0])
    expected_direction: str = "any"  # positive / negative / any
    date_start: str | None = None
    date_end: str | None = None
    residualize: ResidualizeSpec = field(default_factory=ResidualizeSpec)
    attenuation: AttenuationSpec | None = None
    n_bootstrap: int = 2000
    fdr_q: float = 0.05
    confirmatory_r_threshold: float = 0.25
    extra: dict[str, Any] = field(default_factory=dict)


# ── Registry ───────────────────────────────────────────────────────────

CORE_METRICS_FOR_H10 = [
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
]

RR_PAIRS_FOR_H12 = [
    ("rr_whoop_sleep", "rr_eight_sleep"),
    ("rr_whoop_sleep", "rr_garmin_waking"),
    ("rr_eight_sleep", "rr_garmin_waking"),
    ("rr_whoop_sleep", "rr_google_sleep"),
    ("rr_garmin_waking", "rr_garmin_lowest"),
]

REGISTRY: dict[str, HypothesisSpec] = {
    "H10": HypothesisSpec(
        id="H10",
        name="DOW + Month Calibration",
        tier=Tier.CONFIRMATORY,
        method=Method.KRUSKAL_WALLIS,
        feature="weekday",
        target="all_core",
        residualize=ResidualizeSpec(month=False, weekday=False, epoch=False),
        extra={"metrics": CORE_METRICS_FOR_H10},
    ),
    "H12": HypothesisSpec(
        id="H12",
        name="RR Cross-Source Validation",
        tier=Tier.CONFIRMATORY,
        method=Method.ICC_BLAND_ALTMAN,
        feature="rr_whoop_sleep",
        target="rr_eight_sleep",
        date_start=_src_epoch("eight_sleep"),
        residualize=ResidualizeSpec(month=False, weekday=False, epoch=False),
        extra={"pairs": RR_PAIRS_FOR_H12},
    ),
    "H6": HypothesisSpec(
        id="H6",
        name="Sleep Debt → HRV (exploratory)",
        tier=Tier.EXPLORATORY,
        method=Method.PREWHITENED_CCF,
        feature="sleep_need_debt_whoop",
        target="hrv_whoop_rmssd",
        feature_transform="raw",
        target_transform="z_7",
        lags=[0, 1, 2, 3],
        expected_direction="negative",
        date_start=_src_epoch("whoop_band"),
        residualize=ResidualizeSpec(month=True, weekday=True, epoch=True),
        attenuation=AttenuationSpec(0.85, 0.78),
        fdr_q=0.10,
        confirmatory_r_threshold=0.28,
    ),
    "H2": HypothesisSpec(
        id="H2",
        name="Sleep Duration → HRV (exploratory)",
        tier=Tier.EXPLORATORY,
        method=Method.PREWHITENED_CCF,
        feature="total_sleep_min",
        target="hrv_garmin",
        feature_transform="z_28",
        target_transform="diff",
        lags=[0],
        expected_direction="positive",
        date_start=_src_epoch("garmin_watch"),
        residualize=ResidualizeSpec(month=True, weekday=False, epoch=True),
        attenuation=AttenuationSpec(0.85, 0.73),
        fdr_q=0.10,
        confirmatory_r_threshold=0.25,
    ),
    "H14": HypothesisSpec(
        id="H14",
        name="RHR-HRV Decoupling (exploratory)",
        tier=Tier.EXPLORATORY,
        method=Method.QUADRANT_CHI2,
        feature="resting_hr",
        target="hrv_garmin",
        feature_transform="z_28",
        target_transform="z_28",
        date_start=_src_epoch("whoop_band"),  # Whoop strain available from this date for tertiles
        residualize=ResidualizeSpec(month=True, weekday=False, epoch=True),
        extra={"strain_col": "strain_whoop", "tertile_window_days": 14},
    ),
    "H3": HypothesisSpec(
        id="H3",
        name="Deep Sleep | Total → HRV (report-only)",
        tier=Tier.REPORT_ONLY,
        method=Method.PARTIAL_CORRELATION,
        feature="deep_sleep_min",
        target="hrv_garmin",
        control_variables=["total_sleep_min"],
        feature_transform="z_28",
        target_transform="diff",
        date_start=_src_epoch("garmin_watch"),
        residualize=ResidualizeSpec(month=True, weekday=False, epoch=True),
        attenuation=AttenuationSpec(0.50, 0.73),
    ),
    "H6_partial": HypothesisSpec(
        id="H6_partial",
        name="Sleep Debt → HRV | Total Sleep (redundancy check)",
        tier=Tier.EXPLORATORY,
        method=Method.PARTIAL_CORRELATION,
        feature="sleep_need_debt_whoop",
        target="hrv_whoop_rmssd",
        control_variables=["total_sleep_min"],
        feature_transform="raw",
        target_transform="z_7",
        date_start=_src_epoch("whoop_band"),
        residualize=ResidualizeSpec(month=True, weekday=True, epoch=True),
        attenuation=AttenuationSpec(0.85, 0.78),
    ),
    "H11": HypothesisSpec(
        id="H11",
        name="ATL → HRV (BLOCKED)",
        tier=Tier.BLOCKED,
        method=Method.PREWHITENED_CCF,
        feature="acute_training_load",
        target="hrv_garmin",
        feature_transform="z_28",
        target_transform="diff",
        lags=[1, 2, 3, 4, 5],
        expected_direction="negative",
        date_start=_src_epoch("garmin_watch"),
        residualize=ResidualizeSpec(month=True, weekday=False, epoch=True),
        attenuation=AttenuationSpec(0.80, 0.73),
    ),
}


# ── Data prep helpers ──────────────────────────────────────────────────


def _load_paired(
    feature_canonical: str,
    target_canonical: str,
    feature_transform: str,
    target_transform: str,
    date_start: str | None,
    date_end: str | None,
    snapshot: str | None,
) -> pl.DataFrame:
    feat_col = resolve_column(feature_canonical)
    tgt_col = resolve_column(target_canonical)

    feats = wide_daily_features(snapshot)
    raw = wide_daily(snapshot)

    feat_df = _get_transformed_df(feats, raw, feat_col, feature_transform, "feature")
    tgt_df = _get_transformed_df(feats, raw, tgt_col, target_transform, "target")
    df = (
        feat_df.join(tgt_df, on="date", how="inner")
        .filter(pl.col("feature").is_not_null() & pl.col("target").is_not_null())
        .sort("date")
    )

    if date_start:
        df = df.filter(pl.col("date") >= pl.lit(date_start).str.to_date())
    if date_end:
        df = df.filter(pl.col("date") <= pl.lit(date_end).str.to_date())
    return df


def _get_transformed_df(
    feats: pl.DataFrame, raw: pl.DataFrame, base_col: str, transform: str, alias: str
) -> pl.DataFrame:
    if transform == "raw":
        if base_col in feats.columns:
            return feats.select(["date", pl.col(base_col).alias(alias)])
        if base_col in raw.columns:
            return raw.select(["date", pl.col(base_col).alias(alias)])
        raise KeyError(f"Column {base_col} not found")
    suffix_map = {"z_7": "_z7", "z_28": "_z28", "z_90": "_z90", "diff": "_diff"}
    if transform not in suffix_map:
        raise ValueError(f"Unknown transform: {transform}")
    derived_col = f"{base_col}{suffix_map[transform]}"
    if derived_col not in feats.columns:
        raise KeyError(f"Derived column {derived_col} not in features. Run lac-features.")
    return feats.select(["date", pl.col(derived_col).alias(alias)])


def _residualize(df: pl.DataFrame, spec: ResidualizeSpec) -> pl.DataFrame:
    """Regress feature and target on month/DOW/epoch dummies; return residuals."""
    if not (spec.month or spec.weekday or spec.epoch):
        return df

    work = df.with_columns(
        pl.col("date").dt.month().alias("__month"),
        pl.col("date").dt.weekday().alias("__weekday"),
    )
    epoch_expr = pl.lit(0).cast(pl.Int64)
    for boundary in EPOCH_BOUNDARY_DATES:
        epoch_expr = epoch_expr + (pl.col("date") >= pl.lit(boundary).str.to_date()).cast(pl.Int64)
    work = work.with_columns(epoch_expr.alias("__epoch"))

    n = work.height
    parts: list[np.ndarray] = []
    if spec.month:
        m = work["__month"].to_numpy()
        d = np.zeros((n, 11))
        for i, mi in enumerate(m):
            if mi > 1:
                d[i, mi - 2] = 1
        parts.append(d)
    if spec.weekday:
        w = work["__weekday"].to_numpy()
        d = np.zeros((n, 6))
        for i, wi in enumerate(w):
            if wi > 1:
                d[i, wi - 2] = 1
        parts.append(d)
    if spec.epoch:
        e = work["__epoch"].to_numpy()
        n_epochs = int(e.max())
        if n_epochs > 0:
            d = np.zeros((n, n_epochs))
            for i, ei in enumerate(e):
                if ei > 0:
                    d[i, ei - 1] = 1
            parts.append(d)

    if not parts:
        return df

    X = np.column_stack([np.ones(n)] + parts)
    for col in ("feature", "target"):
        y = work[col].to_numpy().astype(float)
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        residuals = y - X @ beta
        work = work.with_columns(pl.Series(col, residuals))

    return work.drop(["__month", "__weekday", "__epoch"])


# ── Method: prewhitened CCF ────────────────────────────────────────────


def _fit_arima_simple(values: np.ndarray, max_p: int = 3, max_q: int = 2) -> tuple[ARIMA, tuple[int, int, int]]:
    """Grid search ARIMA(p,d,q) with d=0 (assumes input pre-detrended); pick min AIC."""
    best_aic = np.inf
    best_model = None
    best_order = (0, 0, 0)
    for p in range(max_p + 1):
        for q in range(max_q + 1):
            if p == 0 and q == 0:
                continue
            try:
                model = ARIMA(values, order=(p, 0, q)).fit(method_kwargs={"warn_convergence": False})
                if model.aic < best_aic:
                    best_aic = model.aic
                    best_model = model
                    best_order = (p, 0, q)
            except Exception:
                continue
    if best_model is None:
        # fallback: AR(1)
        best_model = ARIMA(values, order=(1, 0, 0)).fit()
        best_order = (1, 0, 0)
    return best_model, best_order


def _stationary_block_bootstrap_ccf(
    feat: np.ndarray,
    tgt: np.ndarray,
    lag: int,
    block_size: int,
    n_resamples: int,
    seed: int = 42,
) -> tuple[float, float, float, float]:
    """Returns (point_r, ci_low, ci_high, p_two_sided) for cross-correlation at lag k.
    Lag convention: positive lag k means tgt[t] correlated with feat[t-k] (feat leads).
    """
    rng = np.random.default_rng(seed)
    n = len(feat)
    if lag >= 0:
        x = feat[: n - lag]
        y = tgt[lag:]
    else:
        x = feat[-lag:]
        y = tgt[: n + lag]
    if len(x) < 14:
        return float("nan"), float("nan"), float("nan"), float("nan")
    point_r = float(pearsonr(x, y)[0])

    samples = []
    nx = len(x)
    for _ in range(n_resamples):
        starts = rng.integers(0, nx, size=int(np.ceil(nx / block_size)))
        idx = np.concatenate([np.arange(s, s + block_size) % nx for s in starts])[:nx]
        xs = x[idx]
        ys = y[idx]
        try:
            r = float(pearsonr(xs, ys)[0])
            samples.append(r)
        except Exception:
            continue
    if not samples:
        return point_r, float("nan"), float("nan"), float("nan")
    samples_arr = np.asarray(samples)
    ci_low = float(np.percentile(samples_arr, 2.5))
    ci_high = float(np.percentile(samples_arr, 97.5))
    # two-sided p from bootstrap distribution centered at 0
    centered = samples_arr - np.mean(samples_arr)
    p_two = float(np.mean(np.abs(centered) >= abs(point_r)))
    p_two = max(p_two, 1.0 / n_resamples)
    return point_r, ci_low, ci_high, p_two


def run_prewhitened_ccf(spec: HypothesisSpec, snapshot: str | None) -> dict:
    df = _load_paired(
        spec.feature,
        spec.target,
        spec.feature_transform,
        spec.target_transform,
        spec.date_start,
        spec.date_end,
        snapshot,
    )
    if df.height < 30:
        return {"error": f"insufficient data: {df.height} paired observations"}

    df = _residualize(df, spec.residualize)
    feat = df["feature"].to_numpy().astype(float)
    tgt = df["target"].to_numpy().astype(float)

    model, order = _fit_arima_simple(feat)
    feat_white = np.asarray(model.resid)
    # Apply same ARIMA structure to target (refit to enforce same noise model)
    try:
        tgt_model = ARIMA(tgt, order=order).fit()
        tgt_white = np.asarray(tgt_model.resid)
    except Exception:
        tgt_white = tgt - np.mean(tgt)

    # ACF decay → block size for bootstrap
    a = acf(feat_white, nlags=20, fft=True)
    block = max(2, int(np.argmax(np.abs(a[1:]) < 0.1)) + 1)

    lag_results = []
    raw_p = []
    for lag in spec.lags:
        r, lo, hi, p = _stationary_block_bootstrap_ccf(feat_white, tgt_white, lag, block, spec.n_bootstrap)
        att = spec.attenuation.factor if spec.attenuation else 1.0
        r_corrected = r / att if att > 0 and not math.isnan(r) else float("nan")
        lag_results.append(
            {
                "lag": lag,
                "ccf": round(r, 4),
                "ci_low": round(lo, 4),
                "ci_high": round(hi, 4),
                "p_raw": round(p, 5),
                "r_observed": round(r, 4),
                "r_corrected": round(r_corrected, 4),
            }
        )
        raw_p.append(p)

    # FDR within this hypothesis's lags
    if raw_p:
        _, p_fdr, _, _ = multipletests(raw_p, alpha=spec.fdr_q, method="fdr_bh")
        for i, lr in enumerate(lag_results):
            lr["p_fdr"] = round(float(p_fdr[i]), 5)

    # Spearman vs Pearson nonlinearity check (lag 0 only)
    if 0 in spec.lags:
        sp_r = float(spearmanr(feat_white, tgt_white)[0])
        pe_r = float(pearsonr(feat_white, tgt_white)[0])
        nonlin = abs(sp_r - pe_r) > 0.05
    else:
        sp_r, pe_r, nonlin = None, None, False

    # Ljung-Box on feature ARIMA residuals
    try:
        lb = acorr_ljungbox(feat_white, lags=[10], return_df=True)
        lb_p = float(lb["lb_pvalue"].iloc[0])
    except Exception:
        lb_p = None

    return {
        "n_paired": df.height,
        "arima_order": list(order),
        "ljung_box_p_lag10": lb_p,
        "block_size_bootstrap": block,
        "spearman_r": sp_r,
        "pearson_r": pe_r,
        "nonlinearity_flag": bool(nonlin),
        "attenuation_factor": spec.attenuation.factor if spec.attenuation else None,
        "lag_results": lag_results,
    }


# ── Method: ICC + Bland-Altman ─────────────────────────────────────────


def _icc21(x: np.ndarray, y: np.ndarray) -> float:
    """ICC(2,1) absolute agreement, two-way random, single rater. Manual impl (no pingouin dep)."""
    n = len(x)
    if n < 5:
        return float("nan")
    matrix = np.column_stack([x, y])
    grand_mean = matrix.mean()
    msr = np.var(matrix.mean(axis=1), ddof=1) * 2
    msc = np.var(matrix.mean(axis=0), ddof=1) * n
    err = matrix - matrix.mean(axis=1, keepdims=True) - (matrix.mean(axis=0) - grand_mean)
    mse = (err**2).sum() / ((n - 1) * (2 - 1))
    icc = (msr - mse) / (msr + (2 - 1) * mse + 2 * (msc - mse) / n)
    return float(np.clip(icc, -1.0, 1.0))


def _ccc(x: np.ndarray, y: np.ndarray) -> float:
    """Lin's concordance correlation coefficient."""
    mx, my = float(np.mean(x)), float(np.mean(y))
    vx, vy = float(np.var(x, ddof=0)), float(np.var(y, ddof=0))
    cov = float(np.mean((x - mx) * (y - my)))
    denom = vx + vy + (mx - my) ** 2
    return 2 * cov / denom if denom > 0 else float("nan")


def run_icc_bland_altman(spec: HypothesisSpec, snapshot: str | None) -> dict:
    pairs = spec.extra.get("pairs", [(spec.feature, spec.target)])
    raw = wide_daily(snapshot)

    results = []
    for a_canon, b_canon in pairs:
        a_col = resolve_column(a_canon)
        b_col = resolve_column(b_canon)
        if a_col not in raw.columns or b_col not in raw.columns:
            results.append({"pair": f"{a_canon} vs {b_canon}", "error": "column missing"})
            continue
        df = raw.select(["date", a_col, b_col]).filter(pl.col(a_col).is_not_null() & pl.col(b_col).is_not_null())
        if spec.date_start:
            df = df.filter(pl.col("date") >= pl.lit(spec.date_start).str.to_date())
        if df.height < 10:
            results.append(
                {
                    "pair": f"{a_canon} vs {b_canon}",
                    "n_overlap": df.height,
                    "error": "n<10",
                }
            )
            continue
        x = df[a_col].to_numpy().astype(float)
        y = df[b_col].to_numpy().astype(float)
        diff = y - x
        bias = float(np.mean(diff))
        sd = float(np.std(diff, ddof=1))
        loa_low = bias - 1.96 * sd
        loa_high = bias + 1.96 * sd
        icc = _icc21(x, y)
        ccc_v = _ccc(x, y)
        pearson_r = float(pearsonr(x, y)[0]) if df.height >= 5 else float("nan")
        results.append(
            {
                "pair": f"{a_canon} vs {b_canon}",
                "n_overlap": df.height,
                "icc_2_1": round(icc, 4),
                "ccc": round(ccc_v, 4),
                "pearson_r": round(pearson_r, 4),
                "mean_diff": round(bias, 3),
                "loa_low": round(loa_low, 3),
                "loa_high": round(loa_high, 3),
            }
        )
    return {"pairs": results}


# ── Method: quadrant chi-square (H14) ──────────────────────────────────


def run_quadrant_chi2(spec: HypothesisSpec, snapshot: str | None) -> dict:
    df = _load_paired(
        spec.feature,
        spec.target,
        spec.feature_transform,
        spec.target_transform,
        spec.date_start,
        spec.date_end,
        snapshot,
    )
    if df.height < 30:
        return {"error": f"insufficient data: {df.height}"}

    df = _residualize(df, spec.residualize)
    rhr_z = df["feature"].to_numpy()  # resting_hr z_28 (residualized)
    hrv_z = df["target"].to_numpy()  # hrv_garmin z_28 (residualized)

    # Quadrants per Plews framework on residualized z-scores
    rhr_high = rhr_z > 1.0
    rhr_low = rhr_z < -1.0
    hrv_high = hrv_z > 1.0
    hrv_low = hrv_z < -1.0

    a = int(np.sum(rhr_low & hrv_high))  # adaptation
    b = int(np.sum(rhr_high & hrv_low))  # acute fatigue / illness
    c = int(np.sum(rhr_low & hrv_low))  # parasympathetic saturation
    d = int(np.sum(rhr_high & hrv_high))  # unusual
    other = df.height - (a + b + c + d)

    # Strain tertile cross-tab (using strain_whoop rolling 14d as load proxy)
    strain_col = spec.extra.get("strain_col", "strain_whoop")
    win = spec.extra.get("tertile_window_days", 14)
    chi2_result = None
    if strain_col in wide_daily(snapshot).columns:
        feats = wide_daily_features(snapshot)
        if f"{strain_col}_roll{win}_mean" in feats.columns:
            roll = feats.select(["date", f"{strain_col}_roll{win}_mean"]).rename(
                {f"{strain_col}_roll{win}_mean": "load"}
            )
            joined = df.join(roll, on="date", how="left").filter(pl.col("load").is_not_null())
            if joined.height >= 30:
                quad_label = []
                for r, h in zip(joined["feature"].to_list(), joined["target"].to_list(), strict=True):
                    if r > 1.0 and h < -1.0:
                        quad_label.append("B")
                    elif r < -1.0 and h > 1.0:
                        quad_label.append("A")
                    elif r < -1.0 and h < -1.0:
                        quad_label.append("C")
                    elif r > 1.0 and h > 1.0:
                        quad_label.append("D")
                    else:
                        quad_label.append("OTHER")
                joined = joined.with_columns(pl.Series("quad", quad_label))
                # Tertiles
                load_vals = joined["load"].to_numpy()
                p33 = float(np.percentile(load_vals, 33))
                p67 = float(np.percentile(load_vals, 67))
                tert = ["low" if v <= p33 else "mid" if v <= p67 else "high" for v in load_vals]
                joined = joined.with_columns(pl.Series("tertile", tert))
                contingency = (
                    joined.group_by(["tertile", "quad"])
                    .len()
                    .pivot(on="quad", index="tertile", values="len")
                    .fill_null(0)
                )
                # Take only B vs others for clarity
                if "B" in contingency.columns:
                    counts_b = contingency["B"].to_numpy()
                    n_per_tert = contingency.select(pl.exclude("tertile")).sum_horizontal().to_numpy()
                    counts_other = n_per_tert - counts_b
                    tert_labels = contingency["tertile"].to_list()
                    table = np.array([counts_b, counts_other])
                    quadrant_b_by_tertile = {str(t): int(b) for t, b in zip(tert_labels, counts_b, strict=True)}
                    n_by_tertile = {str(t): int(n) for t, n in zip(tert_labels, n_per_tert, strict=True)}
                    if table.sum() > 0 and (table >= 5).all():
                        chi2, p, dof, _ = chi2_contingency(table)
                        chi2_result = {
                            "test": "chi2",
                            "stat": round(float(chi2), 3),
                            "p_value": round(float(p), 5),
                            "dof": int(dof),
                            "quadrant_b_by_tertile": quadrant_b_by_tertile,
                            "n_by_tertile": n_by_tertile,
                        }
                    elif table.shape == (2, 3) or table.shape == (2, 2):
                        # Fisher exact for sparse cells. scipy handles 2x2 directly;
                        # for 2x3 we test pairwise high-vs-low tertile.
                        if table.shape == (2, 3):
                            high_low = np.array(
                                [
                                    [counts_b[2], counts_b[0]],
                                    [counts_other[2], counts_other[0]],
                                ]
                            )
                        else:
                            high_low = table
                        odds, p = fisher_exact(high_low, alternative="two-sided")
                        chi2_result = {
                            "test": "fisher_exact_high_vs_low",
                            "stat": round(float(odds), 3),
                            "p_value": round(float(p), 5),
                            "quadrant_b_by_tertile": quadrant_b_by_tertile,
                            "n_by_tertile": n_by_tertile,
                            "note": (
                                "expected count <5 in some cell; Fisher exact comparing high vs low strain tertile only"
                            ),
                        }
                    else:
                        chi2_result = {
                            "test": "skipped",
                            "quadrant_b_by_tertile": quadrant_b_by_tertile,
                            "n_by_tertile": n_by_tertile,
                            "note": "table shape unsupported",
                        }
    return {
        "n_paired": df.height,
        "quadrants": {
            "A_adaptation": a,
            "B_acute_fatigue": b,
            "C_parasymp_sat": c,
            "D_unusual": d,
            "other": other,
        },
        "chi2_strain_tertiles": chi2_result,
    }


# ── Method: Kruskal-Wallis (H10) ───────────────────────────────────────


def _eta_squared_kw(h_stat: float, n: int, k: int) -> float:
    if n - k <= 0:
        return 0.0
    return max(0.0, (h_stat - k + 1) / (n - k))


def run_kruskal_wallis(spec: HypothesisSpec, snapshot: str | None) -> dict:
    raw = wide_daily(snapshot)
    metrics = spec.extra.get("metrics", CORE_METRICS_FOR_H10)
    rows = []
    for m_canon in metrics:
        m = resolve_column(m_canon)
        if m not in raw.columns:
            continue
        df = raw.select(["date", m]).filter(pl.col(m).is_not_null())
        if df.height < 100:
            continue
        df = df.with_columns(
            pl.col("date").dt.weekday().alias("wd"),
            pl.col("date").dt.month().alias("mo"),
        )
        groups_wd = [df.filter(pl.col("wd") == w)[m].to_numpy() for w in range(1, 8)]
        groups_wd = [g for g in groups_wd if len(g) >= 5]
        groups_mo = [df.filter(pl.col("mo") == mo)[m].to_numpy() for mo in range(1, 13)]
        groups_mo = [g for g in groups_mo if len(g) >= 5]

        if len(groups_wd) >= 2:
            h_wd, p_wd = kruskal(*groups_wd)
            n_wd = sum(len(g) for g in groups_wd)
            eta_wd = _eta_squared_kw(float(h_wd), n_wd, len(groups_wd))
        else:
            h_wd, p_wd, eta_wd = float("nan"), float("nan"), float("nan")

        if len(groups_mo) >= 2:
            h_mo, p_mo = kruskal(*groups_mo)
            n_mo = sum(len(g) for g in groups_mo)
            eta_mo = _eta_squared_kw(float(h_mo), n_mo, len(groups_mo))
        else:
            h_mo, p_mo, eta_mo = float("nan"), float("nan"), float("nan")

        rows.append(
            {
                "metric": m_canon,
                "n": df.height,
                "kw_h_dow": round(float(h_wd), 2) if not math.isnan(h_wd) else None,
                "p_dow": round(float(p_wd), 5) if not math.isnan(p_wd) else None,
                "eta2_dow": round(float(eta_wd), 4) if not math.isnan(eta_wd) else None,
                "kw_h_month": round(float(h_mo), 2) if not math.isnan(h_mo) else None,
                "p_month": round(float(p_mo), 5) if not math.isnan(p_mo) else None,
                "eta2_month": round(float(eta_mo), 4) if not math.isnan(eta_mo) else None,
                "dow_dummy_required": (eta_wd > 0.02) if not math.isnan(eta_wd) else False,
                "month_dummy_required": (eta_mo > 0.03) if not math.isnan(eta_mo) else False,
            }
        )

    # FDR across all p-values
    pvals_dow = [r["p_dow"] for r in rows if r["p_dow"] is not None]
    pvals_mo = [r["p_month"] for r in rows if r["p_month"] is not None]
    if pvals_dow:
        _, fdr_dow, _, _ = multipletests(pvals_dow, alpha=0.05, method="fdr_bh")
        i = 0
        for r in rows:
            if r["p_dow"] is not None:
                r["p_dow_fdr"] = round(float(fdr_dow[i]), 5)
                i += 1
    if pvals_mo:
        _, fdr_mo, _, _ = multipletests(pvals_mo, alpha=0.05, method="fdr_bh")
        i = 0
        for r in rows:
            if r["p_month"] is not None:
                r["p_month_fdr"] = round(float(fdr_mo[i]), 5)
                i += 1

    return {"rows": rows}


# ── Method: partial correlation (H3) ───────────────────────────────────


def _partial_correlation(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> float:
    """Partial correlation of x and y controlling for z."""
    rxy = float(pearsonr(x, y)[0])
    rxz = float(pearsonr(x, z)[0])
    ryz = float(pearsonr(y, z)[0])
    denom = math.sqrt(max(0.0, (1 - rxz**2) * (1 - ryz**2)))
    if denom == 0:
        return float("nan")
    return (rxy - rxz * ryz) / denom


def run_partial_correlation(spec: HypothesisSpec, snapshot: str | None) -> dict:
    df = _load_paired(
        spec.feature,
        spec.target,
        spec.feature_transform,
        spec.target_transform,
        spec.date_start,
        spec.date_end,
        snapshot,
    )
    if not spec.control_variables:
        return {"error": "control_variables required"}
    feats = wide_daily_features(snapshot)
    ctl_canon = spec.control_variables[0]
    ctl_col = resolve_column(ctl_canon)
    suffix_map = {"z_28": "_z28", "z_7": "_z7", "z_90": "_z90", "diff": "_diff"}
    if spec.feature_transform == "raw":
        ctl_full = f"{ctl_col}_z28"  # use z_28 of control by default
    else:
        ctl_full = f"{ctl_col}{suffix_map[spec.feature_transform]}"
    if ctl_full not in feats.columns:
        return {"error": f"control column {ctl_full} not in features"}
    ctl_series = feats.select(["date", ctl_full]).rename({ctl_full: "control"})
    df = df.join(ctl_series, on="date", how="inner").filter(pl.col("control").is_not_null())
    df = _residualize(df, spec.residualize)

    x = df["feature"].to_numpy().astype(float)
    y = df["target"].to_numpy().astype(float)
    z = df["control"].to_numpy().astype(float)

    if len(x) < 20:
        return {"error": f"n too small: {len(x)}"}

    r_partial_xy_z = _partial_correlation(x, y, z)
    r_partial_zy_x = _partial_correlation(z, y, x)
    r_xy = float(pearsonr(x, y)[0])
    r_zy = float(pearsonr(z, y)[0])

    att = spec.attenuation.factor if spec.attenuation else 1.0
    return {
        "n_paired": df.height,
        "feature_canonical": spec.feature,
        "target_canonical": spec.target,
        "control_canonical": ctl_canon,
        "pearson_feature_target": round(r_xy, 4),
        "pearson_control_target": round(r_zy, 4),
        "partial_feature_target_given_control": round(r_partial_xy_z, 4),
        "partial_control_target_given_feature": round(r_partial_zy_x, 4),
        "partial_feature_corrected": round(r_partial_xy_z / att if att > 0 else float("nan"), 4),
        "attenuation_factor": att,
    }


# ── Dispatch + CLI ─────────────────────────────────────────────────────


METHOD_DISPATCH: dict[Method, Callable[[HypothesisSpec, str | None], dict]] = {
    Method.PREWHITENED_CCF: run_prewhitened_ccf,
    Method.ICC_BLAND_ALTMAN: run_icc_bland_altman,
    Method.QUADRANT_CHI2: run_quadrant_chi2,
    Method.KRUSKAL_WALLIS: run_kruskal_wallis,
    Method.PARTIAL_CORRELATION: run_partial_correlation,
}


def _git_sha() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
        return out
    except Exception:
        return "unknown"


def _run_one(spec: HypothesisSpec, snapshot: str | None) -> dict:
    if spec.tier == Tier.BLOCKED:
        return {"error": f"BLOCKED: {spec.name}", "reason": "see HYPOTHESIS_v1.2.md"}
    runner = METHOD_DISPATCH[spec.method]
    return runner(spec, snapshot)


def main() -> None:
    parser = argparse.ArgumentParser(description="lac-test: hypothesis testing engine")
    parser.add_argument(
        "--hypothesis",
        required=True,
        help="H2/H3/H6/H10/H11/H12/H14 or 'all-confirmatory' / 'all-exploratory'",
    )
    parser.add_argument("--snapshot", default=None)
    args = parser.parse_args()

    if args.hypothesis.startswith("all-"):
        tier_filter = args.hypothesis.split("-", 1)[1]
        specs = [s for s in REGISTRY.values() if s.tier.value == tier_filter]
    else:
        if args.hypothesis not in REGISTRY:
            raise SystemExit(f"Unknown hypothesis {args.hypothesis}. Available: {list(REGISTRY)}")
        specs = [REGISTRY[args.hypothesis]]

    base = snapshot_path(args.snapshot)
    out_dir = base / "processed" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    sha = _git_sha()
    timestamp = datetime.now(UTC).isoformat()

    for spec in specs:
        print(f"== {spec.id}: {spec.name} ({spec.tier.value}) ==")
        try:
            result = _run_one(spec, args.snapshot)
        except Exception as e:
            result = {"error": f"{type(e).__name__}: {e}"}
        out = {
            "hypothesis_id": spec.id,
            "name": spec.name,
            "tier": spec.tier.value,
            "method": spec.method.value,
            "snapshot": base.name,
            "git_sha": sha,
            "timestamp": timestamp,
            "spec": {
                "feature": spec.feature,
                "target": spec.target,
                "feature_transform": spec.feature_transform,
                "target_transform": spec.target_transform,
                "lags": spec.lags,
                "expected_direction": spec.expected_direction,
                "date_start": spec.date_start,
                "date_end": spec.date_end,
                "fdr_q": spec.fdr_q,
                "confirmatory_r_threshold": spec.confirmatory_r_threshold,
            },
            "result": result,
        }
        out_path = out_dir / f"{spec.id}_result.json"
        out_path.write_text(json.dumps(out, indent=2, default=str))
        print(f"  Wrote {out_path}")
        print(f"  {json.dumps(result, indent=2, default=str)[:1500]}")
        print()


if __name__ == "__main__":
    main()
