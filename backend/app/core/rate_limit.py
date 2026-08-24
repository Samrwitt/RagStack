"""Simple fixed-window rate limiter."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class FixedWindowRateLimiter:
    limit: int
    window_seconds: int
    _windows: dict[str, tuple[int, float]] = field(default_factory=dict)

    def allow(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        count, started = self._windows.get(key, (0, now))
        if now - started >= self.window_seconds:
            count, started = 0, now
        count += 1
        self._windows[key] = (count, started)
        remaining = max(0, self.limit - count)
        return count <= self.limit, remaining
