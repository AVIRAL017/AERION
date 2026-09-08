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

from app.schemas.evidence import (
    GeoPoint,
    Modality,
    OperationMode,
    TemporalMode,
    ThreatLevel,
    utcnow,
)


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
