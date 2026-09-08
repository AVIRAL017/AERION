"""
AERION — GPU Inference Mutex Unit Tests
Tests serialization, timeout enforcement, cancellation safety, and VRAM concurrency protection.
"""

import asyncio
import unittest

from app.core.errors import InferenceTimeoutError
from app.core.inference_lock import InferenceLock


class TestInferenceLock(unittest.IsolatedAsyncioTestCase):

    async def test_single_task_acquisition(self):
        lock = InferenceLock(default_timeout=5.0)
        self.assertFalse(lock.is_locked)
        self.assertIsNone(lock.active_task_name)
        self.assertEqual(lock.waiters_count, 0)

        async with lock.acquire(task_name="task_single"):
            self.assertTrue(lock.is_locked)
            self.assertEqual(lock.active_task_name, "task_single")
            self.assertEqual(lock.waiters_count, 0)

        self.assertFalse(lock.is_locked)
        self.assertIsNone(lock.active_task_name)

    async def test_serialized_concurrency(self):
        lock = InferenceLock(default_timeout=5.0)
        execution_order = []

        async def worker(name: str, sleep_time: float):
            async with lock.acquire(task_name=name):
                execution_order.append(f"{name}_start")
                await asyncio.sleep(sleep_time)
                execution_order.append(f"{name}_end")

        # Launch two workers concurrently
        task1 = asyncio.create_task(worker("worker1", 0.05))
        # Ensure task1 acquires lock first
        await asyncio.sleep(0.01)
        task2 = asyncio.create_task(worker("worker2", 0.02))

        await asyncio.gather(task1, task2)

        # Execution must be strictly serialized (worker1 finishes before worker2 starts)
        expected = ["worker1_start", "worker1_end", "worker2_start", "worker2_end"]
        self.assertEqual(execution_order, expected)

    async def test_acquisition_timeout_raises_error(self):
        lock = InferenceLock(default_timeout=0.05)

        async def long_holder():
            async with lock.acquire(task_name="holder"):
                await asyncio.sleep(0.2)

        async def impatient_requester():
            await asyncio.sleep(0.01)
            # Timeout should fire before holder finishes
            async with lock.acquire(task_name="requester", timeout=0.04):
                pass

        t1 = asyncio.create_task(long_holder())
        with self.assertRaises(InferenceTimeoutError) as ctx:
            await impatient_requester()

        self.assertIn("GPU is currently occupied", str(ctx.exception))
        await t1

        # Verify lock released cleanly after holder finishes
        self.assertFalse(lock.is_locked)
        self.assertEqual(lock.waiters_count, 0)

    async def test_cancellation_safety(self):
        lock = InferenceLock(default_timeout=5.0)

        async def holder():
            async with lock.acquire(task_name="holder"):
                await asyncio.sleep(0.2)

        async def waiting_worker():
            async with lock.acquire(task_name="waiter"):
                await asyncio.sleep(0.1)

        t_holder = asyncio.create_task(holder())
        await asyncio.sleep(0.01)

        t_waiter = asyncio.create_task(waiting_worker())
        await asyncio.sleep(0.01)
        self.assertEqual(lock.waiters_count, 1)

        # Cancel the waiting worker before it ever gets the lock
        t_waiter.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await t_waiter

        # Waiter count must decrease back to 0
        self.assertEqual(lock.waiters_count, 0)
        await t_holder
        self.assertFalse(lock.is_locked)


if __name__ == "__main__":
    unittest.main()
