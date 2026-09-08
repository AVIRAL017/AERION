"""
AERION — Rate Limiter Abstraction
Provides an abstract base interface for rate limiting with an in-memory sliding-window
implementation for local process protection, designed for transparent future Redis replacement.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from fastapi import Request, Response

from app.core.errors import RateLimitExceededError
from app.core.logging import get_logger

logger = get_logger("rate_limit")


class RateLimiter(ABC):
    """
    Abstract interface for rate limiting engines.
    Allows swappable implementations (InMemory for single-process dev, Redis for distributed prod).
    """

    @abstractmethod
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> Tuple[bool, int, float]:
        """
        Evaluate if a request under 'key' is permitted within the rate limit.

        Parameters
        ----------
        key:
            Unique identifier for the rate-limited entity (e.g. client IP, user ID).
        limit:
            Maximum allowed requests within the window.
        window_seconds:
            Duration of the sliding window in seconds.

        Returns
        -------
        Tuple[bool, int, float]:
            - is_allowed: True if request is under limit, False otherwise.
            - remaining: Number of remaining requests allowed in the active window.
            - reset_time: Epoch timestamp (seconds) when window quota will reset.
        """
        pass


class InMemoryRateLimiter(RateLimiter):
    """
    In-memory sliding-window log rate limiter for single-process environments.

    NOTE: This implementation operates strictly process-locally. It does NOT
    provide distributed synchronization across multiple Uvicorn workers or containers.
    Phase 3E/Phase 4 will introduce a Redis-backed implementation satisfying the same RateLimiter ABC.
    """

    def __init__(self, max_keys: int = 10000, cleanup_interval_seconds: float = 300.0) -> None:
        self._max_keys = max_keys
        self._cleanup_interval = cleanup_interval_seconds
        self._last_cleanup = time.time()
        self._storage: Dict[str, Tuple[List[float], int]] = {}
        self._lock = asyncio.Lock()

    async def _prune_expired_keys(self, now: float) -> None:
        """Evict expired request timestamps and prune idle keys based on each key's window."""
        keys_to_remove = []

        for key, (timestamps, win_sec) in self._storage.items():
            threshold = now - win_sec
            valid_timestamps = [t for t in timestamps if t > threshold]
            if valid_timestamps:
                self._storage[key] = (valid_timestamps, win_sec)
            else:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            self._storage.pop(key, None)

        self._last_cleanup = now

    async def is_allowed(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> Tuple[bool, int, float]:
        now = time.time()
        threshold = now - window_seconds

        async with self._lock:
            # Trigger periodic or emergency cleanup if storage exceeds capacity
            if (now - self._last_cleanup > self._cleanup_interval) or (len(self._storage) >= self._max_keys):
                await self._prune_expired_keys(now)

            entry = self._storage.get(key)
            timestamps = entry[0] if entry else []
            valid_timestamps = [t for t in timestamps if t > threshold]

            if len(valid_timestamps) >= limit:
                # Quota exceeded; reset occurs after the oldest timestamp in window expires
                oldest_timestamp = valid_timestamps[0]
                reset_time = oldest_timestamp + window_seconds
                self._storage[key] = (valid_timestamps, window_seconds)
                return False, 0, reset_time

            # Record current request timestamp
            valid_timestamps.append(now)
            self._storage[key] = (valid_timestamps, window_seconds)
            remaining = max(0, limit - len(valid_timestamps))
            reset_time = now + window_seconds
            return True, remaining, reset_time

    async def reset(self) -> None:
        """Clear all stored rate limit history (primarily for test teardown)."""
        async with self._lock:
            self._storage.clear()
            self._last_cleanup = time.time()


# Global default in-memory rate limiter instance for Phase 3A
default_rate_limiter = InMemoryRateLimiter()


class RateLimitDependency:
    """
    FastAPI route dependency that enforces rate limiting on sensitive or heavy endpoints.
    """

    def __init__(
        self,
        limit: int = 60,
        window_seconds: int = 60,
        limiter: Optional[RateLimiter] = None,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.limiter = limiter or default_rate_limiter

    async def __call__(self, request: Request, response: Response) -> None:
        # Determine client identifier (IP address or fallback to unknown)
        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{request.url.path}:{client_ip}"

        allowed, remaining, reset_time = await self.limiter.is_allowed(
            key=key,
            limit=self.limit,
            window_seconds=self.window_seconds,
        )

        response.headers["X-RateLimit-Limit"] = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(reset_time))

        if not allowed:
            retry_after = max(1, int(reset_time - time.time()))
            response.headers["Retry-After"] = str(retry_after)
            logger.warning(
                f"Rate limit exceeded for key '{key}' on {request.method} {request.url.path}",
                extra={"event": "rate_limit_exceeded", "path": request.url.path, "key": key},
            )
            raise RateLimitExceededError(
                message=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                details=[{"field": "rate_limit", "issue": "too_many_requests", "provided": key}],
                headers={"Retry-After": str(retry_after)},
            )
