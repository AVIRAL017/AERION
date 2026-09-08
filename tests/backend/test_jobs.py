"""
AERION — Background Job Abstraction Unit Tests
Tests task submission, status transitions, result capturing, and cancellation.
"""

import asyncio
import unittest

from app.core.jobs import JobManager, JobStatus


class TestJobManager(unittest.IsolatedAsyncioTestCase):

    async def test_job_successful_execution(self):
        manager = JobManager()

        async def successful_task():
            await asyncio.sleep(0.02)
            return {"frames_analyzed": 100, "status": "ok"}

        record = await manager.submit_job("test_video_task", successful_task)
        self.assertEqual(record.status, JobStatus.QUEUED)
        job_id = record.job_id

        # Allow task to complete
        await asyncio.sleep(0.05)

        retrieved = await manager.get_job(job_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.status, JobStatus.COMPLETED)
        self.assertEqual(retrieved.result, {"frames_analyzed": 100, "status": "ok"})
        self.assertIsNone(retrieved.error)
        self.assertIsNotNone(retrieved.started_at)
        self.assertIsNotNone(retrieved.completed_at)

    async def test_job_failure_execution(self):
        manager = JobManager()

        async def failing_task():
            await asyncio.sleep(0.01)
            raise ValueError("Corrupted video payload.")

        record = await manager.submit_job("failing_task", failing_task)
        job_id = record.job_id

        await asyncio.sleep(0.04)

        retrieved = await manager.get_job(job_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.status, JobStatus.FAILED)
        self.assertIn("Corrupted video payload", retrieved.error)
        self.assertIsNone(retrieved.result)

    async def test_job_cancellation(self):
        manager = JobManager()

        async def long_running_task():
            await asyncio.sleep(1.0)
            return "done"

        record = await manager.submit_job("long_task", long_running_task)
        job_id = record.job_id

        # Wait until it starts running
        await asyncio.sleep(0.01)
        cancelled = await manager.cancel_job(job_id)
        self.assertTrue(cancelled)

        await asyncio.sleep(0.02)
        retrieved = await manager.get_job(job_id)
        self.assertEqual(retrieved.status, JobStatus.CANCELLED)

    async def test_non_existent_job_returns_none(self):
        manager = JobManager()
        result = await manager.get_job("non-existent-uuid-12345")
        self.assertIsNone(result)

    async def test_bounded_history_capacity(self):
        manager = JobManager(max_history=3)

        async def dummy():
            return 1

        ids = []
        for i in range(5):
            rec = await manager.submit_job(f"task_{i}", dummy)
            ids.append(rec.job_id)

        await asyncio.sleep(0.02)
        self.assertLessEqual(len(manager._jobs), 3)
        # Oldest job id[0] must have been evicted
        self.assertIsNone(await manager.get_job(ids[0]))


if __name__ == "__main__":
    unittest.main()
