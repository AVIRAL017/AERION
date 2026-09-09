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
from app.services.video_annotation_service import VideoAnnotationResult, VideoAnnotationService

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
            mode="border",
            drone_model="visdrone_only",
            terrain_context=terrain_context,
            run_intelligence=run_intelligence,
        )

    async def analyze_satellite_tile(
        self,
        image_path: str,
        terrain_context: Optional[str] = "arid",
        run_intelligence: bool = True,
    ) -> AERIONAnalysisResult:
        return await self.analyze_satellite_image(
            image_path=image_path,
            terrain_context=terrain_context,
            run_intelligence=run_intelligence,
        )


class DamageAnalysisService:
    """Handles bi-temporal damage assessment via frozen Siamese ResNet18."""

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
    Streaming video job service for recorded border surveillance footage.
    Guarantees:
    - Never loads all frames into RAM simultaneously (generator streaming)
    - Enforces GPU lock serialization per frame
    - Integrates with SituationEngine for continuous state tracking
    - Encodes and saves derived annotated video artifact frame-by-frame via VideoAnnotationService
    """

    def __init__(
        self,
        runtime_manager: Optional[RuntimeManager] = None,
        job_manager: Optional[JobManager] = None,
        video_annotation_service: Optional[VideoAnnotationService] = None,
    ):
        self.runtime_manager = runtime_manager or default_runtime_manager
        self.job_manager = job_manager or default_job_manager
        self.annotation_service = video_annotation_service or VideoAnnotationService()

    async def process_video_file(
        self,
        project_id: str,
        video_path: str,
        max_frames: Optional[int] = None,
        frame_stride: int = 1,
        terrain_context: Optional[str] = "arid",
        generate_annotated_video: bool = True,
    ) -> Dict[str, Any]:
        """Iterates over video frames without caching raw frames in memory, rendering derived video evidence."""
        import tempfile
        import shutil

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video source: {video_path}")

        total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        source_fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        engine = SituationEngine(
            project_id=project_id,
            mode=OperationMode.BORDER_SECURITY,
            temporal_mode=TemporalMode.RECORDED_FOOTAGE,
        )

        # Retrieve pipeline zone boundary if available
        zone_polygon = None
        try:
            orch = await self.runtime_manager.adapter.get_orchestrator(
                mode="border",
                drone_model="visdrone_only",
                terrain_type=terrain_context,
            )
            pipeline = orch.get_border_pipeline()
            zone_polygon = getattr(pipeline, "zone_polygon", None)
        except Exception as exc:
            logger.debug(f"Could not pre-load zone polygon from pipeline: {exc}")

        # Setup streaming video writer if annotation requested
        video_writer: Optional[cv2.VideoWriter] = None
        temp_annot_dir: Optional[Path] = None
        temp_annot_video_path: Optional[Path] = None

        if generate_annotated_video:
            temp_annot_dir = Path(tempfile.mkdtemp(prefix="aerion_video_annot_"))
            temp_annot_video_path = temp_annot_dir / f"{uuid.uuid4()}.mp4"
            # Output video FPS matches processed frame rate or source FPS
            effective_fps = max(1.0, source_fps / frame_stride)
            video_writer = self.annotation_service.create_video_writer(
                output_path=temp_annot_video_path,
                fps=effective_fps,
                width=frame_w,
                height=frame_h,
            )

        processed_count = 0
        frame_idx = 0
        unique_track_ids = set()
        total_detections = 0
        last_runtime_result: Optional[AERIONAnalysisResult] = None

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
                    last_runtime_result = result

                    # Collect metrics
                    for d in result.detections:
                        total_detections += 1
                        if d.track_id is not None:
                            unique_track_ids.add(d.track_id)
                    for t in (result.tracks or []):
                        if getattr(t, "track_id", None) is not None:
                            unique_track_ids.add(t.track_id)

                    # Stream-render to output video writer
                    if video_writer is not None:
                        # Extract real tracker history
                        tracker_history = {}
                        try:
                            orch = await self.runtime_manager.adapter.get_orchestrator(mode="border")
                            p = orch.get_border_pipeline()
                            tracker_history = getattr(p.tracker, "history", {})
                        except Exception:
                            tracker_history = {}

                        annotated_frame = self.annotation_service.annotate_frame(
                            canvas=frame.copy(),
                            analysis_result=result,
                            frame_idx=frame_idx,
                            total_source_frames=total_video_frames,
                            zone_polygon=zone_polygon,
                            tracker_history=tracker_history,
                        )
                        video_writer.write(annotated_frame)
                        del annotated_frame

                    if max_frames is not None and processed_count >= max_frames:
                        break

                frame_idx += 1
                # Yield to event loop
                await asyncio.sleep(0)
        finally:
            cap.release()
            if video_writer is not None:
                video_writer.release()

        report = engine.generate_border_report()

        # Finalize and store derived video artifact
        annotated_video_artifact: Optional[Dict[str, Any]] = None
        try:
            if generate_annotated_video and temp_annot_video_path and temp_annot_video_path.exists():
                proj_uuid = uuid.UUID(project_id) if len(project_id) == 36 else uuid.UUID("00000000-0000-0000-0000-000000000001")
                effective_fps = max(1.0, source_fps / frame_stride)
                artifact_res = self.annotation_service.finalize_and_store(
                    temp_video_path=temp_annot_video_path,
                    project_id=proj_uuid,
                    width=frame_w,
                    height=frame_h,
                    fps=effective_fps,
                    frame_count=processed_count,
                    source_frame_count=total_video_frames,
                    unique_tracks=len(unique_track_ids),
                    total_detections=total_detections,
                )
                annotated_video_artifact = artifact_res.to_dict()
        except Exception as exc:
            logger.error(f"Failed to finalize annotated video artifact: {exc}", exc_info=True)
        finally:
            if temp_annot_dir and temp_annot_dir.exists():
                shutil.rmtree(temp_annot_dir, ignore_errors=True)

        return {
            "processed_frames": processed_count,
            "total_video_frames": total_video_frames,
            "report": report.model_dump(),
            "annotated_video_artifact": annotated_video_artifact,
            "last_analysis_result": last_runtime_result,
        }
