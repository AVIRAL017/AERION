"""
AERION — Annotated Visual Evidence Service (Roadmap Step 15)
Renders deterministic, presentation-grade visual annotations onto aerial & satellite imagery:
- Consumes real AERION runtime contracts (AERIONAnalysisResult, Detection, BoundingBox, Point2D)
- Does NOT perform detection (presentation & evidence generation only)
- Drone bounding boxes with class name + confidence tags
- Satellite 4-corner Oriented Bounding Box (OBB) polygon rendering
- Restrained zero-detection indicator when detections are empty
- Strictly preserves source images (never overwrites original)
- Bounded image processing with memory safety limits
- Stores derived visual evidence artifact via LocalArtifactStorage
- Returns clean AnnotationResult with base64 preview and storage metadata
"""

from __future__ import annotations

import base64
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

from aerion_runtime_contracts import AERIONAnalysisResult, Detection, Point2D
from app.core.errors import ValidationError
from app.core.security_utils import sanitize_local_path
from app.services.storage_service import LocalArtifactStorage

logger = logging.getLogger("aerion.services.annotation")

# Maximum permitted image dimensions for annotation safety
MAX_ANNOTATION_WIDTH = 8192
MAX_ANNOTATION_HEIGHT = 8192
MAX_IMAGE_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

# Deterministic class color mapping (BGR format for OpenCV)
CLASS_PALETTE_BGR: Dict[str, Tuple[int, int, int]] = {
    # Drone classes
    "pedestrian": (56, 213, 245),      # Neon Cyan
    "person": (56, 213, 245),          # Neon Cyan
    "people": (56, 213, 245),          # Neon Cyan
    "bicycle": (76, 175, 80),          # Green
    "car": (245, 158, 11),             # Amber / Orange
    "van": (217, 119, 6),              # Darker Orange
    "truck": (239, 68, 68),            # Red
    "tricycle": (139, 92, 246),        # Purple
    "awning-tricycle": (167, 139, 250),# Light Purple
    "bus": (236, 72, 153),             # Pink
    "motor": (14, 165, 233),           # Sky Blue
    # Satellite classes (DOTA-v1.5)
    "plane": (245, 158, 11),           # Amber
    "baseball-diamond": (76, 175, 80), # Green
    "bridge": (156, 163, 175),         # Slate Gray
    "ground-track-field": (34, 197, 94),# Light Green
    "small-vehicle": (56, 213, 245),   # Cyan
    "large-vehicle": (239, 68, 68),    # Red
    "ship": (14, 165, 233),            # Blue
    "tennis-court": (168, 85, 247),    # Purple
    "basketball-court": (234, 88, 12), # Deep Orange
    "storage-tank": (202, 138, 4),     # Gold
    "soccer-ball-field": (22, 163, 74),# Green
    "roundabout": (219, 39, 119),      # Magenta
    "harbor": (2, 132, 199),           # Deep Blue
    "swimming-pool": (6, 182, 212),    # Aqua
    "helicopter": (225, 29, 72),       # Rose
    "container-crane": (107, 114, 128),# Gray
}

DEFAULT_BOX_COLOR: Tuple[int, int, int] = (56, 213, 245)  # Cyan


@dataclass
class AnnotationResult:
    """
    Immutable representation of an annotated visual evidence artifact.
    Contains storage metadata and base64 preview for zero-leakage API responses.
    """
    artifact_key: str
    sha256: str
    file_size_bytes: int
    mime_type: str
    image_width: int
    image_height: int
    detection_count: int
    annotated_base64: str
    is_zero_detection: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_key": self.artifact_key,
            "sha256": self.sha256,
            "file_size_bytes": self.file_size_bytes,
            "mime_type": self.mime_type,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "detection_count": self.detection_count,
            "is_zero_detection": self.is_zero_detection,
            "annotated_base64": self.annotated_base64,
        }


