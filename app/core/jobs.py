"""
AERION — Background Job Abstraction
Provides an asynchronous in-process job scheduling and lifecycle tracking abstraction.
Designed for single-process development and seamless future replacement by Celery/Redis in Phase 3E.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

from app.core.logging import get_logger
from app.schemas.common import utc_now_iso

logger = get_logger("jobs")


class JobStatus(str, Enum):
    """Lifecycle states for background asynchronous tasks."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobRecord:
    """Represents the execution state and result of an asynchronous background job."""
    job_id: str
    task_name: str
    status: JobStatus = JobStatus.QUEUED
    created_at: str = field(default_factory=utc_now_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert job record to a JSON-serializable dictionary."""
        return {
            "job_id": self.job_id,
            "task_name": self.task_name,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
        }


class JobManager:
    """
    In-memory background job manager for single-process environments.

    NOTE: Job state is stored in process memory. It does not survive application
    restarts and is not shared across multi-process workers. Distributed persistent
    jobs will be introduced via PostgreSQL/Celery in Phase 3E.
    """

    def __init__(self, max_history: int = 1000) -> None:
        self._max_history = max_history
        self._jobs: Dict[str, JobRecord] = {}
        self._tasks: Dict[str, asyncio.Task[Any]] = {}
        self._lock = asyncio.Lock()

    async def submit_job(
        self,
        task_name: str,
        coro_fn: Callable[[], Coroutine[Any, Any, Any]],
    ) -> JobRecord:
        """
        Register and schedule a coroutine for asynchronous execution.
        """
        job_id = str(uuid.uuid4())
        record = JobRecord(job_id=job_id, task_name=task_name, status=JobStatus.QUEUED)

        async with self._lock:
            # Bound job memory history
            if len(self._jobs) >= self._max_history:
                oldest_key = next(iter(self._jobs))
                self._jobs.pop(oldest_key, None)
                self._tasks.pop(oldest_key, None)

            self._jobs[job_id] = record

        # Launch background execution task
        task = asyncio.create_task(self._run_job(job_id, coro_fn))
        self._tasks[job_id] = task
        logger.info(f"Background job '{task_name}' submitted (ID: {job_id})", extra={"event": "job_submitted", "job_id": job_id})
        return record

    async def _run_job(
        self,
        job_id: str,
        coro_fn: Callable[[], Coroutine[Any, Any, Any]],
    ) -> None:
        """Internal execution wrapper updating status transitions."""
        record = self._jobs.get(job_id)
        if not record:
            return

        record.status = JobStatus.RUNNING
        record.started_at = utc_now_iso()
        logger.info(f"Background job {job_id} started", extra={"event": "job_started", "job_id": job_id})

        try:
            result = await coro_fn()
            record.status = JobStatus.COMPLETED
            record.completed_at = utc_now_iso()
            record.result = result
            logger.info(f"Background job {job_id} completed successfully", extra={"event": "job_completed", "job_id": job_id})
        except asyncio.CancelledError:
            record.status = JobStatus.CANCELLED
            record.completed_at = utc_now_iso()
            record.error = "Job was cancelled."
            logger.warning(f"Background job {job_id} was cancelled", extra={"event": "job_cancelled", "job_id": job_id})
            raise
        except Exception as exc:
            record.status = JobStatus.FAILED
            record.completed_at = utc_now_iso()
            record.error = str(exc)
            logger.exception(f"Background job {job_id} failed: {exc}", extra={"event": "job_failed", "job_id": job_id})
        finally:
            self._tasks.pop(job_id, None)

    async def get_job(self, job_id: str) -> Optional[JobRecord]:
        """Retrieve the current state of a registered job."""
        async with self._lock:
            return self._jobs.get(job_id)

    async def cancel_job(self, job_id: str) -> bool:
        """Attempt to cancel an active running task."""
        async with self._lock:
            task = self._tasks.get(job_id)
            if task and not task.done():
                task.cancel()
                return True
            return False

    async def list_jobs(self, limit: int = 50, status: Optional[JobStatus] = None) -> List[JobRecord]:
        """List recently executed or pending jobs."""
        async with self._lock:
            records = list(self._jobs.values())
            if status:
                records = [r for r in records if r.status == status]
            return records[-limit:]


# Global default job manager instance for Phase 3A
default_job_manager = JobManager()
