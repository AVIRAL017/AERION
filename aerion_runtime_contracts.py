"""
AERION v1 — Unified Runtime Contracts

Purpose
-------
Provides standard, JSON-serializable dataclass contracts for all AERION v1
perception, tracking, damage assessment, and intelligence runtime outputs.

Design Rules:
    - Pure Python standard library dataclasses.
    - No third-party runtime dependencies.
    - Strictly JSON serializable: converts all numpy / torch types to native Python.
    - Validates invariants without silently altering upstream values.
    - Authoritative frozen ML results are preserved without fabrication.
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


def _to_native_scalar(val: Any) -> Any:
    """Recursively convert numpy scalars or other non-standard types to native Python."""
    if val is None:
        return None
    val_type = type(val).__name__
    if "int" in val_type:
        return int(val)
    if "float" in val_type:
        f = float(val)
        return 0.0 if (math.isnan(f) or math.isinf(f)) else f
    if "bool" in val_type:
        return bool(val)
    if isinstance(val, (list, tuple)):
        return [_to_native_scalar(item) for item in val]
    if isinstance(val, dict):
        return {str(k): _to_native_scalar(v) for k, v in val.items()}
    return val


# ================================================================
# 1. GEOMETRY CONTRACTS
# ================================================================

@dataclass
class Point2D:
    """2D Cartesian point in pixel coordinates."""
    x: float
    y: float

    def __post_init__(self) -> None:
        self.x = float(self.x)
        self.y = float(self.y)

    def to_dict(self) -> Dict[str, float]:
        return {
            "x": self.x,
            "y": self.y,
        }


@dataclass
class BoundingBox:
    """Axis-aligned 2D bounding box in pixel coordinates [x1, y1, x2, y2]."""
    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self) -> None:
        self.x1 = float(self.x1)
        self.y1 = float(self.y1)
        self.x2 = float(self.x2)
        self.y2 = float(self.y2)

        if self.x1 > self.x2 or self.y1 > self.y2:
            raise ValueError(
                f"Invalid BoundingBox dimensions: [{self.x1}, {self.y1}, {self.x2}, {self.y2}]. "
                f"Coordinates must satisfy x1 <= x2 and y1 <= y2."
            )

    def to_dict(self) -> Dict[str, float]:
        return {
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
        }


# ================================================================
# 2. PERCEPTION DETECTION CONTRACT
# ================================================================

@dataclass
class Detection:
    """
    Unified detection contract across Drone, Satellite, and Border subsystems.

    Preserves both standard horizontal bounding box (bbox) and
    four-corner Oriented Bounding Box (obb_points) when available.
    """
    source: str
    class_id: int
    class_name: str
    confidence: float
    bbox: Optional[BoundingBox] = None
    obb_points: Optional[List[Point2D]] = None
    track_id: Optional[int] = None
    frame_number: Optional[int] = None

    def __post_init__(self) -> None:
        self.source = str(self.source)
        self.class_id = int(self.class_id)
        self.class_name = str(self.class_name)
        self.confidence = float(self.confidence)

        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"Invalid confidence score {self.confidence}. Expected range [0.0, 1.0]."
            )
        if self.class_id < 0:
            raise ValueError(
                f"Invalid class_id {self.class_id}. Expected non-negative integer."
            )
        if self.bbox is None and self.obb_points is None:
            raise ValueError(
                "Detection must supply at least one geometric representation: 'bbox' or 'obb_points'."
            )
        if self.track_id is not None:
            self.track_id = int(self.track_id)
        if self.frame_number is not None:
            self.frame_number = int(self.frame_number)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "bbox": self.bbox.to_dict() if self.bbox else None,
            "obb_points": [p.to_dict() for p in self.obb_points] if self.obb_points else None,
            "track_id": self.track_id,
            "frame_number": self.frame_number,
        }


# ================================================================
# 3. DAMAGE ASSESSMENT CONTRACT
# ================================================================

@dataclass
class DamageAnalysis:
    """
    Structural damage detection results from the frozen Siamese ResNet18 model.

    Captures summary statistics and binary mask metrics without embedding
    massive multi-megabyte numpy arrays into the standard JSON response.
    """
    before_width: int
    before_height: int
    after_width: int
    after_height: int
    probability_min: float
    probability_max: float
    probability_mean: float
    threshold: float
    damage_pixels: int
    total_pixels: int
    damage_ratio: float
    damage_percentage: float
    probability_map_available: bool = True
    damage_mask_available: bool = True

    def __post_init__(self) -> None:
        self.before_width = int(self.before_width)
        self.before_height = int(self.before_height)
        self.after_width = int(self.after_width)
        self.after_height = int(self.after_height)
        self.probability_min = float(self.probability_min)
        self.probability_max = float(self.probability_max)
        self.probability_mean = float(self.probability_mean)
        self.threshold = float(self.threshold)
        self.damage_pixels = int(self.damage_pixels)
        self.total_pixels = int(self.total_pixels)
        self.damage_ratio = float(self.damage_ratio)
        self.damage_percentage = float(self.damage_percentage)

        if not (0.0 <= self.damage_ratio <= 1.0):
            raise ValueError(
                f"Invalid damage_ratio {self.damage_ratio}. Expected [0.0, 1.0]."
            )
        if not (0.0 <= self.damage_percentage <= 100.0):
            raise ValueError(
                f"Invalid damage_percentage {self.damage_percentage}. Expected [0.0, 100.0]."
            )
        if not (0.0 <= self.threshold <= 1.0):
            raise ValueError(
                f"Invalid threshold {self.threshold}. Expected [0.0, 1.0]."
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "before_width": self.before_width,
            "before_height": self.before_height,
            "after_width": self.after_width,
            "after_height": self.after_height,
            "probability_min": round(self.probability_min, 4),
            "probability_max": round(self.probability_max, 4),
            "probability_mean": round(self.probability_mean, 4),
            "threshold": round(self.threshold, 4),
            "damage_pixels": self.damage_pixels,
            "total_pixels": self.total_pixels,
            "damage_ratio": round(self.damage_ratio, 6),
            "damage_percentage": round(self.damage_percentage, 4),
            "probability_map_available": self.probability_map_available,
            "damage_mask_available": self.damage_mask_available,
        }


# ================================================================
# 4. TRACKING CONTRACT
# ================================================================

@dataclass
class TrackState:
    """
    Object tracking state enriched by BorderTracker over a temporal sliding window.
    """
    track_id: int
    confidence: float
    bbox: BoundingBox
    center: Point2D
    previous_center: Optional[Point2D]
    frames_seen: int
    movement_distance: float
    displacement: float
    direction: str
    persistence: float
    class_id: Optional[int] = None
    class_name: Optional[str] = None

    def __post_init__(self) -> None:
        self.track_id = int(self.track_id)
        self.confidence = float(self.confidence)
        self.frames_seen = int(self.frames_seen)
        self.movement_distance = float(self.movement_distance)
        self.displacement = float(self.displacement)
        self.direction = str(self.direction)
        self.persistence = float(self.persistence)

        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"Invalid track confidence {self.confidence}. Expected [0.0, 1.0]."
            )
        if not (0.0 <= self.persistence <= 1.0):
            raise ValueError(
                f"Invalid track persistence {self.persistence}. Expected [0.0, 1.0]."
            )
        if self.frames_seen < 0:
            raise ValueError(
                f"Invalid frames_seen {self.frames_seen}. Expected >= 0."
            )
        if self.class_id is not None:
            self.class_id = int(self.class_id)
        if self.class_name is not None:
            self.class_name = str(self.class_name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "track_id": self.track_id,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "bbox": self.bbox.to_dict(),
            "center": self.center.to_dict(),
            "previous_center": self.previous_center.to_dict() if self.previous_center else None,
            "frames_seen": self.frames_seen,
            "movement_distance": round(self.movement_distance, 2),
            "displacement": round(self.displacement, 2),
            "direction": self.direction,
            "persistence": round(self.persistence, 4),
        }


# ================================================================
# 5. BORDER ANALYSIS CONTRACT
# ================================================================

@dataclass
class BorderAnalysis:
    """
    High-level threat assessment output from BorderZoneAnalyzer,
    BorderIntelligence, and BorderEventFilter.
    """
    track_id: Optional[int] = None
    inside_restricted_zone: Optional[bool] = None
    distance_to_zone: Optional[float] = None
    previous_distance_to_zone: Optional[float] = None
    approach_score: Optional[float] = None
    direction_relation: Optional[str] = None
    direction_alignment: Optional[float] = None
    direction_score: Optional[float] = None
    zone_entry: Optional[bool] = None
    zone_exit: Optional[bool] = None
    zone_status: Optional[str] = None
    zone_dwell_frames: Optional[int] = None
    zone_dwell_score: Optional[float] = None
    border_activity_score: Optional[float] = None
    border_priority: Optional[str] = None
    movement_score: Optional[float] = None
    movement_inside_score: Optional[float] = None
    moving_away: Optional[bool] = None
    border_candidate: Optional[bool] = None
    border_alert: Optional[bool] = None
    alert_level: Optional[str] = None

    def __post_init__(self) -> None:
        if self.track_id is not None:
            self.track_id = int(self.track_id)
        if self.inside_restricted_zone is not None:
            self.inside_restricted_zone = bool(self.inside_restricted_zone)
        if self.distance_to_zone is not None:
            self.distance_to_zone = float(self.distance_to_zone)
        if self.previous_distance_to_zone is not None:
            self.previous_distance_to_zone = float(self.previous_distance_to_zone)
        if self.approach_score is not None:
            self.approach_score = float(self.approach_score)
        if self.direction_alignment is not None:
            self.direction_alignment = float(self.direction_alignment)
        if self.direction_score is not None:
            self.direction_score = float(self.direction_score)
        if self.zone_entry is not None:
            self.zone_entry = bool(self.zone_entry)
        if self.zone_exit is not None:
            self.zone_exit = bool(self.zone_exit)
        if self.zone_dwell_frames is not None:
            self.zone_dwell_frames = int(self.zone_dwell_frames)
        if self.zone_dwell_score is not None:
            self.zone_dwell_score = float(self.zone_dwell_score)
        if self.border_activity_score is not None:
            self.border_activity_score = float(self.border_activity_score)
        if self.movement_score is not None:
            self.movement_score = float(self.movement_score)
        if self.movement_inside_score is not None:
            self.movement_inside_score = float(self.movement_inside_score)
        if self.moving_away is not None:
            self.moving_away = bool(self.moving_away)
        if self.border_candidate is not None:
            self.border_candidate = bool(self.border_candidate)
        if self.border_alert is not None:
            self.border_alert = bool(self.border_alert)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "track_id": self.track_id,
            "inside_restricted_zone": self.inside_restricted_zone,
            "distance_to_zone": round(self.distance_to_zone, 2) if self.distance_to_zone is not None else None,
            "previous_distance_to_zone": round(self.previous_distance_to_zone, 2) if self.previous_distance_to_zone is not None else None,
            "approach_score": round(self.approach_score, 4) if self.approach_score is not None else None,
            "direction_relation": self.direction_relation,
            "direction_alignment": round(self.direction_alignment, 4) if self.direction_alignment is not None else None,
            "direction_score": round(self.direction_score, 4) if self.direction_score is not None else None,
            "zone_entry": self.zone_entry,
            "zone_exit": self.zone_exit,
            "zone_status": self.zone_status,
            "zone_dwell_frames": self.zone_dwell_frames,
            "zone_dwell_score": round(self.zone_dwell_score, 4) if self.zone_dwell_score is not None else None,
            "border_activity_score": round(self.border_activity_score, 4) if self.border_activity_score is not None else None,
            "border_priority": self.border_priority,
            "movement_score": round(self.movement_score, 4) if self.movement_score is not None else None,
            "movement_inside_score": round(self.movement_inside_score, 4) if self.movement_inside_score is not None else None,
            "moving_away": self.moving_away,
            "border_candidate": self.border_candidate,
            "border_alert": self.border_alert,
            "alert_level": self.alert_level,
        }


# ================================================================
# 6. INTELLIGENCE & SCENE SUMMARY CONTRACTS
# ================================================================

@dataclass
class IntelligenceItem:
    """
    Prioritized assessment for a detected object or change event,
    grounded by intelligence_engine and advisory protocols.
    """
    object_class: str
    confidence: float
    class_weight: Optional[float] = None
    change_score: Optional[float] = None
    priority_score: Optional[float] = None
    priority: Optional[str] = None
    mode: Optional[str] = None
    detection: Optional[Dict[str, Any]] = None
    protocol: Optional[str] = None
    ai_report: Optional[str] = None
    ai_report_error: Optional[str] = None

    def __post_init__(self) -> None:
        self.object_class = str(self.object_class)
        self.confidence = float(self.confidence)

        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"Invalid intelligence confidence {self.confidence}. Expected [0.0, 1.0]."
            )
        if self.class_weight is not None:
            self.class_weight = float(self.class_weight)
        if self.change_score is not None:
            self.change_score = float(self.change_score)
        if self.priority_score is not None:
            self.priority_score = float(self.priority_score)
            if not (0.0 <= self.priority_score <= 1.0):
                raise ValueError(
                    f"Invalid priority_score {self.priority_score}. Expected [0.0, 1.0]."
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_class": self.object_class,
            "confidence": round(self.confidence, 4),
            "class_weight": round(self.class_weight, 4) if self.class_weight is not None else None,
            "change_score": round(self.change_score, 4) if self.change_score is not None else None,
            "priority_score": round(self.priority_score, 4) if self.priority_score is not None else None,
            "priority": self.priority,
            "mode": self.mode,
            "detection": _to_native_scalar(self.detection),
            "protocol": self.protocol,
            "ai_report": self.ai_report,
            "ai_report_error": self.ai_report_error,
        }


@dataclass
class SceneSummary:
    """Incident count breakdown by priority tier."""
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0

    def __post_init__(self) -> None:
        self.critical = int(self.critical)
        self.high = int(self.high)
        self.medium = int(self.medium)
        self.low = int(self.low)

    def to_dict(self) -> Dict[str, int]:
        return {
            "critical": self.critical,
            "high": self.high,
            "medium": self.medium,
            "low": self.low,
        }


# ================================================================
# 7. PRIMARY PUBLIC RUNTIME CONTRACT
# ================================================================

@dataclass
class AERIONAnalysisResult:
    """
    Top-level unified public runtime result across all AERION operational modes.
    Guaranteed to serialize cleanly to standard JSON.
    """
    project: str = "AERION"
    version: str = "v1"
    analysis_id: Optional[str] = None
    mode: str = "disaster"
    source_type: str = "image"
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    frame_number: Optional[int] = None

    detections: List[Detection] = field(default_factory=list)
    tracks: List[TrackState] = field(default_factory=list)
    border_analysis: List[BorderAnalysis] = field(default_factory=list)
    damage_analysis: Optional[DamageAnalysis] = None
    intelligence: List[IntelligenceItem] = field(default_factory=list)
    summary: SceneSummary = field(default_factory=SceneSummary)
    overall_status: str = "analysis_complete"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.analysis_id is None:
            self.analysis_id = str(uuid.uuid4())
        if self.mode not in {"disaster", "border"}:
            raise ValueError(
                f"Invalid operational mode '{self.mode}'. Supported modes are 'disaster' and 'border'."
            )
        if self.image_width is not None:
            self.image_width = int(self.image_width)
        if self.image_height is not None:
            self.image_height = int(self.image_height)
        if self.frame_number is not None:
            self.frame_number = int(self.frame_number)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project": self.project,
            "version": self.version,
            "analysis_id": self.analysis_id,
            "mode": self.mode,
            "source_type": self.source_type,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "frame_number": self.frame_number,
            "detections": [d.to_dict() for d in self.detections],
            "tracks": [t.to_dict() for t in self.tracks],
            "border_analysis": [b.to_dict() for b in self.border_analysis],
            "damage_analysis": self.damage_analysis.to_dict() if self.damage_analysis else None,
            "intelligence": [i.to_dict() for i in self.intelligence],
            "summary": self.summary.to_dict(),
            "overall_status": self.overall_status,
            "metadata": _to_native_scalar(self.metadata),
        }

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize result to a strict JSON formatted string."""
        return json.dumps(self.to_dict(), indent=indent)
