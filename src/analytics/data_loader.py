from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from .date_utils import local_today
from .types import (
    DataPoint,
    MLAnomalyRecord,
    MLForecastMetric,
    MLForecastPoint,
    MLInsights,
)


@dataclass
class RawHealthData:
    hrv_garmin: list[DataPoint] = field(default_factory=list)
    hrv_whoop: list[DataPoint] = field(default_factory=list)
    sleep_garmin: list[DataPoint] = field(default_factory=list)
    sleep_whoop: list[DataPoint] = field(default_factory=list)
    rhr_garmin: list[DataPoint] = field(default_factory=list)
    rhr_whoop: list[DataPoint] = field(default_factory=list)
    stress: list[DataPoint] = field(default_factory=list)
    steps: list[DataPoint] = field(default_factory=list)
    weight: list[DataPoint] = field(default_factory=list)
    energy: list[DataPoint] = field(default_factory=list)
    recovery: list[DataPoint] = field(default_factory=list)
    strain_whoop: list[DataPoint] = field(default_factory=list)
    strain_garmin: list[DataPoint] = field(default_factory=list)
    calories_garmin: list[DataPoint] = field(default_factory=list)
    calories_whoop: list[DataPoint] = field(default_factory=list)
    sleep_deep_garmin: list[DataPoint] = field(default_factory=list)
    sleep_rem_garmin: list[DataPoint] = field(default_factory=list)
    sleep_awake_count_garmin: list[DataPoint] = field(default_factory=list)
    sleep_efficiency_garmin: list[DataPoint] = field(default_factory=list)
    respiratory_rate_garmin: list[DataPoint] = field(default_factory=list)
    sleep_deep_whoop: list[DataPoint] = field(default_factory=list)
    sleep_rem_whoop: list[DataPoint] = field(default_factory=list)
    sleep_efficiency_whoop: list[DataPoint] = field(default_factory=list)
    respiratory_rate_whoop: list[DataPoint] = field(default_factory=list)
    hrv_eight_sleep: list[DataPoint] = field(default_factory=list)
    rhr_eight_sleep: list[DataPoint] = field(default_factory=list)
    sleep_eight_sleep: list[DataPoint] = field(default_factory=list)
    sleep_deep_eight_sleep: list[DataPoint] = field(default_factory=list)
    sleep_rem_eight_sleep: list[DataPoint] = field(default_factory=list)
    sleep_light_eight_sleep: list[DataPoint] = field(default_factory=list)
    respiratory_rate_eight_sleep: list[DataPoint] = field(default_factory=list)
    sleep_score_eight_sleep: list[DataPoint] = field(default_factory=list)
    bed_temp: list[DataPoint] = field(default_factory=list)
    room_temp: list[DataPoint] = field(default_factory=list)
    sleep_latency: list[DataPoint] = field(default_factory=list)
    sleep_fitness_score: list[DataPoint] = field(default_factory=list)
    sleep_routine_score: list[DataPoint] = field(default_factory=list)
    sleep_quality_score_es: list[DataPoint] = field(default_factory=list)
    toss_and_turn: list[DataPoint] = field(default_factory=list)
    workout_dates: list[DataPoint] = field(default_factory=list)
    vo2_max: list[DataPoint] = field(default_factory=list)
    training_readiness: list[DataPoint] = field(default_factory=list)
    fitness_age: list[DataPoint] = field(default_factory=list)
    body_fat: list[DataPoint] = field(default_factory=list)
    zone2_minutes: list[DataPoint] = field(default_factory=list)
    zone5_minutes: list[DataPoint] = field(default_factory=list)
    total_training_minutes: list[DataPoint] = field(default_factory=list)


SOURCE_PRIORITY = {
    "garmin": 1,
    "whoop": 2,
    "eight_sleep": 3,
    "apple_health": 4,
    "google": 5,
}


def _best_per_date(rows: list[tuple[date, str, float | None]]) -> list[DataPoint]:
    best: dict[str, tuple[int, float | None]] = {}
    for d, source, value in rows:
        dk = d.isoformat()
        priority = SOURCE_PRIORITY.get(source, 99)
        existing = best.get(dk)
        if existing is None:
            if value is not None:
                best[dk] = (priority, value)
        elif value is not None and (existing[1] is None or priority < existing[0]):
            best[dk] = (priority, value)
    return [
        DataPoint(date=dk, value=pv[1])
        for dk, pv in sorted(best.items())
        if pv[1] is not None
    ]


