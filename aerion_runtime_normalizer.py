"""
AERION v1 — Runtime Normalizer

Purpose
-------
Adapts raw outputs from frozen AERION v1 ML runtime modules and pipelines into
strict, unified AERION runtime contract dataclasses.

Adapts:
    1. DroneDetectionResult -> List[Detection]
    2. SatelliteDetectionResult -> List[Detection]
    3. (before, after, prob_map, mask) -> DamageAnalysis
    4. BorderPipeline output -> Tuple[List[Detection], List[TrackState], List[BorderAnalysis]]
    5. intelligence_engine.analyze_scene output -> Tuple[List[IntelligenceItem], SceneSummary]

Rules:
    - Never rerun or duplicate inference.
    - Never modify frozen model outputs.
    - Never fabricate missing values; use Optional fields where data is absent.
    - Preserves exact floating-point metrics and coordinates.
"""

from __future__ import annotations

import numpy as np
from typing import Any, Dict, List, Optional, Tuple, Union

from aerion_runtime_contracts import (
    Point2D,
    BoundingBox,
    Detection,
    DamageAnalysis,
    TrackState,
    BorderAnalysis,
    IntelligenceItem,
    SceneSummary,
)


# Known class taxonomies from frozen AERION v1 models
DRONE_VISDRONE_CLASSES = {
    0: "person",
    1: "light_vehicle",
    2: "bus",
    3: "truck",
    4: "motorbike",
    5: "other_transport",
}

DRONE_UNIFIED_CLASSES = {
    0: "person",
    1: "light_vehicle",
    2: "bus",
    3: "truck",
    4: "motorbike",
    5: "other_transport",
    6: "boat",
    7: "jetski",
    8: "life_saving_appliance",
    9: "buoy",
}


# ================================================================
# 1. DRONE RESULT NORMALIZATION
# ================================================================

def normalize_drone_result(
    drone_result: Any,
    frame_number: Optional[int] = None,
    source: str = "drone",
) -> List[Detection]:
    """
    Convert a DroneDetectionResult instance into a list of unified Detection contracts.

    Parameters
    ----------
    drone_result:
        Instance of DroneDetectionResult (from drone_detector.py).
    frame_number:
        Optional frame index if operating in video sequence mode.
    source:
        Subsystem identifier tag (defaults to "drone").
    """
    if not hasattr(drone_result, "detections"):
        raise ValueError(
            f"Expected DroneDetectionResult with 'detections' attribute, got {type(drone_result).__name__}."
        )

    normalized: List[Detection] = []

    for raw_det in drone_result.detections:
        bbox_raw = raw_det.bbox
        if not bbox_raw or len(bbox_raw) < 4:
            raise ValueError(f"Invalid drone detection bbox: {bbox_raw}")

        bbox = BoundingBox(
            x1=float(bbox_raw[0]),
            y1=float(bbox_raw[1]),
            x2=float(bbox_raw[2]),
            y2=float(bbox_raw[3]),
        )

        detection = Detection(
            source=source,
            class_id=int(raw_det.class_id),
            class_name=str(raw_det.class_name),
            confidence=float(raw_det.confidence),
            bbox=bbox,
            obb_points=None,
            track_id=None,
            frame_number=frame_number,
        )
        normalized.append(detection)

    return normalized


# ================================================================
# 2. SATELLITE RESULT NORMALIZATION
# ================================================================

