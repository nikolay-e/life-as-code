from __future__ import annotations

import math

from .constants import MAD_SCALE_FACTOR


def mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def sum_or_none(values: list[float]) -> float | None:
    return sum(values) if values else None


def calculate_percentile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    index = (percentile / 100) * (len(sorted_values) - 1)
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return sorted_values[lower]
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (
        index - lower
    )


def winsorize(
    values: list[float], lower_pct: float = 5, upper_pct: float = 95
) -> list[float]:
    if len(values) < 4:
        return list(values)
    sorted_vals = sorted(values)
    lower_bound = calculate_percentile(sorted_vals, lower_pct)
    upper_bound = calculate_percentile(sorted_vals, upper_pct)
    return [min(max(v, lower_bound), upper_bound) for v in values]


def calculate_median(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    mid = len(sorted_vals) // 2
    if len(sorted_vals) % 2 != 0:
        return sorted_vals[mid]
    return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2


def calculate_mad(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    median = calculate_median(values)
    absolute_deviations = [abs(v - median) for v in values]
    return calculate_median(absolute_deviations)


def calculate_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def calculate_robust_stats(values: list[float]) -> dict:
    if not values:
        return {"median": 0.0, "mad": 0.0, "scaled_mad": 0.0, "mean": 0.0, "std": 0.0}
    mean = sum(values) / len(values)
    std = calculate_std(values)
    median = calculate_median(values)
    mad = calculate_mad(values)
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
    k = 2 / (span + 1)
    ema = values[0]
    for v in values[1:]:
        ema = v * k + ema * (1 - k)
    return ema


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
    x_mean = sum(x) / n
    y_mean = sum(y) / n
    numerator = 0.0
    x_denom = 0.0
    y_denom = 0.0
    for xi, yi in zip(x, y, strict=False):
        x_diff = xi - x_mean
        y_diff = yi - y_mean
        numerator += x_diff * y_diff
        x_denom += x_diff * x_diff
        y_denom += y_diff * y_diff
    denominator = math.sqrt(x_denom * y_denom)
    if denominator < MIN_STD_THRESHOLD:
        return None, None
    r = numerator / denominator

    if n <= 2 or abs(r) >= 1.0:
        return r, 0.0 if abs(r) >= 1.0 else None
    t_stat = r * math.sqrt((n - 2) / (1 - r * r))
    p_value = _two_tailed_t_pvalue(t_stat, n - 2)
    return r, p_value


def _two_tailed_t_pvalue(t: float, df: int) -> float:
    x = df / (df + t * t)
    p = _regularized_incomplete_beta(df / 2.0, 0.5, x)
    return p


def _regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0

    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta)

    # Lentz's continued fraction
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d

    for m in range(1, 201):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c

        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta

        if abs(delta - 1.0) < 1e-10:
            break

    return front / a * h