def _to_points(rows, value_attr: str) -> list[DataPoint]:
    return [
        DataPoint(date=row.date.isoformat(), value=getattr(row, value_attr))
        for row in rows
        if getattr(row, value_attr) is not None
    ]


def load_raw_health_data(
    db: Session,
    user_id: int,
    days_back: int = 1825,
    ref_date: date | None = None,
) -> RawHealthData:
    from models import (
        HRV,
        EightSleepSession,
        Energy,
        GarminActivity,
        GarminTrainingStatus,
        HeartRate,
        Sleep,
        Steps,
        Stress,
        Weight,
        WhoopCycle,
        WhoopRecovery,
        WhoopSleep,
        WorkoutSet,
    )

    anchor = ref_date or local_today()
    cutoff = anchor - timedelta(days=days_back)
    raw = RawHealthData()

    garmin_hrv = (
        db.query(HRV)
        .filter(
            HRV.user_id == user_id,
            HRV.date >= cutoff,
            HRV.date <= anchor,
            HRV.source == "garmin",
        )
        .order_by(HRV.date)
        .all()
    )
    raw.hrv_garmin = _to_points(garmin_hrv, "hrv_avg")

    whoop_recovery = (
        db.query(WhoopRecovery)
        .filter(
            WhoopRecovery.user_id == user_id,
            WhoopRecovery.date >= cutoff,
            WhoopRecovery.date <= anchor,
        )
        .order_by(WhoopRecovery.date)
        .all()
    )
    raw.hrv_whoop = _to_points(whoop_recovery, "hrv_rmssd")
    raw.rhr_whoop = _to_points(whoop_recovery, "resting_heart_rate")
    raw.recovery = _to_points(whoop_recovery, "recovery_score")

    garmin_sleep = (
        db.query(Sleep)
        .filter(
            Sleep.user_id == user_id,
            Sleep.date >= cutoff,
            Sleep.date <= anchor,
            Sleep.source == "garmin",
        )
        .order_by(Sleep.date)
        .all()
    )
    raw.sleep_garmin = _to_points(garmin_sleep, "total_sleep_minutes")
    raw.sleep_deep_garmin = _to_points(garmin_sleep, "deep_minutes")
    raw.sleep_rem_garmin = _to_points(garmin_sleep, "rem_minutes")
    raw.sleep_awake_count_garmin = _to_points(garmin_sleep, "awake_count")
    raw.sleep_efficiency_garmin = [
        DataPoint(
            date=row.date.isoformat(),
            value=round(
                row.total_sleep_minutes
                / (row.total_sleep_minutes + row.awake_minutes)
                * 100,
                1,
            ),
        )
        for row in garmin_sleep
        if row.total_sleep_minutes
        and row.total_sleep_minutes > 0
        and row.awake_minutes is not None
    ]
    raw.respiratory_rate_garmin = _to_points(garmin_sleep, "respiratory_rate")

    whoop_sleep = (
        db.query(WhoopSleep)
        .filter(
            WhoopSleep.user_id == user_id,
            WhoopSleep.date >= cutoff,
            WhoopSleep.date <= anchor,
        )
        .order_by(WhoopSleep.date)
        .all()
    )
    raw.sleep_whoop = _to_points(whoop_sleep, "total_sleep_duration_minutes")
    raw.sleep_deep_whoop = _to_points(whoop_sleep, "deep_sleep_minutes")
    raw.sleep_rem_whoop = _to_points(whoop_sleep, "rem_sleep_minutes")
    raw.sleep_efficiency_whoop = _to_points(whoop_sleep, "sleep_efficiency_percentage")
    raw.respiratory_rate_whoop = _to_points(whoop_sleep, "respiratory_rate")

    garmin_hr = (
        db.query(HeartRate)
        .filter(
            HeartRate.user_id == user_id,
            HeartRate.date >= cutoff,
            HeartRate.date <= anchor,
            HeartRate.source == "garmin",
        )
        .order_by(HeartRate.date)
        .all()
    )
    raw.rhr_garmin = _to_points(garmin_hr, "resting_hr")

    stress_rows = (
        db.query(Stress.date, Stress.source, Stress.avg_stress)
        .filter(Stress.user_id == user_id, Stress.date >= cutoff, Stress.date <= anchor)
        .order_by(Stress.date)
        .all()
    )
    raw.stress = _best_per_date([(r.date, r.source, r.avg_stress) for r in stress_rows])

    steps_rows = (
        db.query(Steps.date, Steps.source, Steps.total_steps)
        .filter(Steps.user_id == user_id, Steps.date >= cutoff, Steps.date <= anchor)
        .order_by(Steps.date)
        .all()
    )
    raw.steps = _best_per_date(
        [
            (r.date, r.source, float(r.total_steps) if r.total_steps else None)
            for r in steps_rows
        ]
    )

    weight_all_rows = (
        db.query(Weight)
        .filter(Weight.user_id == user_id, Weight.date >= cutoff, Weight.date <= anchor)
        .order_by(Weight.date)
        .all()
    )
    raw.weight = _best_per_date(
        [(r.date, r.source, r.weight_kg) for r in weight_all_rows]
    )

    energy_rows = (
        db.query(Energy.date, Energy.source, Energy.active_energy, Energy.basal_energy)
        .filter(Energy.user_id == user_id, Energy.date >= cutoff, Energy.date <= anchor)
        .order_by(Energy.date)
        .all()
    )
    raw.energy = _best_per_date(
        [
            (
                r.date,
                r.source,
                (
                    (r.active_energy or 0) + (r.basal_energy or 0)
                    if r.active_energy is not None or r.basal_energy is not None
                    else None
                ),
            )
            for r in energy_rows
        ]
    )

    whoop_cycles = (
        db.query(WhoopCycle)
        .filter(
            WhoopCycle.user_id == user_id,
            WhoopCycle.date >= cutoff,
            WhoopCycle.date <= anchor,
        )
        .order_by(WhoopCycle.date)
        .all()
    )
    raw.strain_whoop = _to_points(whoop_cycles, "strain")
    raw.calories_whoop = [
        DataPoint(date=c.date.isoformat(), value=round(c.kilojoules / 4.184))
        for c in whoop_cycles
        if c.kilojoules is not None
    ]

    garmin_training = (
        db.query(GarminTrainingStatus)
        .filter(
            GarminTrainingStatus.user_id == user_id,
            GarminTrainingStatus.date >= cutoff,
            GarminTrainingStatus.date <= anchor,
        )
        .order_by(GarminTrainingStatus.date)
        .all()
    )
    raw.strain_garmin = _to_points(garmin_training, "acute_training_load")
    raw.calories_garmin = _to_points(garmin_training, "total_kilocalories")
    raw.vo2_max = _to_points(garmin_training, "vo2_max")
    raw.training_readiness = _to_points(garmin_training, "training_readiness_score")
    raw.fitness_age = [
        DataPoint(date=row.date.isoformat(), value=float(row.fitness_age))
        for row in garmin_training
        if row.fitness_age is not None
    ]

    raw.body_fat = [
        DataPoint(date=row.date.isoformat(), value=row.body_fat_pct)
        for row in weight_all_rows
        if row.body_fat_pct is not None
    ]

    garmin_activities = (
        db.query(GarminActivity)
        .filter(
            GarminActivity.user_id == user_id,
            GarminActivity.date >= cutoff,
            GarminActivity.date <= anchor,
        )
        .order_by(GarminActivity.date)
        .all()
    )
    raw.zone2_minutes = [
        DataPoint(
            date=row.date.isoformat(),
            value=round(row.hr_zone_two_seconds / 60, 1),
        )
        for row in garmin_activities
        if row.hr_zone_two_seconds is not None
    ]
    raw.zone5_minutes = [
        DataPoint(
            date=row.date.isoformat(),
            value=round(row.hr_zone_five_seconds / 60, 1),
        )
        for row in garmin_activities
        if row.hr_zone_five_seconds is not None
    ]
    raw.total_training_minutes = [
        DataPoint(
            date=row.date.isoformat(),
            value=round(row.duration_seconds / 60, 1),
        )
        for row in garmin_activities
        if row.duration_seconds is not None
    ]

    workout_dates_raw = (
        db.query(WorkoutSet.date)
        .filter(
            WorkoutSet.user_id == user_id,
            WorkoutSet.date >= cutoff,
            WorkoutSet.date <= anchor,
        )
        .distinct()
        .order_by(WorkoutSet.date)
        .all()
    )
    raw.workout_dates = [
        DataPoint(date=row.date.isoformat(), value=1.0) for row in workout_dates_raw
    ]

    eight_sleep_sessions = (
        db.query(EightSleepSession)
        .filter(
            EightSleepSession.user_id == user_id,
            EightSleepSession.date >= cutoff,
            EightSleepSession.date <= anchor,
        )
        .order_by(EightSleepSession.date)
        .all()
    )
    raw.hrv_eight_sleep = _to_points(eight_sleep_sessions, "hrv")
    raw.rhr_eight_sleep = _to_points(eight_sleep_sessions, "heart_rate")
    raw.sleep_eight_sleep = [
        DataPoint(
            date=row.date.isoformat(),
            value=round(row.sleep_duration_seconds / 60, 1),
        )
        for row in eight_sleep_sessions
        if row.sleep_duration_seconds is not None
    ]
    raw.sleep_deep_eight_sleep = [
        DataPoint(
            date=row.date.isoformat(),
            value=round(row.deep_duration_seconds / 60, 1),
        )
        for row in eight_sleep_sessions
        if row.deep_duration_seconds is not None
    ]
    raw.sleep_rem_eight_sleep = [
        DataPoint(
            date=row.date.isoformat(),
            value=round(row.rem_duration_seconds / 60, 1),
        )
        for row in eight_sleep_sessions
        if row.rem_duration_seconds is not None
    ]
    raw.sleep_light_eight_sleep = [
        DataPoint(
            date=row.date.isoformat(),
            value=round(row.light_duration_seconds / 60, 1),
        )
        for row in eight_sleep_sessions
        if row.light_duration_seconds is not None
    ]
    raw.respiratory_rate_eight_sleep = _to_points(
        eight_sleep_sessions, "respiratory_rate"
    )
    raw.sleep_score_eight_sleep = _to_points(eight_sleep_sessions, "score")
    raw.bed_temp = _to_points(eight_sleep_sessions, "bed_temp_celsius")
    raw.room_temp = _to_points(eight_sleep_sessions, "room_temp_celsius")
    raw.sleep_latency = [
        DataPoint(
            date=row.date.isoformat(),
            value=round(row.latency_asleep_seconds / 60, 1),
        )
        for row in eight_sleep_sessions
        if row.latency_asleep_seconds is not None
    ]
    raw.sleep_fitness_score = _to_points(eight_sleep_sessions, "sleep_fitness_score")
    raw.sleep_routine_score = _to_points(eight_sleep_sessions, "sleep_routine_score")
    raw.sleep_quality_score_es = _to_points(eight_sleep_sessions, "sleep_quality_score")
    raw.toss_and_turn = _to_points(eight_sleep_sessions, "tnt")

    return raw


