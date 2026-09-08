"""
AERION — Application Runtime Manager (Phase 3E)
Manages the lifecycle of the frozen ML models, isolates damage model import-time
loading, serializes GPU execution across threads, and enforces lazy loading.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from app.core.config import get_settings
from app.core.errors import ModelUnavailableError
from app.core.inference_lock import InferenceLock, default_inference_lock
from app.runtime.adapter import (
    FROZEN_CONFIDENCE_THRESHOLD,
    FROZEN_DAMAGE_THRESHOLD,
    FROZEN_IOU_THRESHOLD,
    RuntimeAdapter,
    default_runtime_adapter,
)

logger = logging.getLogger("aerion.runtime.manager")


class DamageModelRunner:
    """
    Encapsulates and isolates the legacy Siamese ResNet18 model execution.
    Prevents eager model execution during web application startup.
    """

    @staticmethod
    def run_damage_inference(
        before_path: Union[str, Path],
        after_path: Union[str, Path],
        threshold: float = FROZEN_DAMAGE_THRESHOLD,
    ) -> Any:
        """Runs predict_damage in worker thread."""
        from damage_inference import predict_damage
        from aerion_runtime_normalizer import normalize_damage_result
        raw_output = predict_damage(str(before_path), str(after_path))
        return normalize_damage_result(raw_output, threshold=threshold)


class RuntimeManager:
    """
    Central manager for model lifecycle, inference serialization,
    and runtime execution across all operational modes.
    """

    def __init__(
        self,
        adapter: Optional[RuntimeAdapter] = None,
        inference_lock: Optional[InferenceLock] = None,
    ) -> None:
        self.adapter = adapter or default_runtime_adapter
        self.inference_lock = inference_lock or default_inference_lock
        self.settings = get_settings()

    async def run_image_inference(
        self,
        image_path_or_array: Union[str, np.ndarray],
        source_type: str = "drone",
        mode: str = "disaster",
        drone_model: str = "visdrone_only",
        terrain_context: Optional[str] = "arid",
        run_intelligence: bool = True,
    ) -> Any:
        """Executes serialized static perception inference."""
        orch = await self.adapter.get_orchestrator(
            mode=mode,
            drone_model=drone_model,
            terrain_type=terrain_context,
        )

        async with self.inference_lock.acquire(
            task_name=f"image_inference_{source_type}_{mode}",
            timeout=self.settings.INFERENCE_TIMEOUT_SECONDS,
        ):
            logger.info(f"Running serialized image inference ({source_type})")
            result = await asyncio.to_thread(
                orch.process_image,
                image=image_path_or_array,
                source_type=source_type,
                run_intelligence=run_intelligence,
            )
            return result

    async def run_damage_inference(
        self,
        before_path: Union[str, Path],
        after_path: Union[str, Path],
        threshold: float = FROZEN_DAMAGE_THRESHOLD,
        run_intelligence: bool = True,
    ) -> Any:
        """Executes bi-temporal Siamese damage analysis."""
        orch = await self.adapter.get_orchestrator(mode="disaster")

        async with self.inference_lock.acquire(
            task_name="damage_inference_siamese",
            timeout=self.settings.INFERENCE_TIMEOUT_SECONDS,
        ):
            logger.info("Running serialized Siamese damage inference")
            result = await asyncio.to_thread(
                orch.process_change_pair,
                before_path=before_path,
                after_path=after_path,
                threshold=threshold,
                run_intelligence=run_intelligence,
            )
            return result

    async def run_border_frame_inference(
        self,
        frame: Any,
        frame_number: int = 0,
        terrain_context: Optional[str] = "arid",
    ) -> Any:
        """Executes border surveillance frame inference with ByteTrack."""
        orch = await self.adapter.get_orchestrator(
            mode="border",
            drone_model="visdrone_only",
            terrain_type=terrain_context,
        )

        async with self.inference_lock.acquire(
            task_name="border_frame_inference",
            timeout=self.settings.INFERENCE_TIMEOUT_SECONDS,
        ):
            result = await asyncio.to_thread(
                orch.process_border_frame,
                frame=frame,
                frame_number=frame_number,
            )
            return result


default_runtime_manager = RuntimeManager()
