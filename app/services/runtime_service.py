"""
AERION — Runtime Application Service Boundary
Decouples API route endpoints from ML runtime execution details.
Mediates perception workflows, asynchronous task delegation, and job tracking.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
import numpy as np

from app.core.jobs import JobManager, JobRecord, default_job_manager
from app.core.logging import get_logger
from app.runtime.adapter import RuntimeAdapter, default_runtime_adapter

logger = get_logger("runtime_service")


class RuntimeService:
    """
    Application service managing ML perception, change assessment, and background processing.
    """

    def __init__(
        self,
        adapter: Optional[RuntimeAdapter] = None,
        job_manager: Optional[JobManager] = None,
    ) -> None:
        self.adapter = adapter or default_runtime_adapter
        self.job_manager = job_manager or default_job_manager

    async def analyze_image(
        self,
        image_input: Union[str, np.ndarray],
        source_type: str = "drone",
        mode: str = "disaster",
        drone_model: str = "visdrone_only",
        confidence: Optional[float] = None,
        iou: Optional[float] = None,
        run_intelligence: bool = True,
        terrain_context: Optional[str] = "arid",
    ) -> Any:
        """
        Execute synchronous single-image perception analysis.
        """
        logger.info(f"RuntimeService: analyzing image source_type='{source_type}', mode='{mode}'")
        return await self.adapter.process_image(
            image_input=image_input,
            source_type=source_type,
            mode=mode,
            drone_model=drone_model,
            confidence=confidence,
            iou=iou,
            run_intelligence=run_intelligence,
            terrain_context=terrain_context,
        )

    async def analyze_damage(
        self,
        pre_image: Union[str, np.ndarray],
        post_image: Union[str, np.ndarray],
        threshold: Optional[float] = None,
        run_intelligence: bool = True,
        terrain_context: Optional[str] = "arid",
    ) -> Any:
        """
        Execute synchronous bi-temporal disaster damage analysis.
        """
        logger.info("RuntimeService: analyzing bi-temporal damage")
        return await self.adapter.process_damage(
            pre_image=pre_image,
            post_image=post_image,
            threshold=threshold,
            run_intelligence=run_intelligence,
            terrain_context=terrain_context,
        )

    async def submit_async_image_analysis(
        self,
        task_name: str,
        image_input: Union[str, np.ndarray],
        source_type: str = "drone",
        mode: str = "disaster",
        drone_model: str = "visdrone_only",
        confidence: Optional[float] = None,
        iou: Optional[float] = None,
        run_intelligence: bool = True,
        terrain_context: Optional[str] = "arid",
    ) -> JobRecord:
        """
        Submit image analysis as a background job tracked via JobManager.
        """
        async def _job_coro():
            res = await self.adapter.process_image(
                image_input=image_input,
                source_type=source_type,
                mode=mode,
                drone_model=drone_model,
                confidence=confidence,
                iou=iou,
                run_intelligence=run_intelligence,
                terrain_context=terrain_context,
            )
            return res.to_dict() if hasattr(res, "to_dict") else res

        return await self.job_manager.submit_job(
            task_name=task_name,
            coro_fn=_job_coro,
        )

    async def get_job_status(self, job_id: str) -> Optional[JobRecord]:
        """Query state and result of a background job."""
        return await self.job_manager.get_job(job_id)


# Global service instance for Phase 3A
default_runtime_service = RuntimeService()
