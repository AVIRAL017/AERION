"""
AERION — Rate Limiter Unit Tests
Tests in-memory sliding window rate limiting, capacity boundaries, expiry resets, and route dependencies.
"""

import asyncio
import time
import unittest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.config import AERIONSettings
from app.core.rate_limit import InMemoryRateLimiter, RateLimitDependency
from app.main import create_app


class TestRateLimiter(unittest.IsolatedAsyncioTestCase):

    async def test_sliding_window_allows_within_limit(self):
        limiter = InMemoryRateLimiter()
        key = "client-1"
        limit = 5
        window = 10

        for i in range(limit):
            allowed, remaining, _ = await limiter.is_allowed(key, limit, window)
            self.assertTrue(allowed)
            self.assertEqual(remaining, limit - (i + 1))

    async def test_sliding_window_blocks_over_limit(self):
        limiter = InMemoryRateLimiter()
        key = "client-2"
        limit = 3
        window = 10

        for _ in range(limit):
            allowed, _, _ = await limiter.is_allowed(key, limit, window)
            self.assertTrue(allowed)

        # 4th request must be rejected
        allowed, remaining, reset_time = await limiter.is_allowed(key, limit, window)
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)
        self.assertGreater(reset_time, time.time())

    async def test_sliding_window_resets_after_expiry(self):
        limiter = InMemoryRateLimiter()
        key = "client-3"
        limit = 2
        # Short window for testing
        window = 1

        allowed, _, _ = await limiter.is_allowed(key, limit, window)
        self.assertTrue(allowed)
        allowed, _, _ = await limiter.is_allowed(key, limit, window)
        self.assertTrue(allowed)
        allowed, _, _ = await limiter.is_allowed(key, limit, window)
        self.assertFalse(allowed)

        # Wait for window to expire
        await asyncio.sleep(1.05)

        # Next request should be allowed again
        allowed, remaining, _ = await limiter.is_allowed(key, limit, window)
        self.assertTrue(allowed)
        self.assertEqual(remaining, 1)

    async def test_bounded_memory_pruning(self):
        # Limiter with very small max_keys to force pruning
        limiter = InMemoryRateLimiter(max_keys=3, cleanup_interval_seconds=0.01)
        
        # Insert 3 keys with tiny window
        await limiter.is_allowed("k1", 1, 1)
        await limiter.is_allowed("k2", 1, 1)
        await limiter.is_allowed("k3", 1, 1)
        self.assertEqual(len(limiter._storage), 3)

        # Wait for expiration
        await asyncio.sleep(1.05)

        # Insert 4th key; should trigger pruning of expired k1, k2, k3
        await limiter.is_allowed("k4", 1, 10)
        self.assertLessEqual(len(limiter._storage), 2)
        self.assertIn("k4", limiter._storage)


class TestRateLimitDependencyIntegration(unittest.TestCase):

    def setUp(self):
        self.settings = AERIONSettings(ENVIRONMENT="test")
        self.app = create_app(settings=self.settings)

        test_limiter = InMemoryRateLimiter()
        router = APIRouter()

        @router.get(
            "/limited-endpoint",
            dependencies=[Depends(RateLimitDependency(limit=2, window_seconds=10, limiter=test_limiter))],
        )
        async def limited_endpoint():
            return {"status": "success"}

        self.app.include_router(router)
        self.client = TestClient(self.app)

    def test_endpoint_rate_limit_headers_and_rejection(self):
        # Request 1: allowed
        r1 = self.client.get("/limited-endpoint")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.headers.get("X-RateLimit-Limit"), "2")
        self.assertEqual(r1.headers.get("X-RateLimit-Remaining"), "1")

        # Request 2: allowed
        r2 = self.client.get("/limited-endpoint")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.headers.get("X-RateLimit-Remaining"), "0")

        # Request 3: rejected 429
        r3 = self.client.get("/limited-endpoint")
        self.assertEqual(r3.status_code, 429)
        self.assertIn("Retry-After", r3.headers)
        payload = r3.json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"]["code"], "RATE_LIMIT_EXCEEDED")


if __name__ == "__main__":
    unittest.main()
