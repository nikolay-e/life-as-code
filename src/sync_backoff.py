import threading
import time
from dataclasses import dataclass

from logging_config import get_logger

logger = get_logger(__name__)

BACKOFF_SCHEDULE_MINUTES = [5, 15, 60, 240, 480]
RATE_LIMIT_ESCALATION = 2


@dataclass
class SourceBackoffState:
    failure_count: int = 0
    backoff_level: int = 0
    last_failure_time: float = 0.0
    is_rate_limited: bool = False

    @property
    def backoff_minutes(self) -> int:
        idx = min(self.backoff_level, len(BACKOFF_SCHEDULE_MINUTES) - 1)
        return BACKOFF_SCHEDULE_MINUTES[idx]

    @property
    def next_allowed_time(self) -> float:
        return self.last_failure_time + self.backoff_minutes * 60


class SyncBackoffManager:
    def __init__(self):
        self._states: dict[str, SourceBackoffState] = {}
        self._lock = threading.Lock()

    def _key(self, user_id: int, source: str) -> str:
        return f"{user_id}:{source}"

    def _get_state(self, user_id: int, source: str) -> SourceBackoffState:
        key = self._key(user_id, source)
        if key not in self._states:
            self._states[key] = SourceBackoffState()
        return self._states[key]

    def should_skip(self, user_id: int, source: str) -> bool:
        with self._lock:
            state = self._get_state(user_id, source)
            if state.failure_count == 0:
                return False

            now = time.monotonic()
            if now < state.next_allowed_time:
                remaining = int((state.next_allowed_time - now) / 60)
                logger.info(
                    "sync_backoff_skip",
                    user_id=user_id,
                    source=source,
                    backoff_minutes=state.backoff_minutes,
                    remaining_minutes=remaining,
                    failure_count=state.failure_count,
                    is_rate_limited=state.is_rate_limited,
                )
                return True
            return False

    def record_success(self, user_id: int, source: str) -> None:
        with self._lock:
            key = self._key(user_id, source)
            prev = self._states.get(key)
            if prev and prev.failure_count > 0:
                logger.info(
                    "sync_backoff_cleared",
                    user_id=user_id,
                    source=source,
                    previous_failures=prev.failure_count,
                )
            self._states[key] = SourceBackoffState()

    def record_failure(
        self, user_id: int, source: str, is_rate_limit: bool = False
    ) -> None:
        with self._lock:
            state = self._get_state(user_id, source)
            state.failure_count += 1
            state.last_failure_time = time.monotonic()
            state.is_rate_limited = is_rate_limit

            escalation = RATE_LIMIT_ESCALATION if is_rate_limit else 1
            state.backoff_level = min(
                state.backoff_level + escalation, len(BACKOFF_SCHEDULE_MINUTES) - 1
            )

            logger.warning(
                "sync_backoff_recorded",
                user_id=user_id,
                source=source,
                failure_count=state.failure_count,
                backoff_level=state.backoff_level,
                backoff_minutes=state.backoff_minutes,
                is_rate_limit=is_rate_limit,
            )
