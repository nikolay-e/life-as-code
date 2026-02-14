from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db_session_context
from models import (
    HRV,
    Anomaly,
    Energy,
    GarminActivity,
    HeartRate,
    Prediction,
    Sleep,
    Steps,
    Stress,
    Weight,
    WorkoutSet,
)


def build_daily_context(user_id: int, target_date: date | None = None) -> dict:
    if target_date is None:
        target_date = date.today()

    with get_db_session_context() as db:
        ctx = {
            "date": str(target_date),
            "today": _get_day_metrics(db, user_id, target_date),
            "week_avg": _get_rolling_averages(db, user_id, target_date, days=7),
            "month_avg": _get_rolling_averages(db, user_id, target_date, days=30),
            "forecasts": _get_active_forecasts(db, user_id, target_date),
            "recent_anomalies": _get_recent_anomalies(db, user_id, target_date, days=3),
            "recent_workouts": _get_recent_workouts(db, user_id, target_date, days=3),
            "recent_strength": _get_recent_strength(db, user_id, target_date, days=3),
        }

    return ctx


def build_weekly_context(user_id: int, end_date: date | None = None) -> dict:
    if end_date is None:
        end_date = date.today()
    start_date = end_date - timedelta(days=7)

    with get_db_session_context() as db:
        daily_metrics: list[dict] = []
        ctx = {
            "period": f"{start_date} to {end_date}",
            "daily_metrics": daily_metrics,
            "week_avg": _get_rolling_averages(db, user_id, end_date, days=7),
            "prev_week_avg": _get_rolling_averages(db, user_id, start_date, days=7),
            "month_avg": _get_rolling_averages(db, user_id, end_date, days=30),
            "forecasts": _get_active_forecasts(db, user_id, end_date),
            "anomalies": _get_recent_anomalies(db, user_id, end_date, days=7),
            "workouts": _get_recent_workouts(db, user_id, end_date, days=7),
            "strength": _get_recent_strength(db, user_id, end_date, days=7),
        }

        current = start_date
        while current <= end_date:
            day_data = _get_day_metrics(db, user_id, current)
            if day_data:
                day_data["date"] = str(current)
                daily_metrics.append(day_data)
            current += timedelta(days=1)

    return ctx


def _get_day_metrics(db: Session, user_id: int, d: date) -> dict:
    metrics = {}

    sleep = db.query(Sleep).filter(Sleep.user_id == user_id, Sleep.date == d).first()
    if sleep:
        metrics["sleep"] = {
            "total_minutes": sleep.total_sleep_minutes,
            "deep_minutes": sleep.deep_minutes,
            "rem_minutes": sleep.rem_minutes,
            "light_minutes": sleep.light_minutes,
            "awake_minutes": sleep.awake_minutes,
            "score": sleep.sleep_score,
        }

    hrv = db.query(HRV).filter(HRV.user_id == user_id, HRV.date == d).first()
    if hrv:
        metrics["hrv"] = {"avg": hrv.hrv_avg, "status": hrv.hrv_status}

    hr = (
        db.query(HeartRate)
        .filter(HeartRate.user_id == user_id, HeartRate.date == d)
        .first()
    )
    if hr:
        metrics["heart_rate"] = {
            "resting": hr.resting_hr,
            "max": hr.max_hr,
            "avg": hr.avg_hr,
        }

    weight = (
        db.query(Weight).filter(Weight.user_id == user_id, Weight.date == d).first()
    )
    if weight:
        metrics["weight"] = {
            "kg": weight.weight_kg,
            "body_fat_pct": weight.body_fat_pct,
        }

    steps = db.query(Steps).filter(Steps.user_id == user_id, Steps.date == d).first()
    if steps:
        metrics["steps"] = {
            "total": steps.total_steps,
            "distance_m": steps.total_distance,
            "active_minutes": steps.active_minutes,
        }

    energy = (
        db.query(Energy).filter(Energy.user_id == user_id, Energy.date == d).first()
    )
    if energy:
        metrics["energy"] = {
            "active_kcal": energy.active_energy,
            "basal_kcal": energy.basal_energy,
        }

    stress = (
        db.query(Stress).filter(Stress.user_id == user_id, Stress.date == d).first()
    )
    if stress:
        metrics["stress"] = {
            "avg": stress.avg_stress,
            "max": stress.max_stress,
            "level": stress.stress_level,
        }

    return metrics


