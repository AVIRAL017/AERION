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

from aerion_runtime_contracts import AERIONAnalysisResult, SceneSummary
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
        confidence_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None,
    ) -> AERIONAnalysisResult:
        return await self.runtime_manager.run_image_inference(
            image_path_or_array=image_path,
            source_type="drone",
            mode=mode,
            drone_model=drone_model,
            terrain_context=terrain_context,
            run_intelligence=run_intelligence,
            confidence=confidence_threshold,
            iou=iou_threshold,
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
        confidence_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None,
    ) -> AERIONAnalysisResult:
        return await self.runtime_manager.run_image_inference(
            image_path_or_array=image_path,
            source_type="satellite",
            mode="border",
            drone_model="visdrone_only",
            terrain_context=terrain_context,
            run_intelligence=run_intelligence,
            confidence=confidence_threshold,
            iou=iou_threshold,
        )

    async def analyze_satellite_tile(
        self,
        image_path: str,
        terrain_context: Optional[str] = "arid",
        run_intelligence: bool = True,
        confidence_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None,
    ) -> AERIONAnalysisResult:
        return await self.analyze_satellite_image(
            image_path=image_path,
            terrain_context=terrain_context,
            run_intelligence=run_intelligence,
            confidence_threshold=confidence_threshold,
            iou_threshold=iou_threshold,
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
        from app.services.damage_validator import DamagePairValidator
        validation_res = DamagePairValidator.validate_pair(before_path, after_path)
        if not validation_res.is_compatible:
            rejection_reason = validation_res.rejection_reason or "Insufficient scene/spatial correspondence between T0 and T1."
            return AERIONAnalysisResult(
                project="AERION",
                version="v1",
                analysis_id=str(uuid.uuid4()),
                mode="disaster",
                source_type="damage_pair",
                image_width=validation_res.after_dimensions[0],
                image_height=validation_res.after_dimensions[1],
                frame_number=None,
                detections=[],
                tracks=[],
                border_analysis=[],
                damage_analysis=None,
                intelligence=[],
                summary=SceneSummary(),
                overall_status="PAIR_VALIDATION_FAILED",
                metadata={
                    "status": "PAIR_MISMATCH",
                    "overall_status": "PAIR_VALIDATION_FAILED",
                    "pair_validation": validation_res.to_dict(),
                    "rejection_reason": rejection_reason,
                    "damage_analysis": None,
                    "risk_assessment": {
                        "status": "NOT_AVAILABLE",
                        "reason": "DAMAGE PAIR INVALID",
                        "score": None,
                        "level": "UNAVAILABLE",
                    },
                },
            )

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
        zone_polygon: Optional[List[Any]] = None,
        sector_id: Optional[str] = None,
        sector_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Iterates over video frames without caching raw frames in memory, rendering derived video evidence and real-time threat timeline."""
        import tempfile
        import shutil
        from app.services.storage_service import LocalArtifactStorage

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video source: {video_path}")

        total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        source_fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Explicit user-configured zone vs neutral unconfigured state
        effective_zone: Optional[List[Tuple[float, float]]] = None
        if zone_polygon and len(zone_polygon) >= 3:
            effective_zone = [(float(p[0]), float(p[1])) for p in zone_polygon]

        effective_sector_name = sector_name or ("Operational Border Zone" if effective_zone else "BORDER CONTEXT NOT SET")
        effective_sector_id = sector_id or ("ZONE-CONFIGURED" if effective_zone else "NO-ZONE-CONFIGURED")

        engine = SituationEngine(
            project_id=project_id,
            mode=OperationMode.BORDER_SECURITY,
            temporal_mode=TemporalMode.RECORDED_FOOTAGE,
            sector_id=effective_sector_id,
            sector_name=effective_sector_name,
            sector_type="SENSOR_RELATIVE",
            authoritative_border_available=False,
            sensor_coverage_ratio=None,
            terrain_type=terrain_context or "arid",
        )

        # Setup streaming video writer if annotation requested
        video_writer: Optional[cv2.VideoWriter] = None
        temp_annot_dir: Optional[Path] = None
        temp_annot_video_path: Optional[Path] = None

        if generate_annotated_video:
            temp_annot_dir = Path(tempfile.mkdtemp(prefix="aerion_video_annot_"))
            temp_annot_video_path = temp_annot_dir / f"{uuid.uuid4()}.mp4"
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
        all_detections: List[Dict[str, Any]] = []
        all_tracks: List[Dict[str, Any]] = []
        last_runtime_result: Optional[AERIONAnalysisResult] = None
        effective_total_frames = min(max_frames, (total_video_frames + frame_stride - 1) // frame_stride) if max_frames else max(1, (total_video_frames + frame_stride - 1) // frame_stride)

        # Real-time Threat & Zone Tracking Structures
        threat_timeline: List[Dict[str, Any]] = []
        threat_level_changes: List[Dict[str, Any]] = []
        evidence_frames: List[Dict[str, Any]] = []
        track_threat_history: Dict[int, List[Dict[str, Any]]] = {}
        track_zone_history: Dict[int, str] = {}
        track_threat_level_history: Dict[int, str] = {}
        vehicle_classes: Dict[str, int] = {}
        zone_entry_count = 0
        zone_exit_count = 0
        vehicles_inside: Set[int] = set()
        vehicles_approached: Set[int] = set()

        storage_service = LocalArtifactStorage()
        proj_uuid = uuid.UUID(project_id) if len(project_id) == 36 else uuid.UUID("00000000-0000-0000-0000-000000000001")

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
                        border_zone_polygon=effective_zone,
                    )
                    engine.ingest_runtime_result(result)
                    processed_count += 1
                    last_runtime_result = result

                    t_sec = round(frame_idx / source_fps, 2)
                    t_fmt = f"{int(t_sec // 60):02d}:{t_sec % 60:04.1f}"

                    # Collect metrics and structured detection evidence
                    for det_i, d in enumerate(result.detections):
                        total_detections += 1
                        det_dict = d.to_dict()
                        det_dict["frame_number"] = frame_idx
                        det_id = getattr(d, "detection_id", f"{frame_idx}_{det_i}")
                        det_dict["evidence_reference"] = f"FRAME_{frame_idx}_DET_{det_id}"
                        all_detections.append(det_dict)
                        if d.track_id is not None:
                            unique_track_ids.add(d.track_id)
                        c_name = d.class_name or "vehicle"
                        vehicle_classes[c_name] = vehicle_classes.get(c_name, 0) + 1

                    for t in (result.tracks or []):
                        track_dict = t.to_dict()
                        track_dict["frame_number"] = frame_idx
                        all_tracks.append(track_dict)
                        tid = getattr(t, "track_id", None)
                        if tid is not None:
                            unique_track_ids.add(tid)

                        # Match with BorderAnalysis
                        matching_ba = None
                        if result.border_analysis:
                            for ba in result.border_analysis:
                                if ba.track_id == tid:
                                    matching_ba = ba
                                    break

                        # Determine Zone State and Threat Level based on actual evidence
                        is_key_event = False
                        if effective_zone and matching_ba:
                            if matching_ba.zone_entry:
                                zone_state = "ENTERED DEMO ZONE"
                                zone_entry_count += 1
                                vehicles_inside.add(tid)
                                is_key_event = True
                            elif matching_ba.zone_exit:
                                zone_state = "LEFT DEMO ZONE"
                                zone_exit_count += 1
                                vehicles_inside.discard(tid)
                                is_key_event = True
                            elif matching_ba.inside_restricted_zone:
                                zone_state = "INSIDE DEMO ZONE"
                                vehicles_inside.add(tid)
                            elif (matching_ba.direction_relation in ("entering_zone", "toward_boundary") or (matching_ba.approach_score or 0) > 0.4):
                                zone_state = "APPROACHING DEMO ZONE"
                                vehicles_approached.add(tid)
                            else:
                                zone_state = "OUTSIDE DEMO ZONE"

                            threat_lvl = matching_ba.border_priority or "LOW"
                            score = float(matching_ba.border_activity_score or 0.0)

                            # Calculate observable threat trend
                            hist = track_threat_history.get(tid, [])
                            if hist:
                                prev_s = hist[-1]["score"]
                                if score > prev_s + 0.05:
                                    trend = "RISING"
                                elif score < prev_s - 0.05:
                                    trend = "FALLING"
                                else:
                                    trend = "STABLE"
                            else:
                                trend = "BASELINE"
                            track_threat_history.setdefault(tid, []).append({"score": score, "level": threat_lvl})
                        else:
                            zone_state = "NO DEMO ZONE CONFIGURED"
                            threat_lvl = "UNAVAILABLE"
                            trend = "UNAVAILABLE"

                        # Track threat level transition
                        prev_threat_lvl = track_threat_level_history.get(tid)
                        if prev_threat_lvl and prev_threat_lvl != threat_lvl and threat_lvl != "UNAVAILABLE":
                            threat_level_changes.append({
                                "timestamp": t_fmt,
                                "timestamp_seconds": t_sec,
                                "frame_number": frame_idx,
                                "track_id": tid,
                                "object_class": t.class_name,
                                "previous_threat_level": prev_threat_lvl,
                                "current_threat_level": threat_lvl,
                                "zone_state": zone_state,
                            })
                            is_key_event = True
                        track_threat_level_history[tid] = threat_lvl

                        prev_zone = track_zone_history.get(tid)
                        track_zone_history[tid] = zone_state

                        ev_id = f"EV-F{frame_idx}-T{tid}"
                        threat_timeline.append({
                            "timestamp": t_fmt,
                            "timestamp_seconds": t_sec,
                            "frame_number": frame_idx,
                            "track_id": tid,
                            "object_class": t.class_name,
                            "zone_state": zone_state,
                            "event": f"VEHICLE {zone_state}",
                            "threat_level": threat_lvl,
                            "threat_trend": trend,
                            "confidence": round(float(t.confidence), 4),
                            "movement_state": getattr(t, "direction", "unknown"),
                            "position": [round(t.center.x, 1), round(t.center.y, 1)] if getattr(t, "center", None) else None,
                            "evidence_id": ev_id,
                        })

                        # Extract authenticated evidence frame for key events
                        if (is_key_event or tid not in track_threat_history or threat_lvl in ("HIGH", "CRITICAL")) and len(evidence_frames) < 18:
                            try:
                                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_f:
                                    tmp_f_path = Path(tmp_f.name)
                                cv2.imwrite(str(tmp_f_path), frame)
                                art_key, sha256_hex, fsize = storage_service.store_file(
                                    source_path=tmp_f_path,
                                    asset_type="evidence_frames",
                                    project_id=proj_uuid,
                                    suffix=".jpg",
                                )
                                tmp_f_path.unlink(missing_ok=True)
                                evidence_frames.append({
                                    "evidence_id": ev_id,
                                    "frame_number": frame_idx,
                                    "timestamp": t_fmt,
                                    "timestamp_seconds": t_sec,
                                    "track_id": tid,
                                    "object_class": t.class_name,
                                    "event_description": f"Vehicle Track #{tid} ({t.class_name}) {zone_state.lower()} with {threat_lvl} threat level",
                                    "threat_level": threat_lvl,
                                    "confidence": round(float(t.confidence), 4),
                                    "artifact_key": art_key,
                                    "sha256": sha256_hex,
                                    "bounding_box": [t.bbox.x1, t.bbox.y1, t.bbox.x2, t.bbox.y2] if getattr(t, "bbox", None) else None,
                                    "provenance": "Observed from video surveillance frame inference",
                                })
                            except Exception as ev_err:
                                logger.debug(f"Could not persist evidence frame: {ev_err}")

                    # Stream-render to output video writer
                    if video_writer is not None:
                        tracker_history = {}
                        try:
                            orch = await self.runtime_manager.adapter.get_orchestrator(
                                mode="border",
                                drone_model="visdrone_only",
                                terrain_type=terrain_context,
                                border_zone_polygon=effective_zone,
                            )
                            p = orch.get_border_pipeline()
                            tracker_history = getattr(p.tracker, "history", {})
                        except Exception:
                            tracker_history = {}

                        annotated_frame = self.annotation_service.annotate_frame(
                            canvas=frame.copy(),
                            analysis_result=result,
                            frame_idx=frame_idx,
                            total_source_frames=total_video_frames,
                            zone_polygon=effective_zone,
                            tracker_history=tracker_history,
                            processed_frame_idx=processed_count - 1,
                            total_processed_frames=effective_total_frames,
                        )
                        video_writer.write(annotated_frame)
                        del annotated_frame

                    if max_frames is not None and processed_count >= max_frames:
                        break

                frame_idx += 1
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
                annotated_video_artifact["storage_key"] = artifact_res.artifact_key
                annotated_video_artifact["filename"] = Path(artifact_res.artifact_key).name
                annotated_video_artifact["byte_size"] = artifact_res.file_size_bytes
                annotated_video_artifact["duration"] = round(artifact_res.duration_seconds, 2)
        except Exception as exc:
            logger.error(f"Failed to finalize annotated video artifact: {exc}", exc_info=True)
        finally:
            if temp_annot_dir and temp_annot_dir.exists():
                shutil.rmtree(temp_annot_dir, ignore_errors=True)

        # Calculate confidence statistics across actual runtime detections
        conf_list = [float(d.get("confidence", 0.0)) for d in all_detections]
        min_conf = min(conf_list) if conf_list else 0.0
        max_conf = max(conf_list) if conf_list else 0.0
        mean_conf = (sum(conf_list) / len(conf_list)) if conf_list else 0.0

        vehicle_summary = {
            "total_vehicles_observed": len(unique_track_ids),
            "class_distribution": vehicle_classes,
            "approaching_count": len(vehicles_approached),
            "entered_count": zone_entry_count,
            "left_count": zone_exit_count,
            "currently_inside_count": len(vehicles_inside),
        }

        demo_zone_activity = {
            "zone_configured": bool(effective_zone),
            "status": "CONFIGURED" if effective_zone else "NO_DEMO_ZONE_CONFIGURED",
            "sector_name": effective_sector_name,
            "zone_geometry": effective_zone if effective_zone else None,
            "total_entries": zone_entry_count,
            "total_exits": zone_exit_count,
            "active_in_zone": len(vehicles_inside),
            "message": f"{zone_entry_count} entries, {zone_exit_count} exits recorded." if effective_zone else "BORDER CONTEXT NOT SET. Threat relative to demo zone is UNAVAILABLE.",
        }

        return {
            "processed_frames": processed_count,
            "total_video_frames": total_video_frames,
            "report": report.model_dump(),
            "annotated_video_artifact": annotated_video_artifact,
            "annotated_artifact": annotated_video_artifact,
            "last_analysis_result": last_runtime_result,
            "all_detections": all_detections,
            "tracks": all_tracks,
            "unique_tracks_count": len(unique_track_ids),
            "total_detections_count": total_detections,
            "threat_timeline": threat_timeline,
            "threat_level_changes": threat_level_changes,
            "evidence_frames": evidence_frames,
            "vehicle_summary": vehicle_summary,
            "demo_zone_activity": demo_zone_activity,
            "detection_confidence_stats": {
                "min_confidence": round(min_conf, 4),
                "max_confidence": round(max_conf, 4),
                "mean_confidence": round(mean_conf, 4),
            },
        }
