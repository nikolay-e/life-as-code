import datetime
import threading
from collections.abc import Callable
from datetime import timedelta
from typing import Any, cast

from sqlalchemy import select

from database import get_db_session_context
from enums import DataSource, SyncWindow, SyncWindowStatus
from logging_config import get_logger
from models import SyncProgress, UserCredentials
from sync_manager import is_sync_in_progress

logger = get_logger(__name__)

WINDOW_DAYS: dict[str, int | None] = {
    SyncWindow.DAY.value: 1,
    SyncWindow.WEEK.value: 7,
    SyncWindow.MONTH.value: 30,
    SyncWindow.YEAR.value: 365,
    SyncWindow.ALL.value: None,
}

MIN_SYNC_INTERVAL_MINUTES = 15

_progressive_sync_threads: dict[tuple[int, str], threading.Thread] = {}
_progressive_sync_lock = threading.Lock()

_background_sync_threads: dict[int, threading.Thread] = {}
_background_sync_lock = threading.Lock()


def should_start_sync(user_id: int, source: str) -> bool:
    with get_db_session_context() as db:
        progress = db.scalars(
            select(SyncProgress).where(
                SyncProgress.user_id == user_id, SyncProgress.source == source
            )
        ).first()

        if not progress:
            return True

        if progress.window_status == SyncWindowStatus.IN_PROGRESS.value:
            return False

        if progress.last_sync_started_at:
            elapsed = datetime.datetime.utcnow() - progress.last_sync_started_at
            if elapsed < timedelta(minutes=MIN_SYNC_INTERVAL_MINUTES):
                return False

        return True


def get_or_create_sync_progress(user_id: int, source: str) -> SyncProgress:
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.exc import IntegrityError

    with get_db_session_context() as db:
        progress = db.scalars(
            select(SyncProgress).where(
                SyncProgress.user_id == user_id, SyncProgress.source == source
            )
        ).first()

        if progress:
            return progress

        try:
            stmt = (
                pg_insert(SyncProgress)
                .values(
                    user_id=user_id,
                    source=source,
                    current_window=SyncWindow.DAY.value,
                    window_status=SyncWindowStatus.PENDING.value,
                )
                .on_conflict_do_nothing(index_elements=["user_id", "source"])
                .returning(SyncProgress)
            )

            result = db.execute(stmt)
            db.commit()

            progress = result.scalars().first()
            if progress:
                return progress

            progress = db.scalars(
                select(SyncProgress).where(
                    SyncProgress.user_id == user_id, SyncProgress.source == source
                )
            ).first()

            if progress:
                return progress

            raise RuntimeError(
                f"Failed to get or create SyncProgress for user {user_id}, source {source}"
            )

        except IntegrityError:
            db.rollback()
            progress = db.scalars(
                select(SyncProgress).where(
                    SyncProgress.user_id == user_id, SyncProgress.source == source
                )
            ).first()
            if progress:
                return progress
            raise


def get_sync_date_range(window: str, reference_date: datetime.date | None = None):
    today = reference_date or datetime.date.today()
    days = WINDOW_DAYS.get(window)

    if days is None:
        return None, today

    start_date = today - timedelta(days=days)
    return start_date, today


def needs_sync_for_window(user_id: int, source: str, window: str) -> bool:
    with get_db_session_context() as db:
        progress = db.scalars(
            select(SyncProgress).where(
                SyncProgress.user_id == user_id, SyncProgress.source == source
            )
        ).first()

        if not progress:
            return True

        if progress.is_window_completed(window):
            completed_date = getattr(
                progress,
                {
                    SyncWindow.DAY.value: "day_completed",
                    SyncWindow.WEEK.value: "week_completed",
                    SyncWindow.MONTH.value: "month_completed",
                    SyncWindow.YEAR.value: "year_completed",
                    SyncWindow.ALL.value: "full_sync_completed",
                }.get(window, "day_completed"),
            )

            if completed_date is not None:
                today = datetime.date.today()
                if window == SyncWindow.DAY.value:
                    return bool(completed_date < today)
                elif window == SyncWindow.WEEK.value:
                    return bool(completed_date < today - timedelta(days=1))
                else:
                    return False

        return True


def get_next_pending_window(user_id: int, source: str) -> str | None:
    with get_db_session_context() as db:
        progress = db.scalars(
            select(SyncProgress).where(
                SyncProgress.user_id == user_id, SyncProgress.source == source
            )
        ).first()

        if not progress:
            return cast(str, SyncWindow.DAY.value)

        window_order: list[str] = [
            SyncWindow.DAY.value,
            SyncWindow.WEEK.value,
            SyncWindow.MONTH.value,
            SyncWindow.YEAR.value,
            SyncWindow.ALL.value,
        ]

        for w in window_order:
            if needs_sync_for_window(user_id, source, w):
                return w

        return None


