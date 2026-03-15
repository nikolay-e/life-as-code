from __future__ import annotations

import math

import numpy as np
from scipy import stats as scipy_stats

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
    lower_bound = float(np.percentile(values, lower_pct, method="linear"))
    upper_bound = float(np.percentile(values, upper_pct, method="linear"))
    return [min(max(v, lower_bound), upper_bound) for v in values]


def calculate_median(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(np.median(values))


def calculate_mad(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    median = float(np.median(values))
    return float(np.median(np.abs(np.array(values) - median)))


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
    mad = float(np.median(np.abs(arr - median)))
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
    import pandas as pd

    return float(pd.Series(values).ewm(span=span, adjust=False).mean().iloc[-1])


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
        r, p = scipy_stats.pearsonr(x, y)
        r_val = float(r) if math.isfinite(r) else None
        p_val = float(p) if math.isfinite(p) else None
        return r_val, p_val
    except Exception:
        return None, None
