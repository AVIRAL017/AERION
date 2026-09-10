"""
AERION — Evidence Layer Models & Contracts (Phase 3C)
Implements immutable EvidenceRecord, provenance tracking, and coordinate invariants
strictly adhering to AERION_SITUATION_CONTRACT.md and AERION_OPERATIONAL_INTELLIGENCE.md.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Modality(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    EXTERNALLY_PROVIDED = "EXTERNALLY_PROVIDED"
    ESTIMATED = "ESTIMATED"
    UNAVAILABLE = "UNAVAILABLE"


class EvidenceSourceType(str, Enum):
    FROZEN_MODEL_VISDRONE_YOLO = "FROZEN_MODEL_VISDRONE_YOLO"
    FROZEN_MODEL_UNIFIED_DRONE_YOLO = "FROZEN_MODEL_UNIFIED_DRONE_YOLO"
    FROZEN_MODEL_DOTA_OBB_YOLO = "FROZEN_MODEL_DOTA_OBB_YOLO"
    FROZEN_MODEL_SIAMESE_DAMAGE = "FROZEN_MODEL_SIAMESE_DAMAGE"
    DRONE_TELEMETRY = "DRONE_TELEMETRY"
    SATELLITE_METADATA = "SATELLITE_METADATA"
    EXIF_GEOTAG = "EXIF_GEOTAG"
    WEATHER_API = "WEATHER_API"
    ROUTING_ENGINE = "ROUTING_ENGINE"
    SHELTER_REGISTRY = "SHELTER_REGISTRY"
    ELEVATION_API = "ELEVATION_API"
    MAP_TILE_PROVIDER = "MAP_TILE_PROVIDER"
    OPERATOR_INPUT = "OPERATOR_INPUT"
    GEOSPATIAL_REGISTRY = "GEOSPATIAL_REGISTRY"
    HISTORICAL_HAZARD_INVENTORY = "HISTORICAL_HAZARD_INVENTORY"


class VerificationState(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    CALCULATED = "CALCULATED"
    CORROBORATED = "CORROBORATED"
    GROUND_CONFIRMED = "GROUND_CONFIRMED"
    REJECTED = "REJECTED"


class OperationMode(str, Enum):
    BORDER_SECURITY = "BORDER_SECURITY"
    DISASTER_RESPONSE = "DISASTER_RESPONSE"


class TemporalMode(str, Enum):
    LIVE_STREAM = "LIVE_STREAM"
    RECORDED_FOOTAGE = "RECORDED_FOOTAGE"
    STATIC_IMAGE = "STATIC_IMAGE"
    TIME_SERIES = "TIME_SERIES"


class ThreatLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class GeoPoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    latitude: float = Field(ge=-90.0, le=90.0, description="WGS-84 decimal degrees latitude")
    longitude: float = Field(ge=-180.0, le=180.0, description="WGS-84 decimal degrees longitude")
    altitude_m: Optional[float] = Field(default=None, description="Altitude above MSL in meters")


class GeoPolygon(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    type: str = Field(default="Polygon", description="GeoJSON polygon marker")
    coordinates: List[List[List[float]]] = Field(description="Array of linear ring coordinate arrays [[lon, lat], ...]")


class PixelPoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    x: float = Field(description="Pixel X coordinate [0.0, width]")
    y: float = Field(description="Pixel Y coordinate [0.0, height]")


class PixelBoundingBox(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    confidence: float = Field(ge=0.0, le=1.0)
    class_name: str


class EvidenceRecord(BaseModel):
    """
    Atomic, immutable evidence unit produced by neural models, sensor telemetry,
    or external data providers. Enforces cryptographic provenance.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="UUID v4 identifying this evidence record")
    parent_evidence_ids: List[str] = Field(default_factory=list, description="IDs of ancestor evidence records")
    source_type: EvidenceSourceType = Field(description="Originating source system or model")
    created_at_utc: datetime = Field(default_factory=utcnow, description="UTC timestamp when evidence was created")
    asset_timestamp_utc: Optional[datetime] = Field(default=None, description="Capture timestamp for recorded media")
    temporal_mode: TemporalMode = Field(description="Temporal characteristic of the source stream")

    # Coordinate separation: strictly decouple pixel space from EPSG:4326 geospatial space
    crs: Optional[str] = Field(default=None, description="CRS (e.g. 'EPSG:4326'). None if unreferenced/pixel-only")
    geo_location: Optional[GeoPoint] = Field(default=None, description="Geospatial anchor if verified")
    geo_footprint: Optional[GeoPolygon] = Field(default=None, description="Geospatial boundary if calibrated")
    pixel_bbox: Optional[PixelBoundingBox] = Field(default=None, description="Bounding box in frame pixel space")
    pixel_polygon: Optional[List[PixelPoint]] = Field(default=None, description="OBB or segmentation mask in pixel space")

    # Provenance & Quality
    raw_payload_uri: Optional[str] = Field(default=None, description="URI of raw source asset or model output")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score from model or provider")
    verification_state: VerificationState = Field(default=VerificationState.UNVERIFIED)
    modality: Modality = Field(description="Epistemological derivation modality")
    sensor_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary")