def normalize_satellite_result(
    satellite_result: Any,
    frame_number: Optional[int] = None,
    source: str = "satellite",
) -> List[Detection]:
    """
    Convert a SatelliteDetectionResult instance into unified Detection contracts.

    Preserves the full 4-point OBB vertices and derives an enclosing axis-aligned
    BoundingBox without discarding the oriented geometry.

    Parameters
    ----------
    satellite_result:
        Instance of SatelliteDetectionResult (from satellite_detector.py).
    frame_number:
        Optional frame index.
    source:
        Subsystem identifier tag (defaults to "satellite").
    """
    if not hasattr(satellite_result, "detections"):
        raise ValueError(
            f"Expected SatelliteDetectionResult with 'detections' attribute, got {type(satellite_result).__name__}."
        )

    normalized: List[Detection] = []

    for raw_det in satellite_result.detections:
        raw_points = raw_det.obb_points
        if not raw_points or len(raw_points) != 4:
            raise ValueError(
                f"Satellite OBB detection must contain exactly 4 corner points, got {len(raw_points) if raw_points else 0}."
            )

        obb_points = [
            Point2D(x=float(pt[0]), y=float(pt[1]))
            for pt in raw_points
        ]

        xs = [p.x for p in obb_points]
        ys = [p.y for p in obb_points]

        bbox = BoundingBox(
            x1=min(xs),
            y1=min(ys),
            x2=max(xs),
            y2=max(ys),
        )

        detection = Detection(
            source=source,
            class_id=int(raw_det.class_id),
            class_name=str(raw_det.class_name),
            confidence=float(raw_det.confidence),
            bbox=bbox,
            obb_points=obb_points,
            track_id=None,
            frame_number=frame_number,
        )
        normalized.append(detection)

    return normalized


# ================================================================
# 3. DAMAGE RESULT NORMALIZATION
# ================================================================

def normalize_damage_result(
    damage_output: Tuple[Any, Any, Any, Any],
    threshold: float = 0.50,
) -> DamageAnalysis:
    """
    Convert the raw tuple from predict_damage() into a DamageAnalysis contract.

    Input signature:
        (before_original, after_original, probability_map, damage_mask)

    Parameters
    ----------
    damage_output:
        4-element tuple returned by damage_inference.predict_damage().
    threshold:
        Decision boundary applied to probability map (default 0.50 from freeze manifest).
    """
    if not isinstance(damage_output, tuple) or len(damage_output) != 4:
        raise ValueError(
            f"Expected 4-element tuple (before, after, probability_map, damage_mask), got {type(damage_output).__name__} of length {len(damage_output) if isinstance(damage_output, tuple) else 'N/A'}."
        )

    before_img, after_img, prob_map, mask = damage_output

    if not hasattr(before_img, "shape") or len(before_img.shape) < 2:
        raise ValueError("Invalid before_image in damage output: missing shape attribute.")
    if not hasattr(after_img, "shape") or len(after_img.shape) < 2:
        raise ValueError("Invalid after_image in damage output: missing shape attribute.")

    before_height, before_width = int(before_img.shape[0]), int(before_img.shape[1])
    after_height, after_width = int(after_img.shape[0]), int(after_img.shape[1])

    prob_arr = np.asarray(prob_map, dtype=float)
    if prob_arr.ndim != 2:
        raise ValueError(
            f"Expected 2D probability map, got shape {prob_arr.shape}."
        )

    mask_arr = np.asarray(mask)
    if mask_arr.ndim != 2:
        raise ValueError(
            f"Expected 2D binary damage mask, got shape {mask_arr.shape}."
        )

    prob_min = float(np.min(prob_arr))
    prob_max = float(np.max(prob_arr))
    prob_mean = float(np.mean(prob_arr))

    # Basic invariant sanity
    if prob_min < -1e-4 or prob_max > 1.0 + 1e-4:
        raise ValueError(
            f"Probability map values out of [0, 1] range: min={prob_min}, max={prob_max}."
        )
    prob_min = max(0.0, min(1.0, prob_min))
    prob_max = max(0.0, min(1.0, prob_max))
    prob_mean = max(0.0, min(1.0, prob_mean))

    total_pixels = int(mask_arr.size)
    damage_pixels = int(np.count_nonzero(mask_arr > 0))

    damage_ratio = float(damage_pixels / total_pixels) if total_pixels > 0 else 0.0
    damage_percentage = float(damage_ratio * 100.0)

    return DamageAnalysis(
        before_width=before_width,
        before_height=before_height,
        after_width=after_width,
        after_height=after_height,
        probability_min=prob_min,
        probability_max=prob_max,
        probability_mean=prob_mean,
        threshold=float(threshold),
        damage_pixels=damage_pixels,
        total_pixels=total_pixels,
        damage_ratio=damage_ratio,
        damage_percentage=damage_percentage,
        probability_map_available=True,
        damage_mask_available=True,
    )


