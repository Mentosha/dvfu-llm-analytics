from __future__ import annotations

import time
from collections import defaultdict, deque

_history: dict[int, deque[float]] = defaultdict(deque)


def allow(user_id: int, limit: int, window_sec: int = 3600) -> tuple[bool, int]:
    """Возвращает (разрешено?, секунд_до_сброса). Если разрешено — фиксирует запрос."""
    now = time.time()
    hist = _history[user_id]
    while hist and now - hist[0] > window_sec:
        hist.popleft()
    if len(hist) >= limit:
        retry_after = int(window_sec - (now - hist[0])) + 1
        return False, retry_after
    hist.append(now)
    return True, 0


_pending: dict[int, dict] = {}


def set_pending(user_id: int, **fields) -> None:
    _pending.setdefault(user_id, {}).update(fields)


def pop_pending(user_id: int) -> dict:
    return _pending.pop(user_id, {})