def update_sync_progress(
    user_id: int,
    source: str,
    window: str,
    status: str,
    oldest_date: datetime.date | None = None,
    newest_date: datetime.date | None = None,
    error_message: str | None = None,
):
    with get_db_session_context() as db:
        progress = db.scalars(
            select(SyncProgress).where(
                SyncProgress.user_id == user_id, SyncProgress.source == source
            )
        ).first()

        if not progress:
            progress = SyncProgress(user_id=user_id, source=source)
            db.add(progress)

        progress.current_window = window
        progress.window_status = status
        progress.updated_at = datetime.datetime.utcnow()

        if status == SyncWindowStatus.IN_PROGRESS.value:
            progress.last_sync_started_at = datetime.datetime.utcnow()
            progress.error_message = None
        elif status == SyncWindowStatus.COMPLETED.value:
            progress.last_sync_completed_at = datetime.datetime.utcnow()
            progress.mark_window_completed(window, datetime.date.today())
            if oldest_date:
                if (
                    not progress.oldest_synced_date
                    or oldest_date < progress.oldest_synced_date
                ):
                    progress.oldest_synced_date = oldest_date
            if newest_date:
                progress.newest_synced_date = newest_date
        elif status == SyncWindowStatus.FAILED.value:
            progress.error_message = error_message

        db.commit()


def has_credentials_for_source(user_id: int, source: str) -> bool:
    with get_db_session_context() as db:
        creds = db.scalars(
            select(UserCredentials).where(UserCredentials.user_id == user_id)
        ).first()

        if not creds:
            return False

        if source == DataSource.GARMIN.value:
            return bool(creds.garmin_email and creds.encrypted_garmin_password)
        elif source == DataSource.HEVY.value:
            return bool(creds.encrypted_hevy_api_key)
        elif source == DataSource.WHOOP.value:
            return bool(creds.encrypted_whoop_access_token)

        return False


def run_progressive_sync_for_source(
    user_id: int,
    source: str,
    sync_func: Callable[..., dict[str, Any]],
    max_windows: int | None = None,
) -> int:
    windows_processed = 0
    window = get_next_pending_window(user_id, source)

    while window and (max_windows is None or windows_processed < max_windows):
        if is_sync_in_progress(user_id, source):
            logger.info(
                "progressive_sync_waiting",
                user_id=user_id,
                source=source,
                window=window,
            )
            break

        logger.info(
            "progressive_sync_starting_window",
            user_id=user_id,
            source=source,
            window=window,
        )

        update_sync_progress(
            user_id, source, window, SyncWindowStatus.IN_PROGRESS.value
        )

        try:
            days = WINDOW_DAYS.get(window, 1)
            full_sync = window == SyncWindow.ALL.value

            result = sync_func(user_id, days=days or 730, full_sync=full_sync)

            if result.get("success", False):
                start_date, end_date = get_sync_date_range(window)
                update_sync_progress(
                    user_id,
                    source,
                    window,
                    SyncWindowStatus.COMPLETED.value,
                    oldest_date=start_date,
                    newest_date=end_date,
                )
                logger.info(
                    "progressive_sync_window_completed",
                    user_id=user_id,
                    source=source,
                    window=window,
                    records=result.get("total_records", 0),
                )
            else:
                update_sync_progress(
                    user_id,
                    source,
                    window,
                    SyncWindowStatus.FAILED.value,
                    error_message=result.get("error", "Unknown error"),
                )
                logger.error(
                    "progressive_sync_window_failed",
                    user_id=user_id,
                    source=source,
                    window=window,
                    error=result.get("error"),
                )
                break

        except Exception as e:
            update_sync_progress(
                user_id,
                source,
                window,
                SyncWindowStatus.FAILED.value,
                error_message=str(e),
            )
            logger.exception(
                "progressive_sync_exception",
                user_id=user_id,
                source=source,
                window=window,
            )
            break

        windows_processed += 1
        window = get_next_pending_window(user_id, source)

    return windows_processed