def _get_rolling_averages(db: Session, user_id: int, end_date: date, days: int) -> dict:
    start = end_date - timedelta(days=days)
    avgs = {}

    result = (
        db.query(func.avg(Steps.total_steps))
        .filter(Steps.user_id == user_id, Steps.date.between(start, end_date))
        .scalar()
    )
    if result:
        avgs["steps"] = round(float(result), 0)

    result = (
        db.query(func.avg(Sleep.total_sleep_minutes), func.avg(Sleep.deep_minutes))
        .filter(Sleep.user_id == user_id, Sleep.date.between(start, end_date))
        .first()
    )
    if result and result[0]:
        avgs["sleep_total_min"] = round(float(result[0]), 0)
        if result[1]:
            avgs["sleep_deep_min"] = round(float(result[1]), 0)

    result = (
        db.query(func.avg(HeartRate.resting_hr))
        .filter(HeartRate.user_id == user_id, HeartRate.date.between(start, end_date))
        .scalar()
    )
    if result:
        avgs["resting_hr"] = round(float(result), 1)

    result = (
        db.query(func.avg(HRV.hrv_avg))
        .filter(HRV.user_id == user_id, HRV.date.between(start, end_date))
        .scalar()
    )
    if result:
        avgs["hrv"] = round(float(result), 1)

    result = (
        db.query(func.avg(Weight.weight_kg))
        .filter(Weight.user_id == user_id, Weight.date.between(start, end_date))
        .scalar()
    )
    if result:
        avgs["weight_kg"] = round(float(result), 1)

    return avgs


def _get_active_forecasts(db: Session, user_id: int, d: date) -> list[dict]:
    rows = (
        db.query(Prediction)
        .filter(Prediction.user_id == user_id, Prediction.target_date >= d)
        .order_by(Prediction.metric, Prediction.target_date)
        .all()
    )
    return [
        {
            "metric": r.metric,
            "target_date": str(r.target_date),
            "horizon_days": r.horizon_days,
            "p10": r.p10,
            "p50": r.p50,
            "p90": r.p90,
        }
        for r in rows
    ]


def _get_recent_anomalies(db: Session, user_id: int, d: date, days: int) -> list[dict]:
    start = d - timedelta(days=days)
    rows = (
        db.query(Anomaly)
        .filter(
            Anomaly.user_id == user_id,
            Anomaly.date >= start,
            Anomaly.date <= d,
        )
        .order_by(Anomaly.date.desc())
        .all()
    )
    return [
        {
            "date": str(r.date),
            "anomaly_score": r.anomaly_score,
            "contributing_factors": r.contributing_factors,
        }
        for r in rows
    ]


def _get_recent_workouts(db: Session, user_id: int, d: date, days: int) -> list[dict]:
    start = d - timedelta(days=days)
    rows = (
        db.query(GarminActivity)
        .filter(
            GarminActivity.user_id == user_id,
            GarminActivity.date >= start,
            GarminActivity.date <= d,
        )
        .order_by(GarminActivity.date.desc())
        .all()
    )
    return [
        {
            "date": str(r.date),
            "type": r.activity_type,
            "duration_min": (
                round(r.duration_seconds / 60, 0) if r.duration_seconds else None
            ),
            "avg_hr": r.avg_heart_rate,
            "max_hr": r.max_heart_rate,
            "calories": r.calories,
        }
        for r in rows
    ]


def _get_recent_strength(db: Session, user_id: int, d: date, days: int) -> list[dict]:
    start = d - timedelta(days=days)
    rows = (
        db.query(
            WorkoutSet.date,
            WorkoutSet.exercise,
            func.count(WorkoutSet.id).label("sets"),
            func.max(WorkoutSet.weight_kg).label("max_weight"),
            func.sum(WorkoutSet.reps).label("total_reps"),
        )
        .filter(
            WorkoutSet.user_id == user_id,
            WorkoutSet.date >= start,
            WorkoutSet.date <= d,
        )
        .group_by(WorkoutSet.date, WorkoutSet.exercise)
        .order_by(WorkoutSet.date.desc())
        .all()
    )
    return [
        {
            "date": str(r.date),
            "exercise": r.exercise,
            "sets": r.sets,
            "max_weight_kg": float(r.max_weight) if r.max_weight else None,
            "total_reps": r.total_reps,
        }
        for r in rows
    ]