class AnnotationService:
    """
    Evidence presentation service for producing audited, annotated visual artifacts.
    Consumes real AERION runtime perception results without altering model behavior.
    """

    def __init__(self, storage: Optional[LocalArtifactStorage] = None):
        self.storage = storage or LocalArtifactStorage()

    def annotate_and_store(
        self,
        source_image_path: Union[str, Path],
        analysis_result: AERIONAnalysisResult,
        project_id: uuid.UUID,
    ) -> AnnotationResult:
        """
        Loads source image safely, renders detection overlays (or zero-detection banner),
        stores the derived visual evidence in LocalArtifactStorage, and generates a base64 preview.
        Strictly preserves the source image file bytes.
        """
        src_path = sanitize_local_path(str(source_image_path), field_name="source_image_path")
        
        # Guard source file size
        file_size = src_path.stat().st_size
        if file_size > MAX_IMAGE_FILE_SIZE:
            raise ValidationError(
                message=f"Image file exceeds maximum allowable size for annotation ({MAX_IMAGE_FILE_SIZE // (1024*1024)} MB).",
                details=[{"field": "source_image_path", "issue": "file_too_large", "provided": f"{file_size} bytes"}],
            )

        # Read image with OpenCV (BGR)
        img = cv2.imread(str(src_path), cv2.IMREAD_COLOR)
        if img is None:
            raise ValidationError(
                message=f"Failed to decode image data from file: {src_path.name}",
                details=[{"field": "source_image_path", "issue": "decode_failure", "provided": src_path.name}],
            )

        h, w = img.shape[:2]
        if w > MAX_ANNOTATION_WIDTH or h > MAX_ANNOTATION_HEIGHT:
            raise ValidationError(
                message=f"Image dimensions ({w}x{h}) exceed maximum permitted limits ({MAX_ANNOTATION_WIDTH}x{MAX_ANNOTATION_HEIGHT}).",
                details=[{"field": "source_image_path", "issue": "dimensions_exceeded", "provided": f"{w}x{h}"}],
            )

        # Create isolated canvas copy to guarantee source remains untouched
        canvas = img.copy()

        detections = analysis_result.detections or []
        is_zero_detection = (len(detections) == 0)

        # Scaling factors for dynamic, crisp fonts and line widths
        scale = max(w, h)
        line_thickness = max(2, int(scale / 500))
        font_scale = max(0.45, scale / 1600.0)
        font_thickness = max(1, int(scale / 900))

        if is_zero_detection:
            # Render honest, restrained zero-detection banner in bottom-left
            self._render_zero_detection_banner(canvas, w, h, font_scale, font_thickness)
        else:
            # Abbreviation mapping for compact high-density presentation
            abbrev_map = {
                "small_vehicle": "CAR",
                "large_vehicle": "TRUCK",
                "light_vehicle": "CAR",
                "heavy_vehicle": "TRUCK",
                "pedestrian": "PED",
                "person": "PED",
                "bicycle": "BIKE",
                "motorcycle": "MOTO",
            }
            # Render each verified detection
            for det in detections:
                color = CLASS_PALETTE_BGR.get(det.class_name.lower(), DEFAULT_BOX_COLOR)
                short_class = abbrev_map.get(det.class_name.lower(), det.class_name.upper())
                label_text = f"{short_class} • {det.confidence:.2f}"

                if det.obb_points and len(det.obb_points) == 4:
                    # Satellite / OBB 4-corner polygon rendering
                    self._render_obb(canvas, det.obb_points, label_text, color, line_thickness, font_scale, font_thickness)
                elif det.bbox:
                    # Drone / Standard horizontal bounding box
                    self._render_bbox(canvas, det.bbox, label_text, color, line_thickness, font_scale, font_thickness)

        # Save annotated image to isolated temporary file for storage pipeline ingestion
        temp_dir = Path(tempfile.mkdtemp(prefix="aerion_annot_"))
        temp_dest = temp_dir / f"{uuid.uuid4()}.jpg"
        try:
            cv2.imwrite(str(temp_dest), canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 92])

            # Store in LocalArtifactStorage under project_id / "annotated_image"
            storage_key, sha256_hex, stored_bytes = self.storage.store_file(
                source_path=temp_dest,
                asset_type="annotated_image",
                project_id=project_id,
                suffix=".jpg",
            )

            # Generate base64 representation for frontend preview without exposing filesystem
            _, encoded_buffer = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
            b64_str = base64.b64encode(encoded_buffer.tobytes()).decode("utf-8")

            return AnnotationResult(
                artifact_key=storage_key,
                sha256=sha256_hex,
                file_size_bytes=stored_bytes,
                mime_type="image/jpeg",
                image_width=w,
                image_height=h,
                detection_count=len(detections),
                annotated_base64=b64_str,
                is_zero_detection=is_zero_detection,
            )
        finally:
            if temp_dest.exists():
                temp_dest.unlink(missing_ok=True)
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _render_bbox(
        self,
        canvas: np.ndarray,
        bbox: Any,
        label: str,
        color: Tuple[int, int, int],
        thickness: int,
        font_scale: float,
        font_thickness: int,
    ) -> None:
        """Renders an axis-aligned bounding box and badge."""
        x1 = max(0, int(round(bbox.x1)))
        y1 = max(0, int(round(bbox.y1)))
        x2 = min(canvas.shape[1] - 1, int(round(bbox.x2)))
        y2 = min(canvas.shape[0] - 1, int(round(bbox.y2)))

        # Draw bounding rectangle
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness)

        # Draw label badge
        (text_w, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)
        badge_y1 = max(0, y1 - text_h - 8)
        badge_y2 = y1
        badge_x2 = min(canvas.shape[1], x1 + text_w + 8)

        # Background badge fill
        cv2.rectangle(canvas, (x1, badge_y1), (badge_x2, badge_y2), color, -1)
        # Foreground text (dark for high contrast against saturated badges)
        text_y = badge_y2 - 4
        cv2.putText(canvas, label, (x1 + 4, text_y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (7, 9, 12), font_thickness, cv2.LINE_AA)

    def _render_obb(
        self,
        canvas: np.ndarray,
        obb_points: List[Point2D],
        label: str,
        color: Tuple[int, int, int],
        thickness: int,
        font_scale: float,
        font_thickness: int,
    ) -> None:
        """Renders a 4-corner Oriented Bounding Box polygon and badge."""
        pts = np.array([[int(round(p.x)), int(round(p.y))] for p in obb_points], dtype=np.int32)
        cv2.polylines(canvas, [pts], isClosed=True, color=color, thickness=thickness, lineType=cv2.LINE_AA)

        # Anchor badge at first vertex
        top_pt = pts[0]
        tx, ty = int(top_pt[0]), int(top_pt[1])

        (text_w, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)
        badge_y1 = max(0, ty - text_h - 8)
        badge_y2 = ty
        badge_x2 = min(canvas.shape[1], tx + text_w + 8)

        cv2.rectangle(canvas, (tx, badge_y1), (badge_x2, badge_y2), color, -1)
        cv2.putText(canvas, label, (tx + 4, badge_y2 - 4), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (7, 9, 12), font_thickness, cv2.LINE_AA)

    def _render_zero_detection_banner(
        self,
        canvas: np.ndarray,
        w: int,
        h: int,
        font_scale: float,
        font_thickness: int,
    ) -> None:
        """Renders an honest, restrained 'NO DETECTIONS' indicator."""
        banner_text = "AERION VERIFIED: NO DETECTIONS IN SCENE"
        (text_w, text_h), baseline = cv2.getTextSize(banner_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale * 1.1, font_thickness)
        pad = 12
        bx1 = 16
        by2 = h - 16
        by1 = by2 - text_h - (pad * 2)
        bx2 = bx1 + text_w + (pad * 2)

        # Semi-transparent dark pill background
        overlay = canvas.copy()
        cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (18, 22, 28), -1)
        cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (56, 213, 245), max(1, int(font_thickness / 2)))
        cv2.addWeighted(overlay, 0.82, canvas, 0.18, 0, canvas)

        # Text in cyan / accent
        cv2.putText(canvas, banner_text, (bx1 + pad, by2 - pad), cv2.FONT_HERSHEY_SIMPLEX, font_scale * 1.1, (56, 213, 245), font_thickness, cv2.LINE_AA)

    def render_damage_overlay_and_store(
        self,
        after_image_path: Union[str, Path],
        before_image_path: Union[str, Path],
        damage_analysis: Any,
        project_id: uuid.UUID,
    ) -> AnnotationResult:
        """
        Renders an authoritative damage overlay highlighting verified building damage
        onto the post-disaster image and persists it as an evidence artifact.
        """
        src_path = sanitize_local_path(str(after_image_path))
        if not src_path.exists():
            raise ValidationError(
                message=f"Post-disaster image not found for damage annotation: {after_image_path}",
                details=[{"field": "after_image_path", "issue": "file_not_found"}],
            )

        # Load image via cv2
        img = cv2.imread(str(src_path), cv2.IMREAD_COLOR)
        if img is None:
            raise ValidationError(
                message="Post-disaster image could not be decoded for damage visualization.",
                details=[{"field": "after_image_path", "issue": "invalid_image_data"}],
            )

        h, w = img.shape[:2]
        canvas = img.copy()

        # Re-run Siamese predict_damage to extract high-resolution probability and binary mask
        from damage_inference import predict_damage
        try:
            _, _, prob_map, raw_mask = predict_damage(str(before_image_path), str(after_image_path))
        except Exception as exc:
            logger.warning(f"Failed to extract damage mask directly: {exc}")
            prob_map = None
            raw_mask = None

        is_zero_damage = True
        damage_percentage = 0.0

        if raw_mask is not None and prob_map is not None:
            damage_percentage = (float(raw_mask.sum()) / float(raw_mask.size)) * 100.0
            is_zero_damage = bool(raw_mask.sum() == 0)

            # Resize damage mask to original canvas dimensions
            mask_resized = cv2.resize(raw_mask.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST)
            prob_resized = cv2.resize(prob_map.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)

            if not is_zero_damage:
                # Create colored damage heatmap/highlight (bright crimson red BGR: 40, 40, 235)
                overlay = canvas.copy()
                damage_indices = mask_resized > 0
                overlay[damage_indices] = [40, 40, 235]  # Crimson Red

                # Alpha blend overlay over damaged regions
                cv2.addWeighted(overlay, 0.55, canvas, 0.45, 0, canvas)

                # Draw high-contrast contours around damaged zones
                contours, _ = cv2.findContours(mask_resized, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                scale = max(w, h)
                contour_thickness = max(1, int(scale / 800))
                cv2.drawContours(canvas, contours, -1, (0, 0, 255), contour_thickness, cv2.LINE_AA)

        # Render presentation badge with damage percentage
        scale = max(w, h)
        font_scale = max(0.45, scale / 1500.0)
        font_thickness = max(1, int(scale / 900))

        if is_zero_damage:
            badge_text = "AERION VERIFIED: NO STRUCTURAL DAMAGE DETECTED"
            badge_color = (56, 213, 245)  # Cyan
        else:
            badge_text = f"AERION DAMAGE ASSESSMENT: {damage_percentage:.2f}% STRUCTURAL DAMAGE"
            badge_color = (40, 40, 235)  # Crimson

        (text_w, text_h), baseline = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)
        pad = 12
        bx1 = 16
        by2 = h - 16
        by1 = by2 - text_h - (pad * 2)
        bx2 = bx1 + text_w + (pad * 2)

        overlay = canvas.copy()
        cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (18, 22, 28), -1)
        cv2.rectangle(overlay, (bx1, by1), (bx2, by2), badge_color, max(1, int(font_thickness / 2)))
        cv2.addWeighted(overlay, 0.85, canvas, 0.15, 0, canvas)
        cv2.putText(canvas, badge_text, (bx1 + pad, by2 - pad), cv2.FONT_HERSHEY_SIMPLEX, font_scale, badge_color, font_thickness, cv2.LINE_AA)

        # Save annotated image and store in LocalArtifactStorage
        temp_dir = Path(tempfile.mkdtemp(prefix="aerion_dmg_"))
        temp_dest = temp_dir / f"{uuid.uuid4()}.jpg"
        try:
            cv2.imwrite(str(temp_dest), canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 92])

            storage_key, sha256_hex, stored_bytes = self.storage.store_file(
                source_path=temp_dest,
                asset_type="damage_mask",
                project_id=project_id,
                suffix=".jpg",
            )

            _, encoded_buffer = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
            b64_str = base64.b64encode(encoded_buffer.tobytes()).decode("utf-8")

            return AnnotationResult(
                artifact_key=storage_key,
                sha256=sha256_hex,
                file_size_bytes=stored_bytes,
                mime_type="image/jpeg",
                image_width=w,
                image_height=h,
                detection_count=0 if is_zero_damage else int(mask_resized.sum() if 'mask_resized' in locals() else 1),
                annotated_base64=b64_str,
                is_zero_detection=is_zero_damage,
            )
        finally:
            if temp_dest.exists():
                temp_dest.unlink(missing_ok=True)
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
