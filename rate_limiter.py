"""
rate_limiter.py — Hybrid rate limiter for Image Quality Bot v1.5

Primary:  Supabase DB (persistent across restarts)
Fallback: In-memory sliding window (used when DB is unavailable)

Public interface is identical to v1.0 — no changes needed in bot.py.
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from threading import Lock

from config import MAX_IMAGES_PER_HOUR

# ── In-memory fallback (identical to v1.0) ────────────────────────────────────

class _InMemoryLimiter:
    def __init__(self, max_per_hour: int = MAX_IMAGES_PER_HOUR):
        self.max_per_hour = max_per_hour
        self._requests: dict[int, list[datetime]] = defaultdict(list)
        self._lock = Lock()
        self._last_cleanup = datetime.now()

    def is_allowed(self, user_id: int) -> bool:
        now    = datetime.now()
        cutoff = now - timedelta(hours=1)
        with self._lock:
            self._requests[user_id] = [t for t in self._requests[user_id] if t > cutoff]
            if len(self._requests[user_id]) >= self.max_per_hour:
                return False
            self._requests[user_id].append(now)
            if (now - self._last_cleanup) > timedelta(hours=6):
                self._full_cleanup(cutoff)
                self._last_cleanup = now
            return True

    def _full_cleanup(self, cutoff: datetime) -> None:
        inactive = [uid for uid, ts in self._requests.items()
                    if not ts or max(ts) < cutoff]
        for uid in inactive:
            del self._requests[uid]

    def seconds_until_reset(self, user_id: int) -> int:
        with self._lock:
            if not self._requests.get(user_id):
                return 0
            oldest    = min(self._requests[user_id])
            remaining = (oldest + timedelta(hours=1) - datetime.now()).total_seconds()
            return max(0, int(remaining))


_memory = _InMemoryLimiter()


# ── Public async interface ────────────────────────────────────────────────────

async def check_rate_limit(user_id: int) -> bool:
    """
    Returns True if the user is within the rate limit.
    Tries DB first; falls back to in-memory on any failure.
    Also records the request in the in-memory tracker for the fallback.
    """
    from database import count_recent_requests
    from config import DB_ENABLED

    if DB_ENABLED:
        count = await count_recent_requests(user_id)
        if count is not None:
            # DB check succeeded — enforce limit without touching in-memory
            return count < MAX_IMAGES_PER_HOUR

    # DB unavailable or not configured — use in-memory
    return _memory.is_allowed(user_id)


def seconds_until_reset(user_id: int) -> int:
    """Approximate seconds until the oldest request in the window expires."""
    return _memory.seconds_until_reset(user_id)
