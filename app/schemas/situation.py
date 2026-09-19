"""
AERION — Situation State, Event, and Report Schemas (Phase 3C)
Defines SituationState, SituationEvent, SectorVulnerabilitySummary,
and Structured Operational Intelligence Reports.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from enum import Enum

from app.schemas.evidence import (
    GeoPoint,
    GeoPolygon,
    Modality,
    OperationMode,
    TemporalMode,
    ThreatLevel,
    utcnow,
)


class DisasterType(str, Enum):
    EARTHQUAKE = "EARTHQUAKE"
    FLOOD = "FLOOD"
    WILDFIRE = "WILDFIRE"
    CYCLONE = "CYCLONE"
    LANDSLIDE = "LANDSLIDE"
    INDUSTRIAL_ACCIDENT = "INDUSTRIAL_ACCIDENT"
    UNKNOWN = "UNKNOWN"


class RouteType(str, Enum):
    FASTEST_FEASIBLE = "FASTEST_FEASIBLE"
    SAFEST_FEASIBLE = "SAFEST_FEASIBLE"


class RouteStatus(str, Enum):
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


class ShelterStatus(str, Enum):
    OPEN = "OPEN"
    APPROACHING_CAPACITY = "APPROACHING_CAPACITY"
    FULL = "FULL"
    DAMAGED_CLOSED = "DAMAGED_CLOSED"
    UNKNOWN = "UNKNOWN"


class WeatherObservation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    observation_id: str = Field(description="UUID v4 of weather capture")
    provider_name: str = Field(description="e.g. Open-Meteo, NOAA")
    observation_timestamp_utc: datetime = Field(description="Actual meteorological reading timestamp")
    is_historical_reconstructed: bool = Field(description="True if historical weather fetched for recorded asset timestamp")
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    temperature_celsius: Optional[float] = None
    wind_speed_mps: Optional[float] = None
    wind_gust_mps: Optional[float] = None
    wind_direction_deg: Optional[float] = Field(default=None, ge=0.0, le=360.0)
    visibility_meters: Optional[float] = Field(default=None, ge=0.0)
    precipitation_mm_hr: Optional[float] = Field(default=None, ge=0.0)
    cloud_cover_percentage: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    relative_humidity_percentage: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    flight_suitability: str = Field(description="'OPTIMAL', 'MARGINAL', 'GROUNDED', or 'UNAVAILABLE'")
    ground_trafficability_index: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class RouteSegment(BaseModel):
    segment_index: int
    name: str
    distance_meters: float
    duration_seconds: float
    is_blocked: bool
    hazard_proximity_meters: Optional[float] = None
    geo_line: List[GeoPoint] = Field(default_factory=list)


class RouteAssessment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    route_id: str = Field(description="UUID v4 of assessed route")
    route_type: RouteType = Field(description="FASTEST_FEASIBLE or SAFEST_FEASIBLE")
    status: RouteStatus = Field(description="ACTIVE, BLOCKED, DEGRADED, or UNAVAILABLE")
    origin: GeoPoint
    destination: GeoPoint
    destination_shelter_id: Optional[str] = None
    total_distance_meters: Optional[float] = None
    total_duration_seconds: Optional[float] = None
    elevation_gain_meters: Optional[float] = None
    hazards_avoided_count: int = Field(default=0, ge=0)
    road_segments: List[RouteSegment] = Field(default_factory=list)
    geometry_geojson: Optional[Dict[str, Any]] = None
    routing_engine_name: str
    engine_response_timestamp_utc: datetime
    evidence_ids: List[str] = Field(min_length=1)


class Shelter(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    shelter_id: str
    name: str
    geo_location: GeoPoint
    status: ShelterStatus
    capacity_total: int = Field(ge=0)
    capacity_occupied: int = Field(ge=0)
    is_generator_powered: bool = False
    medical_support_available: bool = False
    last_reported_utc: datetime
    modality: Modality = Modality.OBSERVED
    source_registry: str


class HazardZone(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    hazard_id: str
    hazard_type: str
    threat_level: ThreatLevel
    geo_boundary: GeoPolygon
    identified_at_utc: datetime
    active: bool = True
    evidence_ids: List[str] = Field(default_factory=list)



class SituationEvent(BaseModel):
    """
    Immutable event appended to the SituationEngine audit trail.
    Links causally to supporting evidence_ids.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="UUID v4 of the event")
    situation_id: str = Field(description="UUID v4 of the parent situation")
    sequence_number: int = Field(ge=1, description="Monotonically increasing sequence number")
    event_timestamp_utc: datetime = Field(default_factory=utcnow, description="Event production timestamp")
    event_type: str = Field(description="Canonical event identifier (e.g. 'POTENTIAL_UNAUTHORIZED_CROSSING_INDICATOR')")
    threat_level: ThreatLevel = Field(description="Assessed event threat level")
    evidence_ids: List[str] = Field(min_length=1, description="Causal evidence IDs supporting this event")
    geo_point: Optional[GeoPoint] = Field(default=None)
    sector_id: Optional[str] = Field(default=None)
    description: str = Field(description="Deterministic human-readable event summary")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event-specific parameters")


