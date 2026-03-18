from __future__ import annotations

import math
from datetime import date

from .constants import (
    HRV_AGE_BASELINE_AGE,
    HRV_AGE_BASELINE_HRV,
    HRV_AGE_DECAY_RATE,
    LONGEVITY_SCORE_WEIGHTS,
    MIN_BIO_AGE_DATA_DAYS,
    RHR_HAZARD_PER_10BPM,
    RHR_REFERENCE,
    VO2MAX_NORMATIVE_MALE,
    ZONE2_WEEKLY_TARGET_MINUTES,
    ZONE5_WEEKLY_TARGET_MINUTES,
)
from .date_utils import local_today, to_day_date, to_day_key
from .series import get_window_values, to_daily_series
from .stats import calculate_std, mean_or_none
from .types import (
    BiologicalAgeComponent,
    BiologicalAgeMetrics,
    DataPoint,
    LongevityInsights,
    LongevityScore,
    TrainingZoneMetrics,
)


def _hrv_to_age(hrv_value: float) -> float | None:
    if hrv_value <= 0:
        return None
    ratio = hrv_value / HRV_AGE_BASELINE_HRV
    raw_age = HRV_AGE_BASELINE_AGE - math.log(ratio) / HRV_AGE_DECAY_RATE
    return max(16.0, raw_age)


def _vo2max_to_age(vo2max: float) -> float | None:
    if vo2max <= 0:
        return None
    decades = sorted(VO2MAX_NORMATIVE_MALE.keys())
    for decade in decades:
        if vo2max >= VO2MAX_NORMATIVE_MALE[decade]["p50"]:
            if decade == decades[0]:
                return float(decade)
            prev = decades[decades.index(decade) - 1]
            prev_p50 = VO2MAX_NORMATIVE_MALE[prev]["p50"]
            curr_p50 = VO2MAX_NORMATIVE_MALE[decade]["p50"]
            if prev_p50 == curr_p50:
                return float(decade)
            ratio = (vo2max - curr_p50) / (prev_p50 - curr_p50)
            return decade - ratio * 10
    return float(decades[-1]) + 5


def _rhr_to_age_offset(rhr: float) -> float:
    return (rhr - RHR_REFERENCE) / 10 * math.log(RHR_HAZARD_PER_10BPM) * 15


