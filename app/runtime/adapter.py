"""
AERION — Runtime Boundary Adapter
Encapsulates all interaction with the frozen AERIONOrchestrator and underlying ML models.
Guarantees strict lazy loading, GPU serialization lock enforcement, and off-thread execution.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Final, List, Optional, Tuple, Union
import numpy as np

from app.core.config import AERIONSettings, get_settings
from app.core.errors import ModelUnavailableError
from app.core.inference_lock import InferenceLock, default_inference_lock
from app.core.logging import get_logger

logger = get_logger("runtime_adapter")


# ================================================================
# FROZEN ML RUNTIME CONSTANTS (IMMUTABLE)
# Validated thresholds for AERION v1 models.
# Must NOT be modified, dynamic, or overridable via environment settings.
# ================================================================
FROZEN_CONFIDENCE_THRESHOLD: Final[float] = 0.25
FROZEN_IOU_THRESHOLD: Final[float] = 0.50
FROZEN_DAMAGE_THRESHOLD: Final[float] = 0.50


class RuntimeAdapter:
    """
    Adapter decoupling the FastAPI web layer from the frozen ML runtime.

    Key Architectural Invariants:
    1. LAZY LOADING: Neither this class nor its parent modules eagerly import or
       instantiate YOLOv8 or Siamese ResNet18 models during application startup.
    2. GPU MUTEX: Heavy perception calls acquire the shared InferenceLock to
       prevent concurrent memory allocations from violating the 6 GB VRAM ceiling.
    3. NON-BLOCKING: Synchronous ML operations run via asyncio.to_thread() to avoid
       starving the asynchronous web server event loop.
    4. FROZEN THRESHOLDS: Uses validated immutable runtime constants (conf=0.25,
       iou=0.50, damage=0.50) to preserve frozen model immutability.
    """

    # Class-level bindings to validated constants
    FROZEN_CONFIDENCE: Final[float] = FROZEN_CONFIDENCE_THRESHOLD
    FROZEN_IOU: Final[float] = FROZEN_IOU_THRESHOLD
    FROZEN_DAMAGE: Final[float] = FROZEN_DAMAGE_THRESHOLD

    def __init__(
        self,
        settings: Optional[AERIONSettings] = None,
        inference_lock: Optional[InferenceLock] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.inference_lock = inference_lock or default_inference_lock
        self._orchestrators: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    def _create_orchestrator(
        self,
        mode: str = "disaster",
        drone_model: str = "visdrone_only",
        terrain_type: Optional[str] = "arid",
    ) -> Any:
        """
        Instantiate an AERIONOrchestrator. Imports orchestrator lazily.
        Does not load models into GPU until detector methods are invoked.
        """
        try:
            from aerion_orchestrator import AERIONOrchestrator
            return AERIONOrchestrator(
                mode=mode,
                device=self.settings.DEVICE,
                drone_model=drone_model,
                confidence=FROZEN_CONFIDENCE_THRESHOLD,
                iou=FROZEN_IOU_THRESHOLD,
                terrain_type=terrain_type,
            )
        except Exception as exc:
            logger.exception(f"Failed to initialize AERIONOrchestrator for mode '{mode}': {exc}")
            raise ModelUnavailableError(
                message=f"Failed to initialize runtime perception orchestrator: {exc}",
                details=[{"field": "orchestrator", "issue": "initialization_failed", "provided": mode}],
            )

    async def get_orchestrator(
        self,
        mode: str = "disaster",
        drone_model: str = "visdrone_only",
        terrain_type: Optional[str] = "arid",
    ) -> Any:
        """Retrieve or lazily instantiate an orchestrator instance for the requested configuration."""
        key = f"{mode}:{drone_model}:{terrain_type}"
        async with self._lock:
            if key not in self._orchestrators:
                logger.info(f"Lazily creating AERIONOrchestrator instance for key: {key}")
                self._orchestrators[key] = self._create_orchestrator(
                    mode=mode,
                    drone_model=drone_model,
                    terrain_type=terrain_type,
                )
            return self._orchestrators[key]

    async def process_image(
        self,
        image_input: Union[str, np.ndarray],
        source_type: str = "drone",
        mode: str = "disaster",
        drone_model: str = "visdrone_only",
        confidence: Optional[float] = None,
        iou: Optional[float] = None,
        run_intelligence: bool = True,
        terrain_context: Optional[str] = "arid",
        timeout: Optional[float] = None,
    ) -> Any:
        """
        Execute perception inference on an aerial or satellite image.
        Protected by the GPU mutex and offloaded to worker thread.
        """
        orch = await self.get_orchestrator(mode=mode, drone_model=drone_model, terrain_type=terrain_context)
        conf = confidence if confidence is not None else FROZEN_CONFIDENCE_THRESHOLD
        iou_val = iou if iou is not None else FROZEN_IOU_THRESHOLD

        async with self.inference_lock.acquire(
            task_name=f"process_image_{source_type}_{mode}",
            timeout=timeout or self.settings.INFERENCE_TIMEOUT_SECONDS,
        ):
            logger.info(f"Executing process_image with source_type='{source_type}', mode='{mode}'")
            result = await asyncio.to_thread(
                orch.process_image,
                image_input=image_input,
                source_type=source_type,
                confidence=conf,
                iou=iou_val,
                run_intelligence=run_intelligence,
                terrain_context=terrain_context,
            )
            return result

    async def process_damage(
        self,
        pre_image: Union[str, np.ndarray],
        post_image: Union[str, np.ndarray],
        threshold: Optional[float] = None,
        run_intelligence: bool = True,
        terrain_context: Optional[str] = "arid",
        timeout: Optional[float] = None,
    ) -> Any:
        """
        Execute bi-temporal disaster damage inference using the Siamese ResNet18 model.
        Protected by the GPU mutex and offloaded to worker thread.
        """
        orch = await self.get_orchestrator(mode="disaster", terrain_type=terrain_context)
        dmg_threshold = threshold if threshold is not None else FROZEN_DAMAGE_THRESHOLD

        async with self.inference_lock.acquire(
            task_name="process_damage_siamese",
            timeout=timeout or self.settings.INFERENCE_TIMEOUT_SECONDS,
        ):
            logger.info("Executing process_damage via Siamese ResNet18")
            result = await asyncio.to_thread(
                orch.process_damage,
                pre_image=pre_image,
                post_image=post_image,
                threshold=dmg_threshold,
                run_intelligence=run_intelligence,
                terrain_context=terrain_context,
            )
            return result

    async def analyze_detections(
        self,
        detections: List[Dict[str, Any]],
        mode: str = "disaster",
        terrain_context: Optional[str] = None,
    ) -> Tuple[List[Any], Any]:
        """
        Execute deterministic intelligence scoring on existing detections.
        CPU-only scoring; does not require the GPU lock.
        """
        orch = await self.get_orchestrator(mode=mode, terrain_type=terrain_context)
        return await asyncio.to_thread(
            orch.analyze_detections,
            detections=detections,
            mode=mode,
            terrain_context=terrain_context,
        )

    async def generate_advisory_report(
        self,
        query_context: Dict[str, Any],
        mode: str = "disaster",
    ) -> Dict[str, Any]:
        """
        Generate deterministic advisory protocol information.
        CPU-only deterministic mapping; does not require the GPU lock.
        """
        orch = await self.get_orchestrator(mode=mode)
        return await asyncio.to_thread(
            orch.generate_advisory_report,
            query_context=query_context,
        )


# Global process-level adapter instance for Phase 3A
default_runtime_adapter = RuntimeAdapter()
