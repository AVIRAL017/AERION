"""
AERION — In-Memory TTL Cache
Thread-safe and async-compatible in-memory caching with bounded size and TTL eviction.
Designed for external API query caching (weather, routing, geocoding) without requiring Redis.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional, Tuple


class InMemoryTTLCache:
    """
    Lightweight, thread-safe, bounded in-memory cache with time-to-live (TTL) expiration.
    Automatically evicts expired entries and enforces max_size via oldest-entry eviction.
    """

    def __init__(self, max_size: int = 500, default_ttl_seconds: float = 600.0):
        self.max_size = max_size
        self.default_ttl = default_ttl_seconds
        self._cache: Dict[str, Tuple[Any, float]] = {}  # key -> (value, expiry_timestamp)
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve value by key if present and unexpired; otherwise return None."""
        async with self._lock:
            if key not in self._cache:
                return None
            val, expiry = self._cache[key]
            if time.time() > expiry:
                del self._cache[key]
                return None
            return val

    async def set(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        """Store value with TTL. Evicts oldest entries if capacity is exceeded."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expiry = time.time() + ttl

        async with self._lock:
            # Purge expired entries if over 80% capacity
            if len(self._cache) >= int(self.max_size * 0.8):
                now = time.time()
                expired_keys = [k for k, (_, exp) in self._cache.items() if now > exp]
                for k in expired_keys:
                    del self._cache[k]

            # If still at max size, evict oldest entry
            if len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]

            self._cache[key] = (value, expiry)

    async def delete(self, key: str) -> bool:
        """Remove a single entry from the cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> None:
        """Clear all cached entries."""
        async with self._lock:
            self._cache.clear()

    async def size(self) -> int:
        """Return count of active, unexpired entries."""
        async with self._lock:
            now = time.time()
            return sum(1 for _, exp in self._cache.values() if exp > now)


# Global singleton instances for external provider caching
weather_cache = InMemoryTTLCache(max_size=300, default_ttl_seconds=600.0)    # 10 minutes
routing_cache = InMemoryTTLCache(max_size=300, default_ttl_seconds=900.0)    # 15 minutes
geocoding_cache = InMemoryTTLCache(max_size=500, default_ttl_seconds=3600.0) # 1 hour