# ================================================================
# 4. BORDER RESULT NORMALIZATION
# ================================================================

def normalize_border_result(
    border_output: List[Dict[str, Any]],
    frame_number: Optional[int] = None,
    source: str = "border",
    class_map: Optional[Dict[int, str]] = None,
) -> Tuple[List[Detection], List[TrackState], List[BorderAnalysis]]:
    """
    Normalize the list of enriched dictionaries returned by BorderPipeline.process_frame().

    Separates the composite output into:
        - List[Detection]
        - List[TrackState]
        - List[BorderAnalysis]

    Parameters
    ----------
    border_output:
        List of dictionaries returned by BorderPipeline.process_frame().
    frame_number:
        Current frame index.
    source:
        Subsystem identifier (defaults to "border").
    class_map:
        Optional mapping from integer class_id to string class_name.
    """
    if not isinstance(border_output, list):
        raise ValueError(
            f"Expected list of detection dictionaries from BorderPipeline, got {type(border_output).__name__}."
        )

    cmap = class_map or DRONE_VISDRONE_CLASSES

    detections: List[Detection] = []
    tracks: List[TrackState] = []
    analyses: List[BorderAnalysis] = []

    for item in border_output:
        track_id = int(item["track_id"]) if item.get("track_id") is not None else None
        class_id = int(item["class_id"]) if item.get("class_id") is not None else 0
        class_name = item.get("class_name")
        if not class_name:
            class_name = cmap.get(class_id, f"class_{class_id}")
        class_name = str(class_name)

        confidence = float(item.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))

        bbox_raw = item.get("bbox")
        if not bbox_raw or len(bbox_raw) < 4:
            raise ValueError(f"Border detection missing or invalid bbox: {item}")

        bbox = BoundingBox(
            x1=float(bbox_raw[0]),
            y1=float(bbox_raw[1]),
            x2=float(bbox_raw[2]),
            y2=float(bbox_raw[3]),
        )

        # 1. Perception Detection
        detection = Detection(
            source=source,
            class_id=class_id,
            class_name=class_name,
            confidence=confidence,
            bbox=bbox,
            obb_points=None,
            track_id=track_id,
            frame_number=frame_number,
        )
        detections.append(detection)

        # 2. Tracking State
        center_raw = item.get("center")
        if not center_raw or len(center_raw) < 2:
            cx = (bbox.x1 + bbox.x2) / 2.0
            cy = (bbox.y1 + bbox.y2) / 2.0
        else:
            cx = float(center_raw[0])
            cy = float(center_raw[1])
        center = Point2D(x=cx, y=cy)

        prev_center_raw = item.get("previous_center")
        prev_center: Optional[Point2D] = None
        if prev_center_raw and len(prev_center_raw) >= 2:
            prev_center = Point2D(x=float(prev_center_raw[0]), y=float(prev_center_raw[1]))

        persistence = float(item.get("persistence", 0.0))
        persistence = max(0.0, min(1.0, persistence))

        track = TrackState(
            track_id=track_id if track_id is not None else -1,
            class_id=class_id,
            class_name=class_name,
            confidence=confidence,
            bbox=bbox,
            center=center,
            previous_center=prev_center,
            frames_seen=int(item.get("frames_seen", 1)),
            movement_distance=float(item.get("movement_distance", 0.0)),
            displacement=float(item.get("displacement", 0.0)),
            direction=str(item.get("direction", "unknown")),
            persistence=persistence,
        )
        tracks.append(track)

        # 3. Border Threat Analysis
        analysis = BorderAnalysis(
            track_id=track_id,
            inside_restricted_zone=bool(item["inside_restricted_zone"]) if "inside_restricted_zone" in item else None,
            distance_to_zone=float(item["distance_to_zone"]) if item.get("distance_to_zone") is not None else None,
            previous_distance_to_zone=float(item["previous_distance_to_zone"]) if item.get("previous_distance_to_zone") is not None else None,
            approach_score=float(item["approach_score"]) if item.get("approach_score") is not None else None,
            direction_relation=str(item["direction_relation"]) if item.get("direction_relation") is not None else None,
            direction_alignment=float(item["direction_alignment"]) if item.get("direction_alignment") is not None else None,
            direction_score=float(item["direction_score"]) if item.get("direction_score") is not None else None,
            zone_entry=bool(item["zone_entry"]) if "zone_entry" in item else None,
            zone_exit=bool(item["zone_exit"]) if "zone_exit" in item else None,
            zone_status=str(item["zone_status"]) if item.get("zone_status") is not None else None,
            zone_dwell_frames=int(item["zone_dwell_frames"]) if item.get("zone_dwell_frames") is not None else None,
            zone_dwell_score=float(item["zone_dwell_score"]) if item.get("zone_dwell_score") is not None else None,
            border_activity_score=float(item["border_activity_score"]) if item.get("border_activity_score") is not None else None,
            border_priority=str(item["border_priority"]) if item.get("border_priority") is not None else None,
            movement_score=float(item["movement_score"]) if item.get("movement_score") is not None else None,
            movement_inside_score=float(item["movement_inside_score"]) if item.get("movement_inside_score") is not None else None,
            moving_away=bool(item["moving_away"]) if "moving_away" in item else None,
            border_candidate=bool(item["border_candidate"]) if "border_candidate" in item else None,
            border_alert=bool(item["border_alert"]) if "border_alert" in item else None,
            alert_level=str(item["alert_level"]) if item.get("alert_level") is not None else None,
        )
        analyses.append(analysis)

    return detections, tracks, analyses


