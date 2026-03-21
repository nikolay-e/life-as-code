import threading

_sync_locks: dict[tuple[int, str], threading.Lock] = {}
_locks_lock = threading.Lock()


def _get_sync_lock(user_id: int, source: str) -> threading.Lock:
    key = (user_id, source)
    with _locks_lock:
        if key not in _sync_locks:
            _sync_locks[key] = threading.Lock()
        return _sync_locks[key]


def is_sync_locked(user_id: int, source: str) -> bool:
    lock = _get_sync_lock(user_id, source)
    acquired = lock.acquire(blocking=False)
    if acquired:
        lock.release()
        return False
    return True


def acquire_sync_lock(user_id: int, source: str) -> bool:
    lock = _get_sync_lock(user_id, source)
    return lock.acquire(blocking=False)


def release_sync_lock(user_id: int, source: str) -> None:
    lock = _get_sync_lock(user_id, source)
    try:
        lock.release()
    except RuntimeError:
        pass
