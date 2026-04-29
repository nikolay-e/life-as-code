"""Local Sleep Index — open-source approximation of a Sleep Fitness Score.

Eight Sleep's official Sleep Fitness Score (sfs) is now read directly from
`app-api.8slp.net/v1/users/<id>/metrics/summary`, but the underlying weights
are an undisclosed adaptive engine and the field can disappear (subscription
lapse, API revocation, host migration). This module computes a transparent,
self-contained 0-100 score so we can keep showing a useful number even when
the upstream value is null.

Formula weights (rounded; sum to 1.0):
    0.25  routine_score          (Eight Sleep wake-time consistency, when present)
    0.20  quality_score          (Eight Sleep HR/HRV/RR/TnT composite, when present)
    0.20  duration_score         (piecewise: 100 inside [7h, 9h], linear falloff)
    0.10  efficiency_score       (AASM: sleep_min / time_in_bed_min)
    0.08  deep_pct_score         (gaussian around 18% of TST)
    0.07  rem_pct_score          (gaussian around 22% of TST)
    0.05  latency_score          (100 inside [5, 20] min, penalty outside)
    0.05  hrv_recovery_score     (z-score of overnight HRV vs trailing 28d mean)

When `routine_score` or `quality_score` is null (e.g. Garmin/Whoop-only night),
their weight is redistributed proportionally across the remaining components so
the final score stays on the same 0-100 scale and remains source-agnostic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SleepIndexInputs:
    routine_score: int | None  # 0-100, Eight Sleep srs
    quality_score: int | None  # 0-100, Eight Sleep sqs
    total_sleep_minutes: float | None
    time_in_bed_minutes: float | None
    deep_minutes: float | None
    rem_minutes: float | None
    latency_asleep_minutes: float | None
    hrv_overnight_ms: float | None
    hrv_baseline_mean_ms: float | None  # trailing 28d mean
    hrv_baseline_std_ms: float | None  # trailing 28d std


_WEIGHTS = {
    "routine": 0.25,
    "quality": 0.20,
    "duration": 0.20,
    "efficiency": 0.10,
    "deep_pct": 0.08,
    "rem_pct": 0.07,
    "latency": 0.05,
    "hrv_recovery": 0.05,
}


def _duration_score(total_min: float | None) -> float | None:
    if total_min is None or total_min <= 0:
        return None
    # Plateau between 7h and 9h, linear falloff to 0 at 4h or 11h.
    if 420 <= total_min <= 540:
        return 100.0
    if total_min < 420:
        return max(0.0, 100.0 * (total_min - 240) / (420 - 240))
    return max(0.0, 100.0 * (660 - total_min) / (660 - 540))


def _efficiency_score(
    total_min: float | None, in_bed_min: float | None
) -> float | None:
    if total_min is None or in_bed_min is None or in_bed_min <= 0:
        return None
    eff = total_min / in_bed_min
    if eff >= 0.95:
        return 100.0
    if eff <= 0.50:
        return 0.0
    return max(0.0, min(100.0, (eff - 0.50) / (0.95 - 0.50) * 100.0))


def _gaussian_pct_score(
    pct: float | None, target_pct: float, sigma: float
) -> float | None:
    if pct is None:
        return None
    deviation = (pct - target_pct) / sigma
    return max(0.0, min(100.0, 100.0 * math.exp(-0.5 * deviation * deviation)))


def _latency_score(latency_min: float | None) -> float | None:
    if latency_min is None or latency_min < 0:
        return None
    if 5 <= latency_min <= 20:
        return 100.0
    if latency_min < 5:
        return max(0.0, 100.0 * latency_min / 5.0)
    if latency_min <= 60:
        return max(0.0, 100.0 * (60 - latency_min) / (60 - 20))
    return 0.0


def _hrv_recovery_score(
    overnight_ms: float | None,
    baseline_mean_ms: float | None,
    baseline_std_ms: float | None,
) -> float | None:
    if (
        overnight_ms is None
        or baseline_mean_ms is None
        or baseline_std_ms is None
        or baseline_std_ms <= 0
    ):
        return None
    z = (overnight_ms - baseline_mean_ms) / baseline_std_ms
    # Map z-score to 0-100; z=0 -> 50, z=+1 -> ~84, z=-1 -> ~16.
    cdf = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    return max(0.0, min(100.0, cdf * 100.0))


def compute_sleep_index(inputs: SleepIndexInputs) -> float | None:
    """Return a 0-100 Sleep Index; None if no contributing component is available."""
    deep_pct = (
        100.0 * inputs.deep_minutes / inputs.total_sleep_minutes
        if inputs.deep_minutes is not None
        and inputs.total_sleep_minutes is not None
        and inputs.total_sleep_minutes > 0
        else None
    )
    rem_pct = (
        100.0 * inputs.rem_minutes / inputs.total_sleep_minutes
        if inputs.rem_minutes is not None
        and inputs.total_sleep_minutes is not None
        and inputs.total_sleep_minutes > 0
        else None
    )

    components: dict[str, float | None] = {
        "routine": (
            float(inputs.routine_score) if inputs.routine_score is not None else None
        ),
        "quality": (
            float(inputs.quality_score) if inputs.quality_score is not None else None
        ),
        "duration": _duration_score(inputs.total_sleep_minutes),
        "efficiency": _efficiency_score(
            inputs.total_sleep_minutes, inputs.time_in_bed_minutes
        ),
        "deep_pct": _gaussian_pct_score(deep_pct, target_pct=18.0, sigma=6.0),
        "rem_pct": _gaussian_pct_score(rem_pct, target_pct=22.0, sigma=5.0),
        "latency": _latency_score(inputs.latency_asleep_minutes),
        "hrv_recovery": _hrv_recovery_score(
            inputs.hrv_overnight_ms,
            inputs.hrv_baseline_mean_ms,
            inputs.hrv_baseline_std_ms,
        ),
    }

    available_weight = sum(_WEIGHTS[k] for k, v in components.items() if v is not None)
    if available_weight <= 0:
        return None

    weighted_sum = sum(_WEIGHTS[k] * v for k, v in components.items() if v is not None)
    # Renormalise so missing components don't drag the score toward zero.
    return max(0.0, min(100.0, weighted_sum / available_weight))
