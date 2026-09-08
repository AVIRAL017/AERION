"""
AERION — Application Services (Phase 3E)
Implements:
- ImageProcessingService
- DamageAnalysisService
- BorderVideoService (streaming frame-by-frame without filling RAM)
- SatelliteAnalysisService
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union
import cv2
import numpy as np

from aerion_runtime_contracts import AERIONAnalysisResult
from app.core.config import get_settings
from app.core.jobs import JobManager, default_job_manager
from app.runtime.adapter import FROZEN_DAMAGE_THRESHOLD
from app.schemas.evidence import OperationMode, TemporalMode
from app.services.runtime_manager import RuntimeManager, default_runtime_manager
from app.services.situation_engine import SituationEngine

logger = logging.getLogger("aerion.services.application")


class ImageProcessingService:
    """Handles static perception analysis requests for drone imagery."""

    def __init__(self, runtime_manager: Optional[RuntimeManager] = None):
        self.runtime_manager = runtime_manager or default_runtime_manager

    async def analyze_image(
        self,
        image_path: str,
        mode: str = "disaster",
        drone_model: str = "visdrone_only",
        terrain_context: Optional[str] = "arid",
        run_intelligence: bool = True,
    ) -> AERIONAnalysisResult:
        return await self.runtime_manager.run_image_inference(
            image_path_or_array=image_path,
            source_type="drone",
            mode=mode,
            drone_model=drone_model,
            terrain_context=terrain_context,
            run_intelligence=run_intelligence,
        )


class SatelliteAnalysisService:
    """Handles static satellite OBB perception requests."""

    def __init__(self, runtime_manager: Optional[RuntimeManager] = None):
        self.runtime_manager = runtime_manager or default_runtime_manager

    async def analyze_satellite_image(
        self,
        image_path: str,
        terrain_context: Optional[str] = "arid",
        run_intelligence: bool = True,
    ) -> AERIONAnalysisResult:
        return await self.runtime_manager.run_image_inference(
            image_path_or_array=image_path,
            source_type="satellite",
            mode="disaster",
            terrain_context=terrain_context,
            run_intelligence=run_intelligence,
        )


class DamageAnalysisService:
    """Handles bi-temporal disaster damage analysis requests."""

    def __init__(self, runtime_manager: Optional[RuntimeManager] = None):
        self.runtime_manager = runtime_manager or default_runtime_manager

    async def analyze_damage_pair(
        self,
        before_path: str,
        after_path: str,
        threshold: float = FROZEN_DAMAGE_THRESHOLD,
        run_intelligence: bool = True,
    ) -> AERIONAnalysisResult:
        return await self.runtime_manager.run_damage_inference(
            before_path=before_path,
            after_path=after_path,
            threshold=threshold,
            run_intelligence=run_intelligence,
        )


class BorderVideoJobService:
    """
    Processes recorded border video files sequentially using frame iteration.
    Guarantees:
    - Never loads all frames into RAM simultaneously (generator streaming)
    - Enforces GPU lock serialization per frame
    - Integrates with SituationEngine for continuous state tracking
    """

    def __init__(
        self,
        runtime_manager: Optional[RuntimeManager] = None,
        job_manager: Optional[JobManager] = None,
    ):
        self.runtime_manager = runtime_manager or default_runtime_manager
        self.job_manager = job_manager or default_job_manager

    async def process_video_file(
        self,
        project_id: str,
        video_path: str,
        max_frames: Optional[int] = None,
        frame_stride: int = 1,
        terrain_context: Optional[str] = "arid",
    ) -> Dict[str, Any]:
        """Iterates over video frames without caching raw frames in memory."""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video source: {video_path}")

        total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        engine = SituationEngine(
            project_id=project_id,
            mode=OperationMode.BORDER_SECURITY,
            temporal_mode=TemporalMode.RECORDED_FOOTAGE,
        )

        processed_count = 0
        frame_idx = 0

        try:
            while True:
                success, frame = cap.read()
                if not success:
                    break

                if frame_idx % frame_stride == 0:
                    result = await self.runtime_manager.run_border_frame_inference(
                        frame=frame,
                        frame_number=frame_idx,
                        terrain_context=terrain_context,
                    )
                    engine.ingest_runtime_result(result)
                    processed_count += 1

                    if max_frames is not None and processed_count >= max_frames:
                        break

                frame_idx += 1
                # Yield to event loop
                await asyncio.sleep(0)
        finally:
            cap.release()

        report = engine.generate_border_report()
        return {
            "processed_frames": processed_count,
            "total_video_frames": total_video_frames,
            "report": report.model_dump(),
        }