class SectorVulnerabilitySummary(BaseModel):
    """
    Sector vulnerability assessment calculated strictly by the deterministic vulnerability engine.
    If required evidence inputs are missing, vulnerability_score is None and status is INSUFFICIENT_EVIDENCE.
    """
    sector_id: str
    sector_name: str
    sector_type: str = Field(default="SENSOR_RELATIVE", description="'SENSOR_RELATIVE', 'OPERATIONAL_GEOFENCE', or 'AUTHORITATIVE_BORDER'")
    authoritative_border_available: bool = Field(default=False, description="Whether authoritative international border geometry is active in local registry")
    vulnerability_score: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Null if required inputs are missing/unverified")
    vulnerability_status: str = Field(default="INSUFFICIENT_EVIDENCE", description="'CALCULATED', 'INSUFFICIENT_EVIDENCE', or 'UNAVAILABLE'")
    contributing_factors: Dict[str, Any] = Field(default_factory=dict, description="Factor breakdown: status and value")
    threat_level: ThreatLevel
    active_indicators_count: int = Field(ge=0, default=0)
    last_observation_utc: Optional[datetime] = None
    sensor_coverage_status: str = Field(default="NOMINAL", description="'NOMINAL', 'DEGRADED', or 'BLIND_SPOT'")


class SituationState(BaseModel):
    """
    Mutable state representing the operational frame of an active situation session.
    """
    situation_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="UUID v4 of active situation")
    project_id: str = Field(description="UUID v4 of parent project")
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Associated session or mission run")
    mode: OperationMode = Field(description="Active operation mode")
    temporal_mode: TemporalMode = Field(description="Temporal mode of processing")
    created_at_utc: datetime = Field(default_factory=utcnow)
    updated_at_utc: datetime = Field(default_factory=utcnow)
    active_frame_index: int = Field(default=0, ge=0)

    is_active: bool = Field(default=True)
    overall_threat_level: ThreatLevel = Field(default=ThreatLevel.LOW)
    overall_score: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Null if insufficient evidence")
    overall_score_status: str = Field(default="CALCULATED", description="'CALCULATED', 'INSUFFICIENT_EVIDENCE', or 'UNAVAILABLE'")

    active_evidence_count: int = Field(default=0, ge=0)
    active_event_count: int = Field(default=0, ge=0)
    latest_event_id: Optional[str] = None
    sectors: List[SectorVulnerabilitySummary] = Field(default_factory=list)


class BorderSituationReport(BaseModel):
    """
    Machine-readable, deterministic situation report for Border Security mode.
    """
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    situation_id: str
    session_id: str
    generated_at_utc: datetime = Field(default_factory=utcnow)
    operation_mode: OperationMode = Field(default=OperationMode.BORDER_SECURITY)
    temporal_mode: TemporalMode
    tactical_overview: Dict[str, Any]
    detections_summary: Dict[str, Any]
    potential_unauthorized_crossing_indicators: List[Dict[str, Any]]
    sector_assessments: List[SectorVulnerabilitySummary]
    environmental_impact: Dict[str, Any]
    mistral_advisory: Optional[Dict[str, Any]] = None
    evidence_manifest: Dict[str, Any]
    confidence_and_limitations: Dict[str, Any]


class DisasterSituationReport(BaseModel):
    """
    Machine-readable, deterministic situation report for Disaster Response mode.
    """
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    situation_id: str
    session_id: str
    generated_at_utc: datetime = Field(default_factory=utcnow)
    operation_mode: OperationMode = Field(default=OperationMode.DISASTER_RESPONSE)
    temporal_mode: TemporalMode
    disaster_assessment: Dict[str, Any]
    infrastructure_damage: Dict[str, Any]
    evacuation_routes: List[Dict[str, Any]]
    shelter_assessments: List[Dict[str, Any]]
    environmental_conditions: Dict[str, Any]
    mistral_advisory: Optional[Dict[str, Any]] = None
    evidence_manifest: Dict[str, Any]
    confidence_and_limitations: Dict[str, Any]


# ============================================================================
# API ENDPOINT RESPONSE SCHEMAS (Roadmap Step 12)
# ============================================================================

class SituationItemResponse(BaseModel):
    id: str
    title: str
    situation_type: str
    status: str
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    vulnerability_score: Optional[float] = None
    threat_level: Optional[str] = None
    created_at: str
    updated_at: str


class SituationDetailResponse(SituationItemResponse):
    detections: List[Dict[str, Any]] = Field(default_factory=list)
    events: List[Dict[str, Any]] = Field(default_factory=list)
    weather: Optional[Dict[str, Any]] = None
    routes: Optional[List[Dict[str, Any]]] = None
    shelters: Optional[List[Dict[str, Any]]] = None
    damage: Optional[Dict[str, Any]] = None


class SituationEventResponse(BaseModel):
    id: str
    situation_id: str
    event_type: str
    title: str
    description: Optional[str] = None
    severity: str
    created_at: str
    metadata: Optional[Dict[str, Any]] = None


class RouteOptionResponse(BaseModel):
    id: str
    name: str
    type: str
    distance_km: float
    duration_min: float
    hazard_clearance_score: Optional[float] = None
    is_viable: bool
    waypoints: Optional[List[List[float]]] = None


class SituationReportResponse(BaseModel):
    situation_id: str
    generated_at: str
    executive_summary: str
    verified_facts: List[str] = Field(default_factory=list)
    derived_metrics: Dict[str, Any] = Field(default_factory=dict)
    ai_advisory: Optional[Dict[str, Any]] = None
    evidence_lineage: Optional[List[Dict[str, Any]]] = None
    # Phase C Authoritative Analysis Backing
    analysis_id: Optional[str] = None
    job_id: Optional[str] = None
    project_id: Optional[str] = None
    mode: Optional[str] = None
    analysis_type: Optional[str] = None
    input_asset_reference: Optional[str] = None
    overall_status: Optional[str] = None
    limitations: List[str] = Field(default_factory=list)
    detection_summary: Optional[Dict[str, Any]] = None
    damage_summary: Optional[Dict[str, Any]] = None
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    annotated_image_base64: Optional[str] = None
    annotated_artifact: Optional[Dict[str, Any]] = None
    annotated_video_artifact: Optional[Dict[str, Any]] = None