def calculate_biological_age(
    hrv_data: list[DataPoint],
    vo2_max_data: list[DataPoint],
    rhr_data: list[DataPoint],
    fitness_age_data: list[DataPoint],
    recovery_data: list[DataPoint],
    chronological_age: float | None,
    ref_date: date | None = None,
) -> BiologicalAgeMetrics:
    if chronological_age is None:
        chronological_age = 30.0

    components: list[BiologicalAgeComponent] = []

    hrv_vals = get_window_values(
        to_daily_series(hrv_data, "mean"), MIN_BIO_AGE_DATA_DAYS, ref_date=ref_date
    )
    if hrv_vals:
        hrv_mean = mean_or_none(hrv_vals)
        if hrv_mean and hrv_mean > 0:
            hrv_age = _hrv_to_age(hrv_mean)
            if hrv_age is not None:
                components.append(
                    BiologicalAgeComponent(
                        name="hrv_age",
                        estimated_age=hrv_age,
                        chronological_age=chronological_age,
                        delta=hrv_age - chronological_age,
                        confidence=min(1.0, len(hrv_vals) / 30),
                        data_source="garmin/whoop",
                    )
                )

    vo2_vals = get_window_values(
        to_daily_series(vo2_max_data, "last"), 30, ref_date=ref_date
    )
    if vo2_vals:
        vo2_current = vo2_vals[-1]
        vo2_age = _vo2max_to_age(vo2_current)
        if vo2_age is not None:
            components.append(
                BiologicalAgeComponent(
                    name="fitness_age",
                    estimated_age=vo2_age,
                    chronological_age=chronological_age,
                    delta=vo2_age - chronological_age,
                    confidence=0.9,
                    data_source="garmin_vo2max",
                )
            )

    garmin_fitness_vals = get_window_values(
        to_daily_series(fitness_age_data, "last"), 30, ref_date=ref_date
    )
    if garmin_fitness_vals and not vo2_vals:
        garmin_fa = garmin_fitness_vals[-1]
        components.append(
            BiologicalAgeComponent(
                name="fitness_age",
                estimated_age=garmin_fa,
                chronological_age=chronological_age,
                delta=garmin_fa - chronological_age,
                confidence=0.85,
                data_source="garmin_native",
            )
        )

    rhr_vals = get_window_values(
        to_daily_series(rhr_data, "mean"), MIN_BIO_AGE_DATA_DAYS, ref_date=ref_date
    )
    if rhr_vals:
        rhr_mean = mean_or_none(rhr_vals)
        if rhr_mean:
            rhr_offset = _rhr_to_age_offset(rhr_mean)
            rhr_age = chronological_age + rhr_offset
            components.append(
                BiologicalAgeComponent(
                    name="rhr_age",
                    estimated_age=rhr_age,
                    chronological_age=chronological_age,
                    delta=rhr_offset,
                    confidence=min(1.0, len(rhr_vals) / 30) * 0.7,
                    data_source="garmin/whoop",
                )
            )

    rec_vals = get_window_values(
        to_daily_series(recovery_data, "last"), MIN_BIO_AGE_DATA_DAYS, ref_date=ref_date
    )
    if rec_vals:
        rec_mean = mean_or_none(rec_vals)
        if rec_mean is not None:
            recovery_offset = (50 - rec_mean) / 10 * 2
            recovery_age = chronological_age + recovery_offset
            components.append(
                BiologicalAgeComponent(
                    name="recovery_age",
                    estimated_age=recovery_age,
                    chronological_age=chronological_age,
                    delta=recovery_offset,
                    confidence=min(1.0, len(rec_vals) / 30) * 0.6,
                    data_source="whoop",
                )
            )

    composite: float | None = None
    age_delta: float | None = None
    if components:
        total_weight = sum(c.confidence for c in components)
        if total_weight > 0:
            composite = (
                sum(
                    (c.estimated_age or 0) * c.confidence
                    for c in components
                    if c.estimated_age is not None
                )
                / total_weight
            )
            age_delta = composite - chronological_age

    return BiologicalAgeMetrics(
        composite_biological_age=composite,
        chronological_age=chronological_age,
        age_delta=age_delta,
        components=components,
        pace_of_aging=None,
        pace_trend=None,
    )


def _aggregate_zone_minutes(
    zone_data: list[DataPoint],
    window_days: int,
    ref_date: date | None = None,
) -> float | None:
    vals = get_window_values(
        to_daily_series(zone_data, "sum"), window_days, ref_date=ref_date
    )
    return sum(vals) if vals else None


def calculate_training_zones(
    zone2_data: list[DataPoint],
    zone5_data: list[DataPoint],
    total_training_data: list[DataPoint],
    ref_date: date | None = None,
) -> TrainingZoneMetrics:
    z2_7d = _aggregate_zone_minutes(zone2_data, 7, ref_date)
    z2_30d = _aggregate_zone_minutes(zone2_data, 30, ref_date)
    z5_7d = _aggregate_zone_minutes(zone5_data, 7, ref_date)
    z5_30d = _aggregate_zone_minutes(zone5_data, 30, ref_date)
    total_7d = _aggregate_zone_minutes(total_training_data, 7, ref_date)
    total_30d = _aggregate_zone_minutes(total_training_data, 30, ref_date)

    z2_pct = (
        (z2_30d / total_30d * 100) if z2_30d and total_30d and total_30d > 0 else None
    )
    z5_pct = (
        (z5_30d / total_30d * 100) if z5_30d and total_30d and total_30d > 0 else None
    )

    z2_target = z2_7d >= ZONE2_WEEKLY_TARGET_MINUTES if z2_7d is not None else None
    z5_target = z5_7d >= ZONE5_WEEKLY_TARGET_MINUTES if z5_7d is not None else None

    return TrainingZoneMetrics(
        zone2_minutes_7d=z2_7d,
        zone2_minutes_30d=z2_30d,
        zone2_pct_of_total=z2_pct,
        zone5_minutes_7d=z5_7d,
        zone5_minutes_30d=z5_30d,
        zone5_pct_of_total=z5_pct,
        total_training_minutes_7d=total_7d,
        total_training_minutes_30d=total_30d,
        zone2_target_met=z2_target,
        zone5_target_met=z5_target,
    )


