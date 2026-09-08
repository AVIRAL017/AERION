"""
AERION — Evidence Builder (Phase 3C)
Transforms frozen runtime outputs (AERIONAnalysisResult, Detection, TrackState, DamageAnalysis)
into immutable EvidenceRecord instances with strict epistemological modality and provenance.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from aerion_runtime_contracts import (
    AERIONAnalysisResult,
    Detection as RuntimeDetection,
    TrackState as RuntimeTrack,
    DamageAnalysis as RuntimeDamage,
    BorderAnalysis as RuntimeBorder,
)
from app.schemas.evidence import (
    EvidenceRecord,
    EvidenceSourceType,
    Modality,
    PixelBoundingBox,
    PixelPoint,
    TemporalMode,
    VerificationState,
    utcnow,
)


class EvidenceBuilder:
    """
    Constructs cryptographically auditable EvidenceRecord items from runtime perception results.
    """

    @staticmethod
    def from_runtime_detection(
        detection: RuntimeDetection,
        temporal_mode: TemporalMode = TemporalMode.STATIC_IMAGE,
        asset_timestamp_utc: Optional[datetime] = None,
        source_type: Optional[EvidenceSourceType] = None,
    ) -> EvidenceRecord:
        """Transforms a raw runtime object detection into an EvidenceRecord."""
        if source_type is None:
            if detection.source == "visdrone_only":
                source_type = EvidenceSourceType.FROZEN_MODEL_VISDRONE_YOLO
            elif detection.source == "unified":
                source_type = EvidenceSourceType.FROZEN_MODEL_UNIFIED_DRONE_YOLO
            elif detection.source == "satellite_detector":
                source_type = EvidenceSourceType.FROZEN_MODEL_DOTA_OBB_YOLO
            else:
                source_type = EvidenceSourceType.FROZEN_MODEL_VISDRONE_YOLO

        # Pixel bbox
        pixel_bbox = None
        if detection.bbox is not None:
            pixel_bbox = PixelBoundingBox(
                x_min=detection.bbox.x1,
                y_min=detection.bbox.y1,
                x_max=detection.bbox.x2,
                y_max=detection.bbox.y2,
                confidence=detection.confidence,
                class_name=detection.class_name,
            )

        # Pixel polygon for OBB
        pixel_poly = None
        if detection.obb_points:
            pixel_poly = [PixelPoint(x=p.x, y=p.y) for p in detection.obb_points]

        return EvidenceRecord(
            evidence_id=str(uuid.uuid4()),
            parent_evidence_ids=[],
            source_type=source_type,
            created_at_utc=utcnow(),
            asset_timestamp_utc=asset_timestamp_utc,
            temporal_mode=temporal_mode,
            crs=None,  # Raw detection is pixel space only unless georeferenced
            geo_location=None,
            geo_footprint=None,
            pixel_bbox=pixel_bbox,
            pixel_polygon=pixel_poly,
            confidence=float(detection.confidence),
            verification_state=VerificationState.CALCULATED,
            modality=Modality.OBSERVED,
            sensor_metadata={
                "class_id": detection.class_id,
                "class_name": detection.class_name,
                "source_pipeline": detection.source,
                "track_id": detection.track_id,
                "frame_number": detection.frame_number,
            },
        )

    @staticmethod
    def from_runtime_damage(
        damage: RuntimeDamage,
        temporal_mode: TemporalMode = TemporalMode.STATIC_IMAGE,
        asset_timestamp_utc: Optional[datetime] = None,
    ) -> EvidenceRecord:
        """Transforms runtime Siamese damage assessment into an EvidenceRecord."""
        return EvidenceRecord(
            evidence_id=str(uuid.uuid4()),
            parent_evidence_ids=[],
            source_type=EvidenceSourceType.FROZEN_MODEL_SIAMESE_DAMAGE,
            created_at_utc=utcnow(),
            asset_timestamp_utc=asset_timestamp_utc,
            temporal_mode=temporal_mode,
            crs=None,
            geo_location=None,
            geo_footprint=None,
            pixel_bbox=None,
            pixel_polygon=None,
            confidence=float(damage.probability_mean),
            verification_state=VerificationState.CALCULATED,
            modality=Modality.OBSERVED,
            sensor_metadata={
                "threshold": damage.threshold,
                "damage_pixels": damage.damage_pixels,
                "total_pixels": damage.total_pixels,
                "damage_ratio": damage.damage_ratio,
                "damage_percentage": damage.damage_percentage,
                "probability_mean": damage.probability_mean,
            },
        )

    @staticmethod
    def from_external_weather(
        weather_data: Dict[str, Any],
        temporal_mode: TemporalMode,
        observation_timestamp_utc: datetime,
    ) -> EvidenceRecord:
        """Creates an EvidenceRecord for external meteorological feeds."""
        return EvidenceRecord(
            evidence_id=str(uuid.uuid4()),
            parent_evidence_ids=[],
            source_type=EvidenceSourceType.WEATHER_API,
            created_at_utc=utcnow(),
            asset_timestamp_utc=observation_timestamp_utc,
            temporal_mode=temporal_mode,
            confidence=1.0,
            verification_state=VerificationState.GROUND_CONFIRMED,
            modality=Modality.EXTERNALLY_PROVIDED,
            sensor_metadata=weather_data,
        )
