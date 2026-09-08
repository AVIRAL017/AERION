"""
AERION — GPU Inference Mutex
Provides an asynchronous serialization lock guarding GPU VRAM allocation.
Ensures single-occupancy GPU execution on hardware constrained by the 6 GB RTX 3050 ceiling.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from app.core.errors import InferenceTimeoutError
from app.core.logging import get_logger

logger = get_logger("inference_lock")


class InferenceLock:
    """
    Asynchronous serialized execution lock protecting GPU memory.

    AERION models (YOLOv8 + Siamese ResNet18) operate on a dedicated 6 GB VRAM budget.
    Simultaneous model execution or concurrent memory allocations cause Out-Of-Memory (OOM)
    fatal crashes. This lock guarantees strict serialized access to hardware inference.

    NOTE: This is initially a single-process asyncio serialization mechanism.
    Distributed multi-node locking will be handled in Phase 3E/Phase 4.
    """

    def __init__(self, default_timeout: float = 60.0) -> None:
        self.default_timeout = default_timeout
        self._lock = asyncio.Lock()
        self._active_task_name: Optional[str] = None
        self._waiters_count: int = 0

    @property
    def is_locked(self) -> bool:
        """True if an inference task is currently holding the GPU lock."""
        return self._lock.locked()

    @property
    def active_task_name(self) -> Optional[str]:
        """Name or description of the task currently holding the lock."""
        return self._active_task_name

    @property
    def waiters_count(self) -> int:
        """Number of pending requests currently queued waiting for the GPU."""
        return self._waiters_count

    @asynccontextmanager
    async def acquire(
        self,
        task_name: str = "inference_task",
        timeout: Optional[float] = None,
    ) -> AsyncIterator[None]:
        """
        Acquire the GPU lock with timeout protection and cancellation safety.

        Parameters
        ----------
        task_name:
            Descriptive name for structured logging and status tracking.
        timeout:
            Max seconds to wait before raising InferenceTimeoutError.
            Defaults to self.default_timeout if None.
        """
        effective_timeout = timeout if timeout is not None else self.default_timeout
        self._waiters_count += 1
        lock_acquired = False

        logger.debug(
            f"Task '{task_name}' requesting GPU inference lock (queued waiters: {self._waiters_count})",
            extra={"event": "gpu_lock_request", "task_name": task_name, "waiters": self._waiters_count},
        )

        try:
            # Wait for lock acquisition bounded by timeout
            await asyncio.wait_for(self._lock.acquire(), timeout=effective_timeout)
            lock_acquired = True
            self._waiters_count = max(0, self._waiters_count - 1)
            self._active_task_name = task_name
            logger.info(
                f"GPU inference lock acquired by '{task_name}'",
                extra={"event": "gpu_lock_acquired", "task_name": task_name},
            )
            yield
        except asyncio.TimeoutError:
            logger.error(
                f"GPU inference lock acquisition timed out after {effective_timeout}s for '{task_name}'",
                extra={"event": "gpu_lock_timeout", "task_name": task_name, "timeout": effective_timeout},
            )
            raise InferenceTimeoutError(
                message=f"Inference lock acquisition timed out after {effective_timeout}s. GPU is currently occupied.",
                details=[{"field": "inference_lock", "issue": "lock_acquisition_timeout", "provided": task_name}],
            )
        finally:
            if not lock_acquired:
                self._waiters_count = max(0, self._waiters_count - 1)
            else:
                self._active_task_name = None
                self._lock.release()
                logger.info(
                    f"GPU inference lock released by '{task_name}'",
                    extra={"event": "gpu_lock_released", "task_name": task_name},
                )


# Global process-level inference lock instance for Phase 3A
default_inference_lock = InferenceLock()