def load_ml_insights(
    db: Session,
    user_id: int,
    ref_date: date | None = None,
    anomaly_lookback_days: int = 14,
) -> MLInsights:
    from models import Anomaly, Prediction

    anchor = ref_date or local_today()
    historical_cutoff = anchor - timedelta(days=7)
    anomaly_cutoff = anchor - timedelta(days=anomaly_lookback_days)

    all_prediction_rows = (
        db.query(Prediction)
        .filter(
            Prediction.user_id == user_id,
            Prediction.target_date >= historical_cutoff,
        )
        .order_by(Prediction.metric, Prediction.target_date)
        .all()
    )

    by_metric: dict[str, list[MLForecastPoint]] = defaultdict(list)
    by_metric_hist: dict[str, list[MLForecastPoint]] = defaultdict(list)
    for r in all_prediction_rows:
        point = MLForecastPoint(
            target_date=r.target_date.isoformat(),
            horizon_days=r.horizon_days,
            p10=r.p10,
            p50=r.p50,
            p90=r.p90,
        )
        if r.target_date >= anchor:
            by_metric[r.metric].append(point)
        else:
            by_metric_hist[r.metric].append(point)

    forecasts = [
        MLForecastMetric(metric=m, forecasts=pts) for m, pts in by_metric.items()
    ]
    historical_forecasts = [
        MLForecastMetric(metric=m, forecasts=pts) for m, pts in by_metric_hist.items()
    ]

    anomaly_rows = (
        db.query(Anomaly)
        .filter(
            Anomaly.user_id == user_id,
            Anomaly.date >= anomaly_cutoff,
            Anomaly.date <= anchor,
        )
        .order_by(Anomaly.date.desc())
        .all()
    )

    ml_anomalies = [
        MLAnomalyRecord(
            date=r.date.isoformat(),
            anomaly_score=r.anomaly_score,
            contributing_factors=r.contributing_factors,
        )
        for r in anomaly_rows
    ]

    has_recent = any((anchor - r.date).days <= 2 for r in anomaly_rows)

    return MLInsights(
        forecasts=forecasts,
        historical_forecasts=historical_forecasts,
        ml_anomalies=ml_anomalies,
        has_active_forecasts=len(forecasts) > 0,
        has_historical_forecasts=len(historical_forecasts) > 0,
        has_recent_ml_anomalies=has_recent,
    )
