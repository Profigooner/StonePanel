import time
from collections import defaultdict


class SlidingWindowCounter:
    """In-memory sliding window rate limiter."""

    def __init__(self):
        # key -> list of timestamps
        self._windows: dict[str, list[float]] = defaultdict(list)
        # key -> block expiry timestamp
        self._blocked: dict[str, float] = {}

    def is_blocked(self, key: str) -> bool:
        """Check if a key is currently blocked."""
        expiry = self._blocked.get(key)
        if expiry is None:
            return False
        if time.time() > expiry:
            del self._blocked[key]
            return False
        return True

    def block(self, key: str, duration: int) -> None:
        """Block a key for the given duration in seconds."""
        self._blocked[key] = time.time() + duration

    def record(self, key: str, max_requests: int, window: int) -> bool:
        """Record a request. Returns True if within limit, False if limit exceeded."""
        now = time.time()
        cutoff = now - window

        # Clean old entries
        timestamps = self._windows[key]
        self._windows[key] = [t for t in timestamps if t > cutoff]

        # Check limit
        if len(self._windows[key]) >= max_requests:
            return False

        self._windows[key].append(now)
        return True

    def get_count(self, key: str, window: int) -> int:
        """Get the current request count for a key within the window."""
        now = time.time()
        cutoff = now - window
        return sum(1 for t in self._windows.get(key, []) if t > cutoff)

    def cleanup(self, max_age: int = 3600) -> None:
        """Remove stale entries older than max_age seconds."""
        now = time.time()
        cutoff = now - max_age
        empty_keys = []
        for key, timestamps in self._windows.items():
            self._windows[key] = [t for t in timestamps if t > cutoff]
            if not self._windows[key]:
                empty_keys.append(key)
        for key in empty_keys:
            del self._windows[key]

        expired_blocks = [k for k, v in self._blocked.items() if now > v]
        for key in expired_blocks:
            del self._blocked[key]
