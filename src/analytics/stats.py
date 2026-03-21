from __future__ import annotations

import math

import numpy as np
from scipy import stats as scipy_stats
from scipy.stats import median_abs_deviation
from scipy.stats.mstats import winsorize as _scipy_winsorize

from .constants import MAD_SCALE_FACTOR


def mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.mean(values))


def sum_or_none(values: list[float]) -> float | None:
    return float(np.sum(values)) if values else None


def calculate_percentile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    return float(np.percentile(sorted_values, percentile, method="linear"))


def winsorize(
    values: list[float], lower_pct: float = 5, upper_pct: float = 95
) -> list[float]:
    if len(values) < 4:
        return list(values)
    result = _scipy_winsorize(
        np.array(values), limits=(lower_pct / 100.0, 1.0 - upper_pct / 100.0)
    )
    return list(result.astype(float))


def calculate_median(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(np.median(values))


def calculate_mad(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(median_abs_deviation(values, scale=1.0))


def calculate_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(np.std(values, ddof=1))


def calculate_robust_stats(values: list[float]) -> dict:
    if not values:
        return {"median": 0.0, "mad": 0.0, "scaled_mad": 0.0, "mean": 0.0, "std": 0.0}
    arr = np.array(values, dtype=float)
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if len(values) >= 2 else 0.0
    median = float(np.median(arr))
    mad = float(median_abs_deviation(arr, scale=1.0))
    return {
        "median": median,
        "mad": mad,
        "scaled_mad": MAD_SCALE_FACTOR * mad,
        "mean": mean,
        "std": std,
    }


def calculate_ema_value(values: list[float], span: int) -> float | None:
    if not values:
        return None
    alpha = 2.0 / (span + 1)
    ema = values[0]
    for v in values[1:]:
        ema = alpha * v + (1 - alpha) * ema
    return float(ema)


def pearson_correlation(x: list[float], y: list[float]) -> float | None:
    r, _ = pearson_correlation_with_pvalue(x, y)
    return r


def pearson_correlation_with_pvalue(
    x: list[float],
    y: list[float],
) -> tuple[float | None, float | None]:
    from .constants import MIN_CORRELATION_PAIRS, MIN_STD_THRESHOLD

    n = len(x)
    if n != len(y) or n < MIN_CORRELATION_PAIRS:
        return None, None
    if np.std(x) < MIN_STD_THRESHOLD or np.std(y) < MIN_STD_THRESHOLD:
        return None, None
    try:
        result = scipy_stats.pearsonr(x, y)
        r_f = float(result[0])  # type: ignore[arg-type]  # scipy stubs
        p_f = float(result[1])  # type: ignore[arg-type]  # scipy stubs
        r_val = r_f if math.isfinite(r_f) else None
        p_val = p_f if math.isfinite(p_f) else None
        return r_val, p_val
    except Exception:
        return None, None