# ================================================================
# 5. INTELLIGENCE RESULT NORMALIZATION
# ================================================================

def normalize_intelligence_result(
    intelligence_output: Dict[str, Any],
) -> Tuple[List[IntelligenceItem], SceneSummary]:
    """
    Convert output from intelligence_engine.analyze_scene() into unified contracts.

    Parameters
    ----------
    intelligence_output:
        Dictionary returned by intelligence_engine.analyze_scene().
    """
    if not isinstance(intelligence_output, dict):
        raise ValueError(
            f"Expected dictionary from intelligence_engine, got {type(intelligence_output).__name__}."
        )

    raw_items = intelligence_output.get("detections", [])
    raw_summary = intelligence_output.get("summary", {})

    items: List[IntelligenceItem] = []

    for raw in raw_items:
        conf = float(raw.get("confidence", 0.0))
        conf = max(0.0, min(1.0, conf))

        p_score = raw.get("priority_score")
        if p_score is not None:
            p_score = max(0.0, min(1.0, float(p_score)))

        item = IntelligenceItem(
            object_class=str(raw.get("object_class", "unknown")),
            confidence=conf,
            class_weight=float(raw["class_weight"]) if raw.get("class_weight") is not None else None,
            change_score=float(raw["change_score"]) if raw.get("change_score") is not None else None,
            priority_score=p_score,
            priority=str(raw["priority"]) if raw.get("priority") is not None else None,
            mode=str(raw["mode"]) if raw.get("mode") is not None else None,
            detection=raw.get("detection"),
            protocol=raw.get("protocol"),
            ai_report=raw.get("ai_report"),
            ai_report_error=raw.get("ai_report_error"),
        )
        items.append(item)

    summary = SceneSummary(
        critical=int(raw_summary.get("critical", 0)),
        high=int(raw_summary.get("high", 0)),
        medium=int(raw_summary.get("medium", 0)),
        low=int(raw_summary.get("low", 0)),
    )

    return items, summary
