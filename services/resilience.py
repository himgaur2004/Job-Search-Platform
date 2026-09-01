from __future__ import annotations

import time


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, reset_timeout_seconds: int = 600):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout_seconds = reset_timeout_seconds
        self._failures = 0
        self._opened_at: float | None = None

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        elapsed = time.time() - self._opened_at
        if elapsed >= self.reset_timeout_seconds:
            self._opened_at = None
            self._failures = 0
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = time.time()

    @property
    def is_open(self) -> bool:
        return not self.allow()
