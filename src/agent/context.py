from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from analytics import TrendMode
from analytics.alert_manager import get_active_alerts, process_alerts
from analytics.pipeline import compute_and_store_snapshot
from analytics.smart_context import build_smart_context
from database import get_db_session_context
from models import GarminActivity, WorkoutSet

logger = logging.getLogger(__name__)


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
            if active_alerts:
                ctx["active_clinical_alerts"] = active_alerts

        return ctx  # type: ignore[no-any-return]
    except Exception:
        logger.exception("build_weekly_context_failed")
        return {
            "period": f"{start_date} to {end_date}",
            "error": "Health data temporarily unavailable",
        }


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
