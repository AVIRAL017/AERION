"""
AERION — Background Job Abstraction
Provides an asynchronous in-process job scheduling and lifecycle tracking abstraction.
Designed for single-process development and seamless future replacement by Celery/Redis in Phase 3E.
Strictly implements the Step 27 required lifecycle states, stage tracking, progress, and idempotency.
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
    """Lifecycle states for background asynchronous tasks and analysis pipelines."""
    # Standard lifecycle states
    SUBMITTED = "SUBMITTED"
    VALIDATING = "VALIDATING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    ENRICHING = "ENRICHING"
    GENERATING_ADVISORY = "GENERATING_ADVISORY"
    GENERATING_ARTIFACTS = "GENERATING_ARTIFACTS"
    PERSISTING = "PERSISTING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_LIMITATIONS = "COMPLETED_WITH_LIMITATIONS"

    # Explicit failure states
    VALIDATION_FAILED = "VALIDATION_FAILED"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    EXTERNAL_DATA_PARTIAL = "EXTERNAL_DATA_PARTIAL"
    ADVISORY_UNAVAILABLE = "ADVISORY_UNAVAILABLE"
    ARTIFACT_FAILED = "ARTIFACT_FAILED"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

    # Backward compatibility aliases (lowercased)
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


@dataclass
class JobRecord:
    """Represents the execution state and result of an asynchronous background job."""
    job_id: str
    task_name: str
    status: JobStatus = JobStatus.QUEUED
    current_stage: str = "QUEUED"
    progress_percent: int = 0
    mode: Optional[str] = None
    project_id: Optional[str] = None
    user_id: Optional[str] = None
    input_asset_reference: Optional[str] = None
    idempotency_key: Optional[str] = None
    analysis_id: Optional[str] = None
    limitations: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert job record to a JSON-serializable dictionary adhering to the Job Contract."""
        return {
            "job_id": self.job_id,
            "analysis_id": self.analysis_id,
            "task_name": self.task_name,
            "mode": self.mode,
            "status": self.status.value,
            "current_stage": self.current_stage,
            "progress_percent": self.progress_percent,
            "project_id": self.project_id,
            "user_id": self.user_id,
            "input_asset_reference": self.input_asset_reference,
            "idempotency_key": self.idempotency_key,
            "limitations": self.limitations,
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
        self._idempotency_map: Dict[str, str] = {}  # key -> job_id
        self._lock = asyncio.Lock()

    async def submit_job(
        self,
        task_name: str,
        coro_fn: Callable[..., Coroutine[Any, Any, Any]],
        mode: Optional[str] = None,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        input_asset_reference: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        initial_status: JobStatus = JobStatus.QUEUED,
        pass_job_context: bool = False,
    ) -> JobRecord:
        """
        Register and schedule a coroutine for asynchronous execution.
        If idempotency_key is provided and a job with that key is already running or completed,
        returns the existing job record without re-scheduling.
        """
        async with self._lock:
            # Check idempotency
            if idempotency_key:
                composite_key = f"{project_id or 'default'}:{idempotency_key}"
                existing_job_id = self._idempotency_map.get(composite_key)
                if existing_job_id and existing_job_id in self._jobs:
                    existing_record = self._jobs[existing_job_id]
                    # If not failed/cancelled, return existing to avoid duplicate processing
                    if existing_record.status not in (
                        JobStatus.FAILED,
                        JobStatus.CANCELLED,
                        JobStatus.failed,
                        JobStatus.cancelled,
                        JobStatus.VALIDATION_FAILED,
                        JobStatus.PROCESSING_FAILED,
                    ):
                        logger.info(
                            f"Idempotent job hit for key '{composite_key}': returning existing job {existing_job_id}",
                            extra={"event": "job_idempotent_hit", "job_id": existing_job_id},
                        )
                        return existing_record

            job_id = str(uuid.uuid4())
            record = JobRecord(
                job_id=job_id,
                task_name=task_name,
                status=initial_status,
                current_stage=initial_status.value,
                mode=mode,
                project_id=project_id,
                user_id=user_id,
                input_asset_reference=input_asset_reference,
                idempotency_key=idempotency_key,
            )

            # Bound job memory history
            if len(self._jobs) >= self._max_history:
                oldest_key = next(iter(self._jobs))
                old_rec = self._jobs.pop(oldest_key, None)
                self._tasks.pop(oldest_key, None)
                if old_rec and old_rec.idempotency_key:
                    old_composite = f"{old_rec.project_id or 'default'}:{old_rec.idempotency_key}"
                    self._idempotency_map.pop(old_composite, None)

            self._jobs[job_id] = record
            if idempotency_key:
                composite_key = f"{project_id or 'default'}:{idempotency_key}"
                self._idempotency_map[composite_key] = job_id

        # Launch background execution task
        task = asyncio.create_task(self._run_job(job_id, coro_fn, pass_job_context))
        self._tasks[job_id] = task
        logger.info(
            f"Background job '{task_name}' submitted (ID: {job_id})",
            extra={"event": "job_submitted", "job_id": job_id},
        )
        return record

    async def update_progress(
        self,
        job_id: str,
        stage: str,
        progress_percent: int,
        status: Optional[JobStatus] = None,
        analysis_id: Optional[str] = None,
        limitations: Optional[List[str]] = None,
    ) -> None:
        """Update job stage, progress percentage, and optional attributes atomically."""
        async with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                return
            record.current_stage = stage
            record.progress_percent = max(0, min(100, progress_percent))
            if status:
                record.status = status
            if analysis_id:
                record.analysis_id = analysis_id
            if limitations:
                record.limitations = list(set(record.limitations + limitations))

    async def _run_job(
        self,
        job_id: str,
        coro_fn: Callable[..., Coroutine[Any, Any, Any]],
        pass_job_context: bool = False,
    ) -> None:
        """Internal execution wrapper updating status transitions and sanitizing errors."""
        record = self._jobs.get(job_id)
        if not record:
            return

        record.status = JobStatus.PROCESSING
        record.current_stage = JobStatus.PROCESSING.value
        record.started_at = utc_now_iso()
        logger.info(f"Background job {job_id} started", extra={"event": "job_started", "job_id": job_id})

        try:
            if pass_job_context:
                result = await coro_fn(job_id)
            else:
                result = await coro_fn()

            # If the coroutine did not already set COMPLETED_WITH_LIMITATIONS
            if record.status not in (JobStatus.COMPLETED, JobStatus.COMPLETED_WITH_LIMITATIONS):
                if record.limitations:
                    record.status = JobStatus.COMPLETED_WITH_LIMITATIONS
                else:
                    record.status = JobStatus.COMPLETED

            record.current_stage = record.status.value
            record.progress_percent = 100
            record.completed_at = utc_now_iso()
            record.result = result
            logger.info(f"Background job {job_id} completed successfully", extra={"event": "job_completed", "job_id": job_id})
        except asyncio.CancelledError:
            record.status = JobStatus.CANCELLED
            record.current_stage = JobStatus.CANCELLED.value
            record.completed_at = utc_now_iso()
            record.error = "Job was cancelled by operator request."
            logger.warning(f"Background job {job_id} was cancelled", extra={"event": "job_cancelled", "job_id": job_id})
            raise
        except Exception as exc:
            # Map exception types to explicit failure states
            exc_str = str(exc)
            # Sanitize internal error messages - do not expose internal stack traces or database connection details
            sanitized_err = exc_str.split("\n")[0][:300] if exc_str else "An unexpected processing error occurred."

            if getattr(exc, "job_status", None):
                record.status = exc.job_status
            elif "Validation" in type(exc).__name__ or "validation" in exc_str.lower():
                record.status = JobStatus.VALIDATION_FAILED
            elif "Persistence" in type(exc).__name__ or "database" in exc_str.lower() or "transaction" in exc_str.lower():
                record.status = JobStatus.PERSISTENCE_FAILED
            elif "Artifact" in type(exc).__name__ or "storage" in exc_str.lower():
                record.status = JobStatus.ARTIFACT_FAILED
            else:
                record.status = JobStatus.FAILED

            record.current_stage = record.status.value
            record.completed_at = utc_now_iso()
            record.error = sanitized_err
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
            record = self._jobs.get(job_id)
            if task and not task.done():
                task.cancel()
                if record:
                    record.status = JobStatus.CANCELLED
                    record.current_stage = JobStatus.CANCELLED.value
                    record.error = "Job was cancelled by operator request."
                return True
            return False

    async def list_jobs(
        self,
        limit: int = 50,
        status: Optional[JobStatus] = None,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[JobRecord]:
        """List recently executed or pending jobs filtered by optional criteria."""
        async with self._lock:
            records = list(self._jobs.values())
            if status:
                records = [r for r in records if r.status == status]
            if project_id:
                records = [r for r in records if r.project_id == project_id]
            if user_id:
                records = [r for r in records if r.user_id == user_id]
            return records[-limit:]


# Global default job manager instance for Phase 3A
default_job_manager = JobManager()
