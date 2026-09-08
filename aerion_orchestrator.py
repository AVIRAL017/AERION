"""
AERION v1 — Orchestrator

Purpose
-------
Central high-level runtime orchestrator for the AERION v1 platform.
Coordinates perception adapters, change assessment, tracking, and deterministic
intelligence scoring to produce standard AERIONAnalysisResult contracts.

Architecture
------------
FROZEN ML (weights immutable, verified in Phase 0)
    ↓
EXISTING RUNTIME ADAPTERS (drone_detector, satellite_detector, damage_inference, border_pipeline)
    ↓
AERION NORMALIZATION (aerion_runtime_normalizer)
    ↓
AERION UNIFIED CONTRACTS (aerion_runtime_contracts)
    ↓
AERION ORCHESTRATOR (aerion_orchestrator)

Rules:
    - Never retrain, fine-tune, or modify frozen model weights.
    - Never duplicate existing perception, tracking, or scoring algorithms.
    - Avoid eager model loading to respect 6 GB VRAM constraint.
    - Keep RAG as an explicit advisory layer; never block core perception on external LLM calls.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from aerion_runtime_contracts import (
    AERIONAnalysisResult,
    Detection,
    TrackState,
    BorderAnalysis,
    DamageAnalysis,
    IntelligenceItem,
    SceneSummary,
)
from aerion_runtime_normalizer import (
    normalize_drone_result,
    normalize_satellite_result,
    normalize_damage_result,
    normalize_border_result,
    normalize_intelligence_result,
)


# Default geofencing polygon matching validated border benchmark
DEFAULT_BORDER_ZONE = [
    (900.0, 200.0),
    (1200.0, 200.0),
    (1200.0, 700.0),
    (900.0, 700.0),
]


class AERIONOrchestrator:
    """
    Primary runtime entry point for AERION v1 multi-modal mission operations.

    Parameters
    ----------
    mode:
        Operational mission profile: "disaster" or "border".
    device:
        Ultralytics/PyTorch device identifier (e.g. 0, "cuda:0", "cpu").
    drone_model:
        Drone model profile: "visdrone_only" (land/border) or "unified" (maritime/joint).
    confidence:
        Perception detection confidence threshold.
    iou:
        Non-maximum suppression IoU threshold.
    imgsz:
        Inference image resolution override (None preserves model validated defaults).
    terrain_type:
        Configured geographic operational environment ("arid", "mountain", "forest", "coastal").
    border_zone_polygon:
        Vertices defining the restricted geofencing boundary in pixel coordinates.
    """

    SUPPORTED_MODES = frozenset({"disaster", "border"})

    def __init__(
        self,
        mode: str = "disaster",
        device: Union[int, str] = 0,
        drone_model: str = "visdrone_only",
        confidence: float = 0.25,
        iou: float = 0.50,
        imgsz: Optional[int] = None,
        terrain_type: Optional[str] = "arid",
        border_zone_polygon: Optional[List[Tuple[float, float]]] = None,
    ) -> None:
        if mode not in self.SUPPORTED_MODES:
            raise ValueError(
                f"Unsupported mode '{mode}'. Supported modes: {sorted(self.SUPPORTED_MODES)}"
            )

        self.mode = mode
        self.device = device
        self.drone_model_name = drone_model
        self.confidence = confidence
        self.iou = iou
        self.imgsz = imgsz
        self.border_zone = border_zone_polygon or DEFAULT_BORDER_ZONE

        # Configure terrain metadata
        self.terrain_type = terrain_type
        self._terrain_context = None
        self._terrain_metadata = {}
        if terrain_type:
            try:
                from terrain_context import TerrainContext
                self._terrain_context = TerrainContext(terrain_type)
                self._terrain_metadata = self._terrain_context.get_context()
            except Exception as e:
                self._terrain_metadata = {
                    "terrain_type": terrain_type,
                    "error": str(e),
                }

        # Lazy-loaded adapter references to conserve GPU memory
        self._drone_detector = None
        self._satellite_detector = None
        self._border_pipeline = None

    # ============================================================
    # ADAPTER ACCESSORS (Lazy Loading)
    # ============================================================

    def get_drone_detector(self):
        """Retrieve or lazily instantiate the frozen DroneDetector."""
        if self._drone_detector is None:
            from drone_detector import create_drone_detector
            self._drone_detector = create_drone_detector(
                model_name=self.drone_model_name,
                device=self.device,
                confidence=self.confidence,
                iou=self.iou,
                imgsz=self.imgsz,
            )
        return self._drone_detector

    def get_satellite_detector(self):
        """Retrieve or lazily instantiate the frozen SatelliteDetector."""
        if self._satellite_detector is None:
            from satellite_detector import create_satellite_detector
            kwargs = {
                "device": self.device,
                "confidence": self.confidence,
                "iou": self.iou,
            }
            if self.imgsz is not None:
                kwargs["imgsz"] = self.imgsz
            self._satellite_detector = create_satellite_detector(**kwargs)
        return self._satellite_detector

    def get_border_pipeline(self):
        """Retrieve or lazily instantiate the composite BorderPipeline."""
        if self._border_pipeline is None:
            from border_pipeline import BorderPipeline
            drone_detector = self.get_drone_detector()
            self._border_pipeline = BorderPipeline(
                model_path=str(drone_detector.model_path),
                zone_polygon=self.border_zone,
            )
        return self._border_pipeline

    # ============================================================
    # LOW-LEVEL SUBSYSTEM METHODS
    # ============================================================

    def detect_drone(self, image: Union[str, Path, Any]):
        """Run perception inference through frozen drone YOLOv8s."""
        detector = self.get_drone_detector()
        return detector.detect(image)

    def detect_satellite(self, image: Union[str, Path, Any]):
        """Run OBB inference through frozen satellite YOLOv8n-OBB."""
        detector = self.get_satellite_detector()
        return detector.detect(image)

    def analyze_damage(
        self,
        before_path: Union[str, Path],
        after_path: Union[str, Path],
        threshold: float = 0.50,
    ) -> DamageAnalysis:
        """
        Execute bi-temporal damage assessment through frozen Siamese ResNet18.
        Lazily imports damage_inference to protect process startup.
        """
        from damage_inference import predict_damage
        raw_output = predict_damage(str(before_path), str(after_path))
        return normalize_damage_result(raw_output, threshold=threshold)

    def analyze_detections(
        self,
        detections: List[Dict[str, Any]],
        mode: Optional[str] = None,
    ) -> Tuple[List[IntelligenceItem], SceneSummary]:
        """
        Evaluate threat/priority scoring using the deterministic intelligence_engine.
        """
        from intelligence_engine import analyze_scene
        effective_mode = mode or self.mode
        raw_intelligence = analyze_scene(detections, mode=effective_mode)
        return normalize_intelligence_result(raw_intelligence)

    # ============================================================
    # UNIFIED HIGH-LEVEL OPERATIONS
    # ============================================================

    def process_image(
        self,
        image: Union[str, Path, Any],
        source_type: str = "drone",
        run_intelligence: bool = True,
        background_ssim: float = 0.50,
    ) -> AERIONAnalysisResult:
        """
        Process a single aerial or satellite frame through perception and scoring.

        Parameters
        ----------
        image:
            Path to image file or OpenCV/numpy image array.
        source_type:
            "drone" or "satellite".
        run_intelligence:
            Whether to execute deterministic scene prioritization.
        background_ssim:
            Reference background similarity score for SSIM prioritization.
        """
        analysis_id = str(uuid.uuid4())
        image_w: Optional[int] = None
        image_h: Optional[int] = None

        if source_type == "drone":
            raw_res = self.detect_drone(image)
            image_w = raw_res.image_width
            image_h = raw_res.image_height
            detections = normalize_drone_result(raw_res, source="drone")
        elif source_type == "satellite":
            raw_res = self.detect_satellite(image)
            image_w = raw_res.image_width
            image_h = raw_res.image_height
            detections = normalize_satellite_result(raw_res, source="satellite")
        else:
            raise ValueError(
                f"Unsupported source_type '{source_type}' for process_image. Use 'drone' or 'satellite'."
            )

        intel_items: List[IntelligenceItem] = []
        summary = SceneSummary()

        if run_intelligence and detections:
            # Format detections for intelligence_engine
            formatted = [
                {
                    "class": d.class_name,
                    "confidence": d.confidence,
                    "background_ssim": background_ssim,
                    "local_ssim": background_ssim,  # Static image default
                }
                for d in detections
            ]
            intel_items, summary = self.analyze_detections(formatted, mode=self.mode)

        overall_status = "detections_available" if detections else "no_detections"

        metadata = {
            "source_type": source_type,
            "drone_model": self.drone_model_name if source_type == "drone" else None,
            "configured_terrain": self._terrain_metadata,
        }

        return AERIONAnalysisResult(
            project="AERION",
            version="v1",
            analysis_id=analysis_id,
            mode=self.mode,
            source_type=source_type,
            image_width=image_w,
            image_height=image_h,
            frame_number=None,
            detections=detections,
            tracks=[],
            border_analysis=[],
            damage_analysis=None,
            intelligence=intel_items,
            summary=summary,
            overall_status=overall_status,
            metadata=metadata,
        )

    def process_change_pair(
        self,
        before_path: Union[str, Path],
        after_path: Union[str, Path],
        threshold: float = 0.50,
        run_intelligence: bool = True,
    ) -> AERIONAnalysisResult:
        """
        Process a bi-temporal disaster image pair through Siamese damage analysis.
        """
        analysis_id = str(uuid.uuid4())
        damage_analysis = self.analyze_damage(before_path, after_path, threshold=threshold)

        intel_items: List[IntelligenceItem] = []
        summary = SceneSummary()

        if run_intelligence:
            # Treat significant structural change as building_damage incident
            damage_conf = float(damage_analysis.probability_mean)
            formatted = [
                {
                    "class": "building_damage",
                    "confidence": max(0.50, min(1.0, damage_conf + 0.3)),
                    "background_ssim": 0.50,
                    "local_ssim": max(0.0, 0.50 * (1.0 - damage_analysis.damage_ratio)),
                }
            ]
            intel_items, summary = self.analyze_detections(formatted, mode="disaster")

        overall_status = "damage_analysis_available"

        metadata = {
            "source_type": "change_detection",
            "before_path": str(before_path),
            "after_path": str(after_path),
            "configured_terrain": self._terrain_metadata,
        }

        return AERIONAnalysisResult(
            project="AERION",
            version="v1",
            analysis_id=analysis_id,
            mode="disaster",
            source_type="change_detection",
            image_width=damage_analysis.after_width,
            image_height=damage_analysis.after_height,
            frame_number=None,
            detections=[],
            tracks=[],
            border_analysis=[],
            damage_analysis=damage_analysis,
            intelligence=intel_items,
            summary=summary,
            overall_status=overall_status,
            metadata=metadata,
        )

    def process_border_frame(
        self,
        frame: Any,
        frame_number: int = 0,
        imgsz: int = 1280,
    ) -> AERIONAnalysisResult:
        """
        Process a single streaming or video frame through the composite BorderPipeline.
        """
        analysis_id = str(uuid.uuid4())
        pipeline = self.get_border_pipeline()

        h, w = frame.shape[:2] if hasattr(frame, "shape") else (None, None)

        raw_results = pipeline.process_frame(
            frame=frame,
            frame_number=frame_number,
            imgsz=imgsz,
        )

        detections, tracks, border_analyses = normalize_border_result(
            border_output=raw_results,
            frame_number=frame_number,
            source="border",
        )

        # Count active alerts
        active_alerts = sum(1 for b in border_analyses if b.border_alert)

        if active_alerts > 0:
            overall_status = "border_alerts_available"
        elif tracks:
            overall_status = "detections_available"
        else:
            overall_status = "no_detections"

        # Tabulate priority summary
        critical_count = sum(1 for b in border_analyses if b.border_priority == "CRITICAL")
        high_count = sum(1 for b in border_analyses if b.border_priority == "HIGH")
        medium_count = sum(1 for b in border_analyses if b.border_priority == "MEDIUM")
        low_count = sum(1 for b in border_analyses if b.border_priority == "LOW")

        summary = SceneSummary(
            critical=critical_count,
            high=high_count,
            medium=medium_count,
            low=low_count,
        )

        metadata = {
            "source_type": "video",
            "frame_number": frame_number,
            "active_alerts": active_alerts,
            "configured_terrain": self._terrain_metadata,
        }

        return AERIONAnalysisResult(
            project="AERION",
            version="v1",
            analysis_id=analysis_id,
            mode="border",
            source_type="video",
            image_width=w,
            image_height=h,
            frame_number=frame_number,
            detections=detections,
            tracks=tracks,
            border_analysis=border_analyses,
            damage_analysis=None,
            intelligence=[],
            summary=summary,
            overall_status=overall_status,
            metadata=metadata,
        )

    # ============================================================
    # ADVISORY PROTOCOL / RAG LAYER
    # ============================================================

    def generate_advisory_report(
        self,
        detection: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Advisory report generation querying protocols and Mistral LLM if available.
        Perception remains 100% operational if LLM fails or is unconfigured.
        """
        from protocols import get_protocol

        mode = detection.get("mode", self.mode)
        obj_class = detection.get("object_class", "unknown")
        protocol = get_protocol(mode, obj_class)

        result: Dict[str, Any] = {
            "protocol": protocol,
            "ai_report": None,
            "ai_report_error": None,
        }

        try:
            from report_generator import generate_report
            report_input = {
                "mode": mode,
                "object_class": obj_class,
                "confidence": float(detection.get("confidence", 0.8)),
                "priority_score": float(detection.get("priority_score", 0.5)),
                "priority_bucket": str(detection.get("priority", "Medium")),
                "location": detection.get("location", "unspecified"),
                "change_detected": detection.get("change_detected", "unknown"),
            }
            result["ai_report"] = generate_report(report_input)
        except Exception as exc:
            result["ai_report"] = (
                "AI report unavailable. Refer to detected evidence and standard protocol."
            )
            result["ai_report_error"] = str(exc)

        return result
