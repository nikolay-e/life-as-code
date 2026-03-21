import os
import signal
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from database import get_db_session_context
from enums import DataSource
from logging_config import configure_logging, get_logger
from models import User
from sync_manager import is_sync_recently_active
from utils import has_credentials_for_source

configure_logging()
logger = get_logger("scheduler")


def _resolve_sync_interval_minutes() -> int:
    minutes_env = os.getenv("SYNC_INTERVAL_MINUTES")
    if minutes_env:
        return int(minutes_env)
    hours_env = os.getenv("SYNC_INTERVAL_HOURS")
    if hours_env:
        return int(hours_env) * 60
    return 5


SYNC_INTERVAL_MINUTES = _resolve_sync_interval_minutes()
SYNC_DAYS = int(os.getenv("SYNC_DAYS", "7"))
INITIAL_DELAY_SECONDS = 60
SOURCES = [DataSource.GARMIN.value, DataSource.HEVY.value, DataSource.WHOOP.value]

shutdown_requested = False


def handle_shutdown(signum, _frame):
    global shutdown_requested
    logger.info("scheduler_shutdown_signal", signal=signum)
    shutdown_requested = True


def interruptible_sleep(seconds):
    elapsed = 0
    while elapsed < seconds and not shutdown_requested:
        time.sleep(1)
        elapsed += 1


def _get_sync_funcs() -> dict:
    from pull_garmin_data import sync_garmin_data_for_user
    from pull_hevy_data import sync_hevy_data_for_user
    from pull_whoop_data import sync_whoop_data_for_user

    return {
        DataSource.GARMIN.value: sync_garmin_data_for_user,
        DataSource.HEVY.value: sync_hevy_data_for_user,
        DataSource.WHOOP.value: sync_whoop_data_for_user,
    }


def _sync_source_for_user(user_id: int, source: str, sync_func) -> None:
    logger.info(
        "scheduler_sync_starting", user_id=user_id, source=source, days=SYNC_DAYS
    )
    try:
        result = sync_func(user_id, days=SYNC_DAYS)
        logger.info(
            "scheduler_sync_completed",
            user_id=user_id,
            source=source,
            success=result.get("success", False),
            records=result.get("total_records", 0),
        )
    except Exception:
        logger.exception("scheduler_sync_error", user_id=user_id, source=source)


def _sync_user_sources(user_id: int, sync_funcs: dict) -> None:
    for source in SOURCES:
        if shutdown_requested:
            break
        if not has_credentials_for_source(user_id, source):
            continue
        if is_sync_recently_active(user_id, source):
            logger.info(
                "scheduler_skipping_active_sync", user_id=user_id, source=source
            )
            continue
        sync_func = sync_funcs.get(source)
        if not sync_func:
            continue
        _sync_source_for_user(user_id, source, sync_func)


def _recompute_analytics_for_user(user_id: int) -> None:
    try:
        from analytics.pipeline import on_data_sync_complete

        with get_db_session_context() as db:
            on_data_sync_complete(db, user_id)
    except Exception:
        logger.exception("scheduler_recompute_error", user_id=user_id)


def sync_all_users():
    sync_funcs = _get_sync_funcs()

    with get_db_session_context() as db:
        users = db.query(User).all()
        user_ids = [u.id for u in users]

    logger.info("scheduler_found_users", count=len(user_ids))

    with ThreadPoolExecutor(max_workers=min(4, max(1, len(user_ids)))) as executor:
        futures = {
            executor.submit(_sync_and_recompute, uid, sync_funcs): uid
            for uid in user_ids
            if not shutdown_requested
        }
        for future in as_completed(futures):
            uid = futures[future]
            try:
                future.result()
            except Exception:
                logger.exception("scheduler_user_sync_error", user_id=uid)


def _sync_and_recompute(user_id, sync_funcs):
    _sync_user_sources(user_id, sync_funcs)
    if not shutdown_requested:
        _recompute_analytics_for_user(user_id)


def main():
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    logger.info(
        "scheduler_starting",
        interval_minutes=SYNC_INTERVAL_MINUTES,
        sync_days=SYNC_DAYS,
    )

    logger.info("scheduler_initial_delay", seconds=INITIAL_DELAY_SECONDS)
    interruptible_sleep(INITIAL_DELAY_SECONDS)

    while not shutdown_requested:
        logger.info("scheduler_cycle_started")

        try:
            sync_all_users()
        except Exception:
            logger.exception("scheduler_cycle_error")

        if not shutdown_requested:
            sleep_seconds = SYNC_INTERVAL_MINUTES * 60
            logger.info("scheduler_sleeping", minutes=SYNC_INTERVAL_MINUTES)
            interruptible_sleep(sleep_seconds)

    logger.info("scheduler_stopped")


if __name__ == "__main__":
    main()
