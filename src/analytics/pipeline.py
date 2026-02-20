from __future__ import annotations

import datetime
import logging
from datetime import date

from sqlalchemy.orm import Session

from .constants import TREND_MODES
from .date_utils import local_today
from .service import compute_health_analysis
from .types import HealthAnalysis, TrendMode

logger = logging.getLogger(__name__)


def compute_and_store_snapshot(
    db: Session,
    user_id: int,
    mode: TrendMode = TrendMode.RECENT,
    target_date: date | None = None,
) -> HealthAnalysis:
    from models import HealthSnapshot

    analysis = compute_health_analysis(db, user_id, mode=mode, target_date=target_date)
    snapshot_date = target_date or local_today()

    existing = (
        db.query(HealthSnapshot)
        .filter_by(user_id=user_id, date=snapshot_date, mode=mode.value)
        .first()
    )

    snapshot_data = analysis.model_dump(
        exclude_none=True, exclude={"mode", "mode_config"}
    )

    if existing:
        existing.snapshot_json = snapshot_data
        existing.health_score = (
            analysis.health_score.overall if analysis.health_score else None
        )
        existing.computed_at = datetime.datetime.utcnow()
    else:
        snapshot = HealthSnapshot(
            user_id=user_id,
            date=snapshot_date,
            mode=mode.value,
            snapshot_json=snapshot_data,
            health_score=(
                analysis.health_score.overall if analysis.health_score else None
            ),
        )
        db.add(snapshot)

    db.flush()
    return analysis


def get_cached_snapshot(
    db: Session,
    user_id: int,
    mode: TrendMode = TrendMode.RECENT,
    target_date: date | None = None,
    max_age_minutes: int = 60,
) -> HealthAnalysis | None:
    from models import HealthSnapshot

    snapshot_date = target_date or local_today()
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(minutes=max_age_minutes)

    existing = (
        db.query(HealthSnapshot)
        .filter_by(user_id=user_id, date=snapshot_date, mode=mode.value)
        .filter(HealthSnapshot.computed_at >= cutoff)
        .first()
    )

    if not existing:
        return None

    try:
        config = TREND_MODES[mode]
        return HealthAnalysis.model_validate(  # type: ignore[no-any-return]
            {
                **existing.snapshot_json,
                "mode": mode.value,
                "mode_config": config.model_dump(),
            }
        )
    except Exception:
        logger.warning(
            "cached_snapshot_invalid user=%d date=%s", user_id, snapshot_date
        )
        return None


def get_or_compute_snapshot(
    db: Session,
    user_id: int,
    mode: TrendMode = TrendMode.RECENT,
    target_date: date | None = None,
    max_age_minutes: int = 60,
) -> HealthAnalysis:
    cached = get_cached_snapshot(db, user_id, mode, target_date, max_age_minutes)
    if cached is not None:
        return cached
    return compute_and_store_snapshot(db, user_id, mode, target_date)


def on_data_sync_complete(db: Session, user_id: int) -> None:
    try:
        target = local_today()
        analysis = compute_and_store_snapshot(
            db, user_id, mode=TrendMode.RECENT, target_date=target
        )
        from .alert_manager import process_alerts

        process_alerts(db, user_id, analysis)
    except Exception:
        logger.warning("post_sync_recompute_failed user=%d", user_id, exc_info=True)
