from __future__ import annotations

import time
from collections import defaultdict


class RateLimiter:
    def __init__(self) -> None:
        self._limits: dict[str, tuple[int, int]] = {}
        self._requests: dict[tuple[int, str], list[float]] = defaultdict(list)

    def configure(
        self,
        action: str,
        max_requests: int,
        window_seconds: int = 60,
    ) -> None:
        self._limits[action] = (max_requests, window_seconds)

    def check(self, user_id: int, action: str) -> bool:
        if action not in self._limits:
            return True

        max_requests, window_seconds = self._limits[action]
        now = time.monotonic()
        key = (user_id, action)
        timestamps = self._requests[key]

        cutoff = now - window_seconds
        self._requests[key] = [t for t in timestamps if t > cutoff]
        timestamps = self._requests[key]

        if len(timestamps) >= max_requests:
            return False

        timestamps.append(now)
        return True

    def get_remaining(self, user_id: int, action: str) -> int:
        if action not in self._limits:
            return 999

        max_requests, window_seconds = self._limits[action]
        now = time.monotonic()
        key = (user_id, action)
        timestamps = self._requests[key]

        cutoff = now - window_seconds
        self._requests[key] = [t for t in timestamps if t > cutoff]
        timestamps = self._requests[key]

        return max(0, max_requests - len(timestamps))
