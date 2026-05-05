from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from analytics import TrendMode
from analytics.alert_manager import get_active_alerts, process_alerts
from analytics.pipeline import compute_and_store_snapshot
from analytics.smart_context import build_smart_context
from database import get_db_session_context
from logging_config import get_logger
from models import (
    GarminActivity,
    GarminRacePrediction,
    GarminTrainingStatus,
    LongevityGoal,
    WhoopRecovery,
    WorkoutSet,
)

logger = get_logger(__name__)


def _local_now() -> datetime:
    offset_hours = int(os.getenv("BOT_TIMEZONE_OFFSET_HOURS", "0"))
    tz = timezone(timedelta(hours=offset_hours))
    return datetime.now(tz)


def build_daily_context(user_id: int, target_date: date | None = None) -> dict:
    if target_date is None:
        target_date = _local_now().date()

    try:
        with get_db_session_context() as db:
            analysis = compute_and_store_snapshot(
                db, user_id, mode=TrendMode.RECENT, target_date=target_date
            )
            new_alerts = process_alerts(db, user_id, analysis)
            active_alerts = get_active_alerts(db, user_id)

            ctx = build_smart_context(analysis, max_anomalies=3)
            now = _local_now()
            ctx["current_datetime"] = now.strftime("%Y-%m-%d %H:%M %Z")
            ctx["date"] = str(target_date)
            ctx["recent_workouts"] = _get_recent_workouts(
                db, user_id, target_date, days=3
            )
            ctx["recent_strength"] = _get_recent_strength(
                db, user_id, target_date, days=3
            )
            training_status = _get_garmin_training_status(db, user_id, target_date)
            if training_status:
                ctx["garmin_training_status"] = training_status
            whoop_recovery = _get_latest_whoop_recovery(db, user_id, target_date)
            if whoop_recovery:
                ctx["whoop_recovery"] = whoop_recovery
            longevity_goals = _get_longevity_goals(db, user_id)
            if longevity_goals:
                ctx["longevity_goals"] = longevity_goals
            if active_alerts:
                ctx["active_clinical_alerts"] = active_alerts
            if new_alerts:
                ctx["new_clinical_alerts"] = new_alerts

        return ctx  # type: ignore[no-any-return]
    except Exception:
        logger.exception("build_daily_context_failed")
        return {
            "date": str(target_date),
            "error": "Health data temporarily unavailable",
        }


def build_weekly_context(user_id: int, end_date: date | None = None) -> dict:
    if end_date is None:
        end_date = _local_now().date()
    start_date = end_date - timedelta(days=7)

    try:
        with get_db_session_context() as db:
            analysis = compute_and_store_snapshot(
                db, user_id, mode=TrendMode.QUARTER, target_date=end_date
            )
            process_alerts(db, user_id, analysis)
            active_alerts = get_active_alerts(db, user_id)

            ctx = build_smart_context(analysis, max_anomalies=5)
            now = _local_now()
            ctx["current_datetime"] = now.strftime("%Y-%m-%d %H:%M %Z")
            ctx["period"] = f"{start_date} to {end_date}"
            ctx["workouts"] = _get_recent_workouts(db, user_id, end_date, days=7)
            ctx["strength"] = _get_recent_strength(db, user_id, end_date, days=7)
            training_status = _get_garmin_training_status(db, user_id, end_date)
            if training_status:
                ctx["garmin_training_status"] = training_status
            race_preds = _get_latest_race_predictions(db, user_id, end_date)
            if race_preds:
                ctx["race_predictions"] = race_preds
            longevity_goals = _get_longevity_goals(db, user_id)
            if longevity_goals:
                ctx["longevity_goals"] = longevity_goals
            if active_alerts:
                ctx["active_clinical_alerts"] = active_alerts

        return ctx  # type: ignore[no-any-return]
    except Exception:
        logger.exception("build_weekly_context_failed")
        return {
            "period": f"{start_date} to {end_date}",
            "error": "Health data temporarily unavailable",
        }


def build_chat_context(user_id: int) -> str:
    ctx = build_daily_context(user_id)

    parts = [f"Time: {ctx.get('current_datetime', 'unknown')}"]

    hs = ctx.get("health_score", {})
    if hs:
        parts.append(
            f"Health Score: overall={hs.get('overall', '?')}, "
            f"recovery={hs.get('recovery_core', '?')}, "
            f"training={hs.get('training_load', '?')}, "
            f"confidence={hs.get('data_confidence', '?')}"
        )

    alerts = ctx.get("active_clinical_alerts")
    if alerts:
        parts.append(f"Active alerts: {alerts}")

    illness = ctx.get("illness_risk", {})
    if illness.get("risk_level") in ("moderate", "high"):
        parts.append(f"Illness risk: {illness['risk_level']}")

    overreaching = ctx.get("overreaching", {})
    if overreaching.get("risk_level") in ("high", "critical"):
        parts.append(f"Overreaching: {overreaching['risk_level']}")

    return "\n".join(parts)


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


def _get_garmin_training_status(db: Session, user_id: int, d: date) -> dict | None:
    row = (
        db.query(GarminTrainingStatus)
        .filter(
            GarminTrainingStatus.user_id == user_id,
            GarminTrainingStatus.date <= d,
        )
        .order_by(GarminTrainingStatus.date.desc())
        .first()
    )
    if not row:
        return None
    return {
        "date": str(row.date),
        "vo2_max": row.vo2_max,
        "fitness_age": row.fitness_age,
        "training_status": row.training_status,
        "training_load_7_day": row.training_load_7_day,
        "training_readiness_score": row.training_readiness_score,
        "endurance_score": row.endurance_score,
    }


def _get_latest_whoop_recovery(db: Session, user_id: int, d: date) -> dict | None:
    row = (
        db.query(WhoopRecovery)
        .filter(
            WhoopRecovery.user_id == user_id,
            WhoopRecovery.date <= d,
        )
        .order_by(WhoopRecovery.date.desc())
        .first()
    )
    if not row:
        return None
    return {
        "date": str(row.date),
        "recovery_score": row.recovery_score,
        "hrv_rmssd": row.hrv_rmssd,
        "resting_hr": row.resting_heart_rate,
        "spo2": row.spo2_percentage,
    }


def _get_latest_race_predictions(db: Session, user_id: int, d: date) -> dict | None:
    row = (
        db.query(GarminRacePrediction)
        .filter(
            GarminRacePrediction.user_id == user_id,
            GarminRacePrediction.date <= d,
        )
        .order_by(GarminRacePrediction.date.desc())
        .first()
    )
    if not row:
        return None

    def _fmt(s: int | None) -> str | None:
        if s is None:
            return None
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"

    return {
        "date": str(row.date),
        "5k": _fmt(row.prediction_5k_seconds),
        "10k": _fmt(row.prediction_10k_seconds),
        "half_marathon": _fmt(row.prediction_half_marathon_seconds),
        "marathon": _fmt(row.prediction_marathon_seconds),
        "vo2_max": row.vo2_max_value,
    }


def _get_longevity_goals(db: Session, user_id: int) -> list[dict]:
    rows = (
        db.query(LongevityGoal)
        .filter(LongevityGoal.user_id == user_id)
        .order_by(LongevityGoal.category)
        .all()
    )
    return [
        {
            "category": r.category,
            "description": r.description,
            "target_value": r.target_value,
            "current_value": r.current_value,
            "unit": r.unit,
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
