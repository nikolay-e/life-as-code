import datetime
import threading

from logging_config import get_logger

logger = get_logger(__name__)

BACKOFF_SCHEDULE_MINUTES = [5, 15, 60, 240, 480, 1440, 2880]
RATE_LIMIT_ESCALATION = 2


class SyncBackoffManager:
    def __init__(self):
        self._lock = threading.Lock()

    def _get_state(self, db, user_id: int, source: str):
        from models import SyncBackoff

        return (
            db.query(SyncBackoff)
            .filter(SyncBackoff.user_id == user_id, SyncBackoff.source == source)
            .first()
        )

    def _backoff_minutes(self, backoff_level: int) -> int:
        idx = min(backoff_level, len(BACKOFF_SCHEDULE_MINUTES) - 1)
        return BACKOFF_SCHEDULE_MINUTES[idx]

    def should_skip(self, user_id: int, source: str) -> bool:
        with self._lock:
            try:
                from database import get_db_session_context
                from date_utils import utcnow

                with get_db_session_context() as db:
                    state = self._get_state(db, user_id, source)
                    if not state or state.failure_count == 0:
                        return False

                    now = utcnow()
                    backoff_min = self._backoff_minutes(state.backoff_level)
                    next_allowed = state.last_failure_at + datetime.timedelta(
                        minutes=backoff_min
                    )

                    if now < next_allowed:
                        remaining = int((next_allowed - now).total_seconds() / 60)
                        logger.info(
                            "sync_backoff_skip",
                            user_id=user_id,
                            source=source,
                            backoff_minutes=backoff_min,
                            remaining_minutes=remaining,
                            failure_count=state.failure_count,
                            is_rate_limited=state.is_rate_limited,
                        )
                        return True
                    return False
            except Exception:
                logger.exception(
                    "sync_backoff_check_error", user_id=user_id, source=source
                )
                return False

    def record_success(self, user_id: int, source: str) -> None:
        with self._lock:
            try:
                from database import get_db_session_context

                with get_db_session_context() as db:
                    state = self._get_state(db, user_id, source)
                    if state and state.failure_count > 0:
                        logger.info(
                            "sync_backoff_cleared",
                            user_id=user_id,
                            source=source,
                            previous_failures=state.failure_count,
                        )
                        db.delete(state)
            except Exception:
                logger.exception(
                    "sync_backoff_clear_error", user_id=user_id, source=source
                )

    def record_failure(
        self, user_id: int, source: str, is_rate_limit: bool = False
    ) -> None:
        with self._lock:
            try:
                from database import get_db_session_context
                from date_utils import utcnow
                from models import SyncBackoff

                with get_db_session_context() as db:
                    state = self._get_state(db, user_id, source)

                    if not state:
                        state = SyncBackoff(
                            user_id=user_id,
                            source=source,
                            failure_count=0,
                            backoff_level=0,
                        )
                        db.add(state)

                    state.failure_count += 1
                    state.last_failure_at = utcnow()
                    state.is_rate_limited = is_rate_limit

                    escalation = RATE_LIMIT_ESCALATION if is_rate_limit else 1
                    state.backoff_level = min(
                        state.backoff_level + escalation,
                        len(BACKOFF_SCHEDULE_MINUTES) - 1,
                    )

                    logger.warning(
                        "sync_backoff_recorded",
                        user_id=user_id,
                        source=source,
                        failure_count=state.failure_count,
                        backoff_level=state.backoff_level,
                        backoff_minutes=self._backoff_minutes(state.backoff_level),
                        is_rate_limit=is_rate_limit,
                    )
            except Exception:
                logger.exception(
                    "sync_backoff_record_error", user_id=user_id, source=source
                )