def _score_vo2max(vo2max: float | None, chrono_age: float) -> float | None:
    if vo2max is None:
        return None
    decade = int(chrono_age // 10) * 10
    decade = max(20, min(70, decade))
    norms = VO2MAX_NORMATIVE_MALE.get(decade)
    if not norms:
        return None
    p10 = norms["p10"]
    p90 = norms["p90"]
    if p90 == p10:
        return 50.0
    raw = (vo2max - p10) / (p90 - p10) * 100
    return max(0.0, min(100.0, raw))


def _score_recovery(
    hrv_data: list[DataPoint],
    recovery_data: list[DataPoint],
    baseline_window: int,
    ref_date: date | None = None,
) -> float | None:
    hrv_vals = get_window_values(
        to_daily_series(hrv_data, "mean"), baseline_window, ref_date=ref_date
    )
    rec_vals = get_window_values(
        to_daily_series(recovery_data, "last"), baseline_window, ref_date=ref_date
    )

    scores = []
    if hrv_vals and len(hrv_vals) >= 7:
        hrv_mean = mean_or_none(hrv_vals)
        hrv_cv = (
            calculate_std(hrv_vals) / hrv_mean * 100
            if hrv_mean and hrv_mean > 0
            else 50
        )
        hrv_score = max(0, min(100, 100 - hrv_cv * 2))
        if hrv_mean:
            hrv_level = min(100, hrv_mean / 80 * 100)
            scores.append((hrv_level + hrv_score) / 2)

    if rec_vals and len(rec_vals) >= 7:
        rec_mean = mean_or_none(rec_vals)
        if rec_mean is not None:
            scores.append(rec_mean)

    return mean_or_none(scores)


def _score_sleep(
    sleep_data: list[DataPoint],
    baseline_window: int,
    ref_date: date | None = None,
) -> float | None:
    vals = get_window_values(
        to_daily_series(sleep_data, "last"), baseline_window, ref_date=ref_date
    )
    if not vals or len(vals) < 7:
        return None
    avg_min = mean_or_none(vals)
    if avg_min is None:
        return None
    avg_hours = avg_min / 60
    optimal = 7.5
    if avg_hours >= optimal:
        duration_score = max(0, 100 - (avg_hours - optimal) * 20)
    else:
        duration_score = max(0, avg_hours / optimal * 100)

    sleep_cv = calculate_std(vals) / avg_min * 100 if avg_min > 0 else 50
    consistency_score = max(0, min(100, 100 - sleep_cv * 3))

    return duration_score * 0.6 + consistency_score * 0.4


def _score_body_composition(
    weight_data: list[DataPoint],
    body_fat_data: list[DataPoint],
    ref_date: date | None = None,
) -> float | None:
    scores = []

    bf_vals = get_window_values(
        to_daily_series(body_fat_data, "last"), 30, ref_date=ref_date
    )
    if bf_vals:
        bf = bf_vals[-1]
        if 10 <= bf <= 20:
            scores.append(100.0)
        elif bf < 10:
            scores.append(max(50, 100 - (10 - bf) * 10))
        else:
            scores.append(max(0, 100 - (bf - 20) * 5))

    w_vals = get_window_values(
        to_daily_series(weight_data, "last"), 90, ref_date=ref_date
    )
    if w_vals and len(w_vals) >= 14:
        weight_cv = calculate_std(w_vals) / (mean_or_none(w_vals) or 1) * 100
        stability_score = max(0, min(100, 100 - weight_cv * 20))
        scores.append(stability_score)

    return mean_or_none(scores)


def _score_activity(
    steps_data: list[DataPoint],
    workout_dates: list[DataPoint],
    ref_date: date | None = None,
) -> float | None:
    today = ref_date or local_today()
    scores = []

    step_vals = get_window_values(
        to_daily_series(steps_data, "last"), 30, ref_date=ref_date
    )
    if step_vals:
        avg_steps = mean_or_none(step_vals)
        if avg_steps is not None:
            scores.append(min(100, avg_steps / 10000 * 100))

    workout_set = {to_day_key(d.date) for d in workout_dates if d.value is not None}
    freq_30d = sum(1 for d in workout_set if (today - to_day_date(d)).days < 30)
    if freq_30d > 0:
        freq_score = min(100, freq_30d / 12 * 100)
        scores.append(freq_score)

    return mean_or_none(scores)


def calculate_longevity_score(
    vo2_max_data: list[DataPoint],
    hrv_data: list[DataPoint],
    recovery_data: list[DataPoint],
    sleep_data: list[DataPoint],
    weight_data: list[DataPoint],
    body_fat_data: list[DataPoint],
    steps_data: list[DataPoint],
    workout_dates: list[DataPoint],
    chronological_age: float,
    baseline_window: int = 90,
    ref_date: date | None = None,
) -> LongevityScore:
    vo2_vals = get_window_values(
        to_daily_series(vo2_max_data, "last"), 30, ref_date=ref_date
    )
    vo2_current = vo2_vals[-1] if vo2_vals else None

    cardio = _score_vo2max(vo2_current, chronological_age)
    recovery = _score_recovery(hrv_data, recovery_data, baseline_window, ref_date)
    sleep = _score_sleep(sleep_data, baseline_window, ref_date)
    body_comp = _score_body_composition(weight_data, body_fat_data, ref_date)
    activity = _score_activity(steps_data, workout_dates, ref_date)

    weights = LONGEVITY_SCORE_WEIGHTS
    component_scores = {
        "cardiorespiratory": cardio,
        "recovery_resilience": recovery,
        "sleep_optimization": sleep,
        "body_composition": body_comp,
        "activity_consistency": activity,
    }

    total_weight = 0.0
    weighted_sum = 0.0
    for name, score in component_scores.items():
        if score is not None:
            w = weights[name]
            weighted_sum += score * w
            total_weight += w

    overall = weighted_sum / total_weight if total_weight > 0 else None

    return LongevityScore(
        overall=overall,
        cardiorespiratory=cardio,
        recovery_resilience=recovery,
        sleep_optimization=sleep,
        body_composition=body_comp,
        activity_consistency=activity,
        trend=None,
    )


def calculate_longevity_insights(
    hrv_data: list[DataPoint],
    rhr_data: list[DataPoint],
    vo2_max_data: list[DataPoint],
    fitness_age_data: list[DataPoint],
    recovery_data: list[DataPoint],
    sleep_data: list[DataPoint],
    weight_data: list[DataPoint],
    body_fat_data: list[DataPoint],
    steps_data: list[DataPoint],
    workout_dates: list[DataPoint],
    zone2_data: list[DataPoint],
    zone5_data: list[DataPoint],
    total_training_data: list[DataPoint],
    chronological_age: float | None,
    baseline_window: int = 90,
    ref_date: date | None = None,
) -> LongevityInsights:
    chrono_age = chronological_age or 30.0

    bio_age = calculate_biological_age(
        hrv_data,
        vo2_max_data,
        rhr_data,
        fitness_age_data,
        recovery_data,
        chronological_age,
        ref_date,
    )
    training_zones = calculate_training_zones(
        zone2_data,
        zone5_data,
        total_training_data,
        ref_date,
    )
    longevity_score = calculate_longevity_score(
        vo2_max_data,
        hrv_data,
        recovery_data,
        sleep_data,
        weight_data,
        body_fat_data,
        steps_data,
        workout_dates,
        chrono_age,
        baseline_window,
        ref_date,
    )

    return LongevityInsights(
        biological_age=bio_age,
        training_zones=training_zones,
        longevity_score=longevity_score,
    )
