"""
AERION — Annotated Video Evidence Service (Roadmap Step 16)
Generates deterministic, presentation-grade annotated video evidence artifacts
from sequential frame-by-frame border surveillance inference and ByteTrack:
- Consumes real AERION runtime contracts (AERIONAnalysisResult, Detection, TrackState, BorderAnalysis)
- Strictly preserves source video file bytes (never overwrites original)
- Bounded memory safety: Sequential stream processing, 1 decoded frame in memory at a time
- Annotates real detections with class color palette and "CLASS CONF ID:<track_id>" badges
- Renders bounded historical trajectory tails from tracker history in pixel coordinates
- Renders verified border zone boundary polygon if configured
- Renders honest zero-detection banner when scene contains 0 detections
- Streams annotated frames to OpenCV VideoWriter (MP4V / AVC1)
- Stores derived video artifact via LocalArtifactStorage under <project_id>/annotated_video/<uuid>.mp4
- Computes cryptographic SHA-256 digest on completed disk artifact
- Cleans up incomplete or temporary artifacts on failure
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import cv2
import numpy as np

from aerion_runtime_contracts import AERIONAnalysisResult, BoundingBox, Detection, Point2D
from app.core.errors import ResourceNotFoundError, ValidationError
from app.core.security_utils import ALLOWED_VIDEO_EXTENSIONS, sanitize_local_path
from app.services.annotation_service import CLASS_PALETTE_BGR, DEFAULT_BOX_COLOR
from app.services.storage_service import LocalArtifactStorage

logger = logging.getLogger("aerion.services.video_annotation")

# Operational & safety constraints
MAX_VIDEO_FILE_SIZE = 150 * 1024 * 1024  # 150 MB hard ceiling
MAX_FRAME_DIMENSION = 8192               # Maximum width or height
DEFAULT_HISTORY_TAIL_MAX = 30            # Max points in trajectory tail


@dataclass
class VideoAnnotationResult:
    """
    Immutable representation of an annotated video evidence artifact.
    Contains storage metadata and perceptual metrics for zero-leakage API responses.
    """
    artifact_key: str
    sha256: str
    file_size_bytes: int
    mime_type: str
    width: int
    height: int
    fps: float
    frame_count: int
    source_frame_count: int
    codec: str
    duration_seconds: float
    unique_tracks_count: int
    total_detections_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_key": self.artifact_key,
            "sha256": self.sha256,
            "file_size_bytes": self.file_size_bytes,
            "mime_type": self.mime_type,
            "width": self.width,
            "height": self.height,
            "fps": round(self.fps, 2),
            "frame_count": self.frame_count,
            "source_frame_count": self.source_frame_count,
            "codec": self.codec,
            "duration_seconds": round(self.duration_seconds, 2),
            "unique_tracks_count": self.unique_tracks_count,
            "total_detections_count": self.total_detections_count,
        }


class VideoAnnotationService:
    """
    Evidence presentation service for producing audited, annotated video artifacts.
    Draws actual detections, track IDs, historical trajectory trails, and zone boundaries.
    """

    def __init__(self, storage: Optional[LocalArtifactStorage] = None):
        self.storage = storage or LocalArtifactStorage()

    @staticmethod
    def get_supported_codec() -> Tuple[str, str]:
        """
        Returns the primary supported fourcc and container extension for OpenCV VideoWriter.
        Uses 'mp4v' for maximum cross-platform reliability on Windows without external DLLs.
        """
        return "mp4v", ".mp4"

    def annotate_frame(
        self,
        canvas: np.ndarray,
        analysis_result: AERIONAnalysisResult,
        frame_idx: int,
        total_source_frames: int,
        zone_polygon: Optional[Sequence[Tuple[float, float]]] = None,
        tracker_history: Optional[Dict[int, List[Dict[str, float]]]] = None,
    ) -> np.ndarray:
        """
        Annotates a single frame using actual perception results:
        1. Configured border zone boundary
        2. Detections with class color and "CLASS CONF ID:<track_id>" badges
        3. Historical pixel trajectory trails for tracked entities
        4. Telemetry watermark / zero-detection banner
        """
        h, w = canvas.shape[:2]
        scale = max(w, h)
        line_thickness = max(2, int(scale / 600))
        font_scale = max(0.45, scale / 1800.0)
        font_thickness = max(1, int(scale / 1000))

        # 1. Render Border Zone Boundary if configured
        if zone_polygon and len(zone_polygon) >= 3:
            self._render_zone_boundary(canvas, zone_polygon, line_thickness)

        # 2. Render Trajectory Tails from tracker history
        if tracker_history:
            self._render_trajectories(canvas, tracker_history, line_thickness)

        detections = analysis_result.detections or []
        is_zero_detection = (len(detections) == 0)

        # 3. Render Detections
        if is_zero_detection:
            self._render_zero_detection_watermark(canvas, w, h, frame_idx, font_scale, font_thickness)
        else:
            for det in detections:
                color = CLASS_PALETTE_BGR.get(det.class_name.lower(), DEFAULT_BOX_COLOR)
                
                # Format truthful label: CLASS CONF ID:<track_id>
                track_tag = f" ID:{det.track_id}" if det.track_id is not None else ""
                label_text = f"{det.class_name.upper()} {det.confidence:.2f}{track_tag}"

                if det.bbox:
                    self._render_bbox(
                        canvas,
                        det.bbox,
                        label_text,
                        color,
                        line_thickness,
                        font_scale,
                        font_thickness,
                    )

        # 4. Top Telemetry Header
        self._render_telemetry_header(
            canvas,
            w,
            frame_idx,
            total_source_frames,
            len(detections),
            len(analysis_result.tracks) if analysis_result.tracks else 0,
            font_scale,
            font_thickness,
        )

        return canvas

    def _render_zone_boundary(
        self,
        canvas: np.ndarray,
        zone_polygon: Sequence[Tuple[float, float]],
        thickness: int,
    ) -> None:
        """Renders the configured border zone polygon with high visibility."""
        pts = np.array([[int(round(x)), int(round(y))] for x, y in zone_polygon], dtype=np.int32)
        # Translucent filled polygon overlay
        overlay = canvas.copy()
        cv2.fillPoly(overlay, [pts], (20, 20, 180))  # Muted crimson
        cv2.addWeighted(overlay, 0.15, canvas, 0.85, 0, canvas)
        # Crisp outline
        cv2.polylines(canvas, [pts], isClosed=True, color=(56, 213, 245), thickness=max(2, thickness), lineType=cv2.LINE_AA)

        # Zone title anchor
        tx, ty = pts[0]
        cv2.putText(
            canvas,
            "RESTRICTED BORDER ZONE",
            (int(tx) + 6, int(ty) - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (56, 213, 245),
            1,
            cv2.LINE_AA,
        )

    def _render_trajectories(
        self,
        canvas: np.ndarray,
        tracker_history: Dict[int, List[Dict[str, float]]],
        thickness: int,
    ) -> None:
        """
        Draws short trajectory tails connecting actual historical positions.
        Bounded to historical points stored by the tracker. Never extrapolates.
        """
        tail_thickness = max(1, thickness - 1)
        for track_id, points in tracker_history.items():
            if not points or len(points) < 2:
                continue
            
            # Use only recent bounded history
            recent_points = points[-DEFAULT_HISTORY_TAIL_MAX:]
            pts = np.array([[int(round(p["x"])), int(round(p["y"]))] for p in recent_points], dtype=np.int32)
            
            # Draw gradient or segmented polyline in amber/cyan
            cv2.polylines(
                canvas,
                [pts],
                isClosed=False,
                color=(245, 158, 11),  # Amber trajectory trail
                thickness=tail_thickness,
                lineType=cv2.LINE_AA,
            )
            # Small circle at latest center
            last_pt = pts[-1]
            cv2.circle(canvas, (int(last_pt[0]), int(last_pt[1])), 3, (56, 213, 245), -1)

    def _render_bbox(
        self,
        canvas: np.ndarray,
        bbox: BoundingBox,
        label: str,
        color: Tuple[int, int, int],
        thickness: int,
        font_scale: float,
        font_thickness: int,
    ) -> None:
        """Renders bounding box with solid badge."""
        x1 = max(0, int(round(bbox.x1)))
        y1 = max(0, int(round(bbox.y1)))
        x2 = min(canvas.shape[1] - 1, int(round(bbox.x2)))
        y2 = min(canvas.shape[0] - 1, int(round(bbox.y2)))

        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness)

        (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)
        badge_y1 = max(0, y1 - text_h - 8)
        badge_y2 = y1
        badge_x2 = min(canvas.shape[1], x1 + text_w + 8)

        cv2.rectangle(canvas, (x1, badge_y1), (badge_x2, badge_y2), color, -1)
        text_y = badge_y2 - 4
        cv2.putText(canvas, label, (x1 + 4, text_y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (7, 9, 12), font_thickness, cv2.LINE_AA)

    def _render_zero_detection_watermark(
        self,
        canvas: np.ndarray,
        w: int,
        h: int,
        frame_idx: int,
        font_scale: float,
        font_thickness: int,
    ) -> None:
        """Renders honest, non-fabricated zero-detection banner."""
        text = f"FRAME {frame_idx:04d} — AERION BORDER PERCEPTION: NO ACTIVE DETECTIONS"
        (text_w, text_h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale * 0.9, font_thickness)
        pad = 8
        bx1 = 16
        by2 = h - 16
        by1 = by2 - text_h - (pad * 2)
        bx2 = bx1 + text_w + (pad * 2)

        overlay = canvas.copy()
        cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (18, 22, 28), -1)
        cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (56, 213, 245), 1)
        cv2.addWeighted(overlay, 0.75, canvas, 0.25, 0, canvas)
        cv2.putText(canvas, text, (bx1 + pad, by2 - pad), cv2.FONT_HERSHEY_SIMPLEX, font_scale * 0.9, (56, 213, 245), font_thickness, cv2.LINE_AA)

    def _render_telemetry_header(
        self,
        canvas: np.ndarray,
        w: int,
        frame_idx: int,
        total_frames: int,
        detection_count: int,
        active_tracks: int,
        font_scale: float,
        font_thickness: int,
    ) -> None:
        """Renders top telemetry bar across canvas width."""
        bar_h = max(26, int(canvas.shape[0] * 0.04))
        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, 0), (w, bar_h), (7, 9, 12), -1)
        cv2.addWeighted(overlay, 0.85, canvas, 0.15, 0, canvas)

        line_text = (
            f"AERION BORDER SURVEILLANCE  |  FRAME {frame_idx + 1}/{total_frames}  |  "
            f"DETECTIONS: {detection_count}  |  ACTIVE TRACKS: {active_tracks}  |  "
            f"FROZEN YOLOv8 + BYTETRACK"
        )
        cv2.putText(
            canvas,
            line_text,
            (12, int(bar_h * 0.65)),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale * 0.75,
            (240, 240, 245),
            font_thickness,
            cv2.LINE_AA,
        )

    def create_video_writer(
        self,
        output_path: Union[str, Path],
        fps: float,
        width: int,
        height: int,
    ) -> cv2.VideoWriter:
        """
        Safely instantiates an OpenCV VideoWriter with probed fourcc codec.
        Fails fast if writer cannot be opened.
        """
        codec, _ = self.get_supported_codec()
        fourcc = cv2.VideoWriter_fourcc(*codec)
        writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
        if not writer.isOpened():
            # Fallback attempt to avc1 or XVID
            for fb_codec in ("avc1", "XVID"):
                logger.warning(f"Codec '{codec}' failed to open. Attempting fallback '{fb_codec}'.")
                fb_fourcc = cv2.VideoWriter_fourcc(*fb_codec)
                writer = cv2.VideoWriter(str(output_path), fb_fourcc, fps, (width, height))
                if writer.isOpened():
                    break
        if not writer.isOpened():
            raise RuntimeError(
                f"OpenCV VideoWriter failed to open for destination '{output_path}' with dimensions {width}x{height}."
            )
        return writer

    def finalize_and_store(
        self,
        temp_video_path: Path,
        project_id: uuid.UUID,
        width: int,
        height: int,
        fps: float,
        frame_count: int,
        source_frame_count: int,
        unique_tracks: int,
        total_detections: int,
    ) -> VideoAnnotationResult:
        """
        Stores the completed video into LocalArtifactStorage, computes SHA-256,
        and returns immutable VideoAnnotationResult.
        """
        if not temp_video_path.exists() or temp_video_path.stat().st_size == 0:
            raise ValidationError(
                message="Video encoding produced an empty or missing output artifact.",
                details=[{"field": "annotated_video", "issue": "empty_output"}],
            )

        codec, _ = self.get_supported_codec()
        storage_key, sha256_hex, file_size = self.storage.store_file(
            source_path=temp_video_path,
            asset_type="annotated_video",
            project_id=project_id,
            suffix=".mp4",
        )

        duration = (frame_count / fps) if fps > 0 else 0.0

        return VideoAnnotationResult(
            artifact_key=storage_key,
            sha256=sha256_hex,
            file_size_bytes=file_size,
            mime_type="video/mp4",
            width=width,
            height=height,
            fps=fps,
            frame_count=frame_count,
            source_frame_count=source_frame_count,
            codec=codec,
            duration_seconds=duration,
            unique_tracks_count=unique_tracks,
            total_detections_count=total_detections,
        )
