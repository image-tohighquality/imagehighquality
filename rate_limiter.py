from collections import defaultdict
from datetime import datetime, timedelta
from threading import Lock
from config import MAX_IMAGES_PER_HOUR


class RateLimiter:
    """
    Thread-safe per-user rate limiter using a sliding 1-hour window.

    Safe for long-running processes: expired entries are purged on every
    check, and a periodic full cleanup prevents unbounded memory growth
    when the bot is used by many unique users over time.
    """

    def __init__(self, max_per_hour: int = MAX_IMAGES_PER_HOUR):
        self.max_per_hour = max_per_hour
        self._requests: dict[int, list[datetime]] = defaultdict(list)
        self._lock = Lock()
        self._last_full_cleanup = datetime.now()

    def is_allowed(self, user_id: int) -> bool:
        """
        Returns True if the user may make a request and records it.
        Returns False if the hourly limit is reached.
        """
        now = datetime.now()
        cutoff = now - timedelta(hours=1)

        with self._lock:
            # Purge expired timestamps for this user
            self._requests[user_id] = [
                t for t in self._requests[user_id] if t > cutoff
            ]

            if len(self._requests[user_id]) >= self.max_per_hour:
                return False

            self._requests[user_id].append(now)

            # Full cleanup every 6 hours to prevent unbounded dict growth
            if (now - self._last_full_cleanup) > timedelta(hours=6):
                self._full_cleanup(cutoff)
                self._last_full_cleanup = now

            return True

    def _full_cleanup(self, cutoff: datetime) -> None:
        """Remove entries for users with no recent activity. Call with lock held."""
        inactive = [
            uid for uid, ts in self._requests.items()
            if not ts or max(ts) < cutoff
        ]
        for uid in inactive:
            del self._requests[uid]

    def seconds_until_reset(self, user_id: int) -> int:
        """Returns seconds until the oldest request in the window expires."""
        with self._lock:
            if not self._requests.get(user_id):
                return 0
            oldest = min(self._requests[user_id])
            remaining = (oldest + timedelta(hours=1) - datetime.now()).total_seconds()
            return max(0, int(remaining))


limiter = RateLimiter()