def start_progressive_sync(
    user_id: int, sources: list[str] | None = None, force: bool = False
) -> dict[str, str]:
    if sources is None:
        sources = [
            DataSource.GARMIN.value,
            DataSource.HEVY.value,
            DataSource.WHOOP.value,
        ]

    from pull_garmin_data import sync_garmin_data_for_user
    from pull_hevy_data import sync_hevy_data_for_user
    from pull_whoop_data import sync_whoop_data_for_user

    sync_funcs: dict[str, Callable[..., dict[str, Any]]] = {
        DataSource.GARMIN.value: sync_garmin_data_for_user,
        DataSource.HEVY.value: sync_hevy_data_for_user,
        DataSource.WHOOP.value: sync_whoop_data_for_user,
    }

    results: dict[str, str] = {}

    for source in sources:
        if not has_credentials_for_source(user_id, source):
            logger.debug(
                "progressive_sync_no_credentials", user_id=user_id, source=source
            )
            results[source] = "no_credentials"
            continue

        if not force and not should_start_sync(user_id, source):
            logger.debug(
                "progressive_sync_skipped_rate_limit", user_id=user_id, source=source
            )
            results[source] = "rate_limited"
            continue

        key = (user_id, source)
        with _progressive_sync_lock:
            existing_thread = _progressive_sync_threads.get(key)
            if existing_thread and existing_thread.is_alive():
                logger.info(
                    "progressive_sync_already_running", user_id=user_id, source=source
                )
                results[source] = "already_running"
                continue

            sync_func = sync_funcs.get(source)
            if not sync_func:
                results[source] = "no_sync_func"
                continue

            thread = threading.Thread(
                target=run_progressive_sync_for_source,
                args=(user_id, source, sync_func),
                kwargs={"max_windows": 1},
                daemon=True,
            )
            _progressive_sync_threads[key] = thread
            thread.start()

            logger.info(
                "progressive_sync_thread_started", user_id=user_id, source=source
            )
            results[source] = "started"

    return results


def start_background_progressive_sync(user_id: int) -> str:
    with _background_sync_lock:
        existing_thread = _background_sync_threads.get(user_id)
        if existing_thread and existing_thread.is_alive():
            logger.info("background_progressive_sync_already_running", user_id=user_id)
            return "already_running"

        thread = threading.Thread(
            target=_run_full_progressive_sync, args=(user_id,), daemon=True
        )
        _background_sync_threads[user_id] = thread
        thread.start()
        logger.info("background_progressive_sync_started", user_id=user_id)
        return "started"


def _run_full_progressive_sync(user_id: int):
    from pull_garmin_data import sync_garmin_data_for_user
    from pull_hevy_data import sync_hevy_data_for_user
    from pull_whoop_data import sync_whoop_data_for_user

    sync_funcs: dict[str, Callable[..., dict[str, Any]]] = {
        DataSource.GARMIN.value: sync_garmin_data_for_user,
        DataSource.HEVY.value: sync_hevy_data_for_user,
        DataSource.WHOOP.value: sync_whoop_data_for_user,
    }

    for source in [
        DataSource.GARMIN.value,
        DataSource.HEVY.value,
        DataSource.WHOOP.value,
    ]:
        if not has_credentials_for_source(user_id, source):
            continue

        sync_func = sync_funcs.get(source)
        if sync_func:
            run_progressive_sync_for_source(
                user_id, source, sync_func, max_windows=None
            )


def get_sync_progress_summary(user_id: int) -> dict[str, Any]:
    with get_db_session_context() as db:
        progress_list = db.scalars(
            select(SyncProgress).where(SyncProgress.user_id == user_id)
        ).all()

        summary: dict[str, Any] = {
            "sources": {},
            "overall_status": "complete",
            "has_pending_sync": False,
        }

        for progress in progress_list:
            source_summary = {
                "current_window": progress.current_window,
                "window_status": progress.window_status,
                "oldest_synced_date": (
                    progress.oldest_synced_date.isoformat()
                    if progress.oldest_synced_date
                    else None
                ),
                "newest_synced_date": (
                    progress.newest_synced_date.isoformat()
                    if progress.newest_synced_date
                    else None
                ),
                "windows_completed": {
                    "day": progress.day_completed is not None,
                    "week": progress.week_completed is not None,
                    "month": progress.month_completed is not None,
                    "year": progress.year_completed is not None,
                    "all": progress.full_sync_completed is not None,
                },
                "last_sync_at": (
                    progress.last_sync_completed_at.isoformat()
                    if progress.last_sync_completed_at
                    else None
                ),
                "error": progress.error_message,
            }
            summary["sources"][progress.source] = source_summary

            if progress.window_status == SyncWindowStatus.IN_PROGRESS.value:
                summary["overall_status"] = "syncing"
                summary["has_pending_sync"] = True
            elif progress.window_status == SyncWindowStatus.FAILED.value:
                summary["overall_status"] = "error"
            elif not progress.full_sync_completed:
                summary["has_pending_sync"] = True

        return summary
