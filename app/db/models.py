"""
AERION — 19 Core Relational & Spatial Database Entities
Adheres strictly to the AERION System Architecture specification:
- SQLAlchemy 2.0 mapped columns
- Separate image/pixel space vs PostGIS WGS84 EPSG:4326 geometry
- Explicit UUID primary keys and foreign key relationships
- GiST indexing on geospatial geometry columns
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================================
# 1. ORGANIZATIONS
# ============================================================================
class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    users: Mapped[List["User"]] = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    projects: Mapped[List["Project"]] = relationship("Project", back_populates="organization", cascade="all, delete-orphan")
    subscription: Mapped[Optional["Subscription"]] = relationship("Subscription", back_populates="organization", uselist=False, cascade="all, delete-orphan")
    usage_events: Mapped[List["UsageEvent"]] = relationship("UsageEvent", back_populates="organization", cascade="all, delete-orphan")


# ============================================================================
# 2. USERS
# ============================================================================
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="operator", nullable=False)  # 'admin', 'operator', 'analyst'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")


# ============================================================================
# 3. PROJECTS
# ============================================================================
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    mode: Mapped[str] = mapped_column(String(50), nullable=False)  # 'disaster', 'border'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="projects")
    assets: Mapped[List["Asset"]] = relationship("Asset", back_populates="project", cascade="all, delete-orphan")
    geofences: Mapped[List["Geofence"]] = relationship("Geofence", back_populates="project", cascade="all, delete-orphan")
    analysis_jobs: Mapped[List["AnalysisJob"]] = relationship("AnalysisJob", back_populates="project", cascade="all, delete-orphan")
    evidence_records: Mapped[List["EvidenceRecord"]] = relationship("EvidenceRecord", back_populates="project", cascade="all, delete-orphan")
    situations: Mapped[List["Situation"]] = relationship("Situation", back_populates="project", cascade="all, delete-orphan")
    shelters: Mapped[List["Shelter"]] = relationship("Shelter", back_populates="project", cascade="all, delete-orphan")
    hazard_zones: Mapped[List["HazardZone"]] = relationship("HazardZone", back_populates="project", cascade="all, delete-orphan")


# ============================================================================
# 4. ASSETS
# ============================================================================
class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'drone_image', 'satellite_image', 'disaster_pair', 'border_video'
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="assets")


# ============================================================================
# 5. GEOFENCES
# ============================================================================
class Geofence(Base):
    __tablename__ = "geofences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Image/Pixel Space
    pixel_polygon: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Geospatial Space (WGS84)
    geom_polygon_4326 = mapped_column(Geometry(geometry_type="POLYGON", srid=4326, spatial_index=True), nullable=True)
    is_georeferenced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dwell_threshold: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="geofences")
    border_events: Mapped[List["BorderEvent"]] = relationship("BorderEvent", back_populates="geofence")


# ============================================================================
# 6. ANALYSIS_JOBS
# ============================================================================
class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False, index=True)  # 'queued', 'processing', 'completed', 'failed'
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="analysis_jobs")
    analysis_result: Mapped[Optional["AnalysisResult"]] = relationship("AnalysisResult", back_populates="job", uselist=False, cascade="all, delete-orphan")
    usage_events: Mapped[List["UsageEvent"]] = relationship("UsageEvent", back_populates="job")


# ============================================================================
# 7. ANALYSIS_RESULTS
# ============================================================================
class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), unique=True, nullable=False)
    analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False, index=True)
    overall_status: Mapped[str] = mapped_column(String(100), nullable=False)
    summary_critical: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary_high: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary_medium: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary_low: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    raw_payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    job: Mapped["AnalysisJob"] = relationship("AnalysisJob", back_populates="analysis_result")
    detections: Mapped[List["Detection"]] = relationship("Detection", back_populates="result", cascade="all, delete-orphan")
    tracks: Mapped[List["Track"]] = relationship("Track", back_populates="result", cascade="all, delete-orphan")
    border_events: Mapped[List["BorderEvent"]] = relationship("BorderEvent", back_populates="result", cascade="all, delete-orphan")
    damage_analysis: Mapped[Optional["DamageAnalysis"]] = relationship("DamageAnalysis", back_populates="result", uselist=False, cascade="all, delete-orphan")
    intelligence_items: Mapped[List["IntelligenceItemModel"]] = relationship("IntelligenceItemModel", back_populates="result", cascade="all, delete-orphan")


# ============================================================================
# 8. DETECTIONS
# ============================================================================
class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_results.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    class_id: Mapped[int] = mapped_column(Integer, nullable=False)
    class_name: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    # Image/Pixel Space
    pixel_bbox_x1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pixel_bbox_y1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pixel_bbox_x2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pixel_bbox_y2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pixel_obb_points: Mapped[Optional[List[Dict[str, float]]]] = mapped_column(JSONB, nullable=True)
    # Geospatial Space (WGS84)
    geom_point_4326 = mapped_column(Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=True)
    is_georeferenced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    track_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    frame_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    result: Mapped["AnalysisResult"] = relationship("AnalysisResult", back_populates="detections")


# ============================================================================
# 9. TRACKS
# ============================================================================
class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_results.id", ondelete="CASCADE"), nullable=False, index=True)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    class_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    # Image/Pixel Space
    pixel_center_x: Mapped[float] = mapped_column(Float, nullable=False)
    pixel_center_y: Mapped[float] = mapped_column(Float, nullable=False)
    pixel_trajectory: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSONB, nullable=True)
    # Geospatial Space (WGS84)
    geom_point_4326 = mapped_column(Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=True)
    geom_trajectory_4326 = mapped_column(Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=True), nullable=True)
    is_georeferenced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    direction: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    persistence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    frame_number: Mapped[int] = mapped_column(Integer, nullable=False)

    result: Mapped["AnalysisResult"] = relationship("AnalysisResult", back_populates="tracks")


# ============================================================================
# 10. BORDER_EVENTS
# ============================================================================
class BorderEvent(Base):
    __tablename__ = "border_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_results.id", ondelete="CASCADE"), nullable=False, index=True)
    geofence_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("geofences.id", ondelete="SET NULL"), nullable=True)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'breach', 'dwell_exceeded', 'proximity_warning'
    alert_level: Mapped[str] = mapped_column(String(50), nullable=False)  # 'CRITICAL', 'HIGH'
    border_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    # Image/Pixel Space
    pixel_location_x: Mapped[float] = mapped_column(Float, nullable=False)
    pixel_location_y: Mapped[float] = mapped_column(Float, nullable=False)
    # Geospatial Space (WGS84)
    geom_point_4326 = mapped_column(Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=True)
    is_georeferenced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    frame_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    result: Mapped["AnalysisResult"] = relationship("AnalysisResult", back_populates="border_events")
    geofence: Mapped[Optional["Geofence"]] = relationship("Geofence", back_populates="border_events")


# ============================================================================
# 11. DAMAGE_ANALYSES
# ============================================================================
class DamageAnalysis(Base):
    __tablename__ = "damage_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_results.id", ondelete="CASCADE"), unique=True, nullable=False)
    threshold: Mapped[float] = mapped_column(Numeric(5, 4), default=0.50, nullable=False)
    damage_pixels: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_pixels: Mapped[int] = mapped_column(BigInteger, nullable=False)
    damage_ratio: Mapped[float] = mapped_column(Numeric(7, 6), nullable=False)
    damage_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    probability_mean: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    mask_storage_key: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    result: Mapped["AnalysisResult"] = relationship("AnalysisResult", back_populates="damage_analysis")


# ============================================================================
# 12. USAGE_EVENTS
# ============================================================================
class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    dimension: Mapped[str] = mapped_column(String(50), nullable=False)  # 'drone_image', 'satellite_tile', 'damage_pair', 'video_minute'
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="usage_events")
    job: Mapped[Optional["AnalysisJob"]] = relationship("AnalysisJob", back_populates="usage_events")


# ============================================================================
# 13. SUBSCRIPTIONS
# ============================================================================
class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="FREE", nullable=False)  # 'FREE', 'PRO'
    price_inr: Mapped[int] = mapped_column(Integer, default=0, nullable=False)      # PRO = 9
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="subscription")


# ============================================================================
# 14. EVIDENCE_RECORDS
# ============================================================================
class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_evidence_ids: Mapped[List[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, nullable=False)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)  # 'FROZEN_MODEL_VISDRONE_YOLO', etc.
    temporal_mode: Mapped[str] = mapped_column(String(50), nullable=False)  # 'LIVE_STREAM', etc.
    asset_timestamp_utc: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    modality: Mapped[str] = mapped_column(String(50), nullable=False)       # 'OBSERVED', 'DERIVED', etc.
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    verification_state: Mapped[str] = mapped_column(String(50), nullable=False)  # 'UNVERIFIED', etc.
    pixel_bbox: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    # Geospatial Space (WGS84)
    geom_point_4326 = mapped_column(Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=True)
    geom_polygon_4326 = mapped_column(Geometry(geometry_type="POLYGON", srid=4326, spatial_index=True), nullable=True)
    sensor_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    raw_payload_uri: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="evidence_records")


# ============================================================================
# 15. SITUATIONS
# ============================================================================
class Situation(Base):
    __tablename__ = "situations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(50), nullable=False)  # 'BORDER_SECURITY', 'DISASTER_RESPONSE'
    temporal_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    overall_threat_level: Mapped[str] = mapped_column(String(50), nullable=False)
    overall_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)  # 0.0 - 100.0
    active_frame_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="situations")
    events: Mapped[List["SituationEvent"]] = relationship("SituationEvent", back_populates="situation", cascade="all, delete-orphan")
    reports: Mapped[List["SituationReport"]] = relationship("SituationReport", back_populates="situation", cascade="all, delete-orphan")


# ============================================================================
# 16. SITUATION_EVENTS
# ============================================================================
class SituationEvent(Base):
    __tablename__ = "situation_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    situation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("situations.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    threat_level: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence_ids: Mapped[List[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    geom_point_4326 = mapped_column(Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=True)
    sector_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    situation: Mapped["Situation"] = relationship("Situation", back_populates="events")

    __table_args__ = (
        Index("idx_situation_events_seq", "situation_id", "sequence_number"),
    )


# ============================================================================
# 17. SITUATION_REPORTS
# ============================================================================
class SituationReport(Base):
    __tablename__ = "situation_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    situation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("situations.id", ondelete="CASCADE"), nullable=False, index=True)
    operation_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    temporal_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    report_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    overall_confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    mistral_advisory_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    situation: Mapped["Situation"] = relationship("Situation", back_populates="reports")


# ============================================================================
# 18. SHELTERS
# ============================================================================
class Shelter(Base):
    __tablename__ = "shelters"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # Authoritative registry ID or generated ID
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    dataset_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("geospatial_datasets.id", ondelete="SET NULL"), nullable=True, index=True)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    geom_point_4326 = mapped_column(Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False)
    
    # Operational semantics (Step 18)
    shelter_type: Mapped[str] = mapped_column(String(100), default="UNKNOWN", nullable=False, index=True)  # 'CYCLONE_SHELTER', 'RELIEF_CAMP', 'COMMUNITY_CENTER', 'UNKNOWN'
    operational_status: Mapped[str] = mapped_column(String(50), default="UNKNOWN", nullable=False, index=True)  # 'CONFIRMED_OPERATIONAL', 'REPORTED_OPERATIONAL', 'CLOSED', 'UNKNOWN', 'NOT_PROVIDED'
    status: Mapped[str] = mapped_column(String(50), default="UNKNOWN", nullable=False)  # Legacy compatibility: 'OPEN', 'FULL', 'CLOSED', 'UNKNOWN'
    
    # Capacity semantics (Step 18)
    capacity_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    capacity_occupied: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    capacity_status: Mapped[str] = mapped_column(String(50), default="NOT_PROVIDED", nullable=False)  # 'VERIFIED', 'SOURCE_REPORTED', 'UNKNOWN', 'NOT_PROVIDED'
    
    # Services & Facilities
    is_generator_powered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    medical_support_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    accessibility: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_information: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    opening_hours: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    services: Mapped[List[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Administrative enrichment (Step 17 linkage)
    state_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    district_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    # Provenance
    source_registry: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    last_reported_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="shelters")
    dataset: Mapped[Optional["GeospatialDataset"]] = relationship("GeospatialDataset", back_populates="shelters")

    __table_args__ = (
        Index("ix_shelters_state_district", "state_code", "district_code"),
        Index("ix_shelters_op_status", "operational_status"),
        Index("ix_shelters_type", "shelter_type"),
    )


# ============================================================================
# 19. HAZARD_ZONES
# ============================================================================
class HazardZone(Base):
    __tablename__ = "hazard_zones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    hazard_type: Mapped[str] = mapped_column(String(100), nullable=False)  # 'FLOOD_POLYGON', etc.
    threat_level: Mapped[str] = mapped_column(String(50), nullable=False)
    geom_polygon_4326 = mapped_column(Geometry(geometry_type="POLYGON", srid=4326, spatial_index=True), nullable=False)
    evidence_ids: Mapped[List[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    identified_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="hazard_zones")


# Auxiliary entity for analysis_results -> intelligence_items mapping
class IntelligenceItemModel(Base):
    __tablename__ = "intelligence_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_results.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    item_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    result: Mapped["AnalysisResult"] = relationship("AnalysisResult", back_populates="intelligence_items")


# ============================================================================
# 20. GEOSPATIAL DATASETS (Step 17 Provenance Layer)
# ============================================================================
class GeospatialDataset(Base):
    __tablename__ = "geospatial_datasets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    dataset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    acquisition_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    license: Mapped[str] = mapped_column(String(255), nullable=False)
    attribution: Mapped[str] = mapped_column(Text, nullable=False)
    geographic_scope: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. 'INDIA_NATIONAL'
    geometry_type: Mapped[str] = mapped_column(String(50), nullable=False)      # e.g. 'MULTIPOLYGON'
    crs: Mapped[str] = mapped_column(String(50), nullable=False)                # e.g. 'EPSG:7755' or 'EPSG:4326'
    source_format: Mapped[str] = mapped_column(String(50), nullable=False)      # e.g. 'GeoJSON', 'Shapefile'
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # SHA-256
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    boundaries: Mapped[List["AdministrativeBoundary"]] = relationship("AdministrativeBoundary", back_populates="dataset", cascade="all, delete-orphan")
    hazard_records: Mapped[List["HistoricalHazardRecord"]] = relationship("HistoricalHazardRecord", back_populates="dataset", cascade="all, delete-orphan")
    shelters: Mapped[List["Shelter"]] = relationship("Shelter", back_populates="dataset")
    international_boundaries: Mapped[List["InternationalBoundary"]] = relationship("InternationalBoundary", back_populates="dataset", cascade="all, delete-orphan")


# ============================================================================
# 20B. INTERNATIONAL BOUNDARIES (Step 19 Authoritative Operational Border)
# ============================================================================
class InternationalBoundary(Base):
    __tablename__ = "international_boundaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("geospatial_datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    boundary_type: Mapped[str] = mapped_column(String(100), default="INTERNATIONAL_OPERATIONAL", nullable=False, index=True)  # 'INTERNATIONAL_OPERATIONAL'
    geom_4326 = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    dataset: Mapped["GeospatialDataset"] = relationship("GeospatialDataset", back_populates="international_boundaries")

    __table_args__ = (
        Index("ix_intl_boundaries_type_name", "boundary_type", "name"),
    )


# ============================================================================
# 21. ADMINISTRATIVE BOUNDARIES (Step 17 Hierarchy ADM0, ADM1, ADM2)
# ============================================================================
class AdministrativeBoundary(Base):
    __tablename__ = "administrative_boundaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("geospatial_datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # 'ADM0', 'ADM1', 'ADM2'
    country_code: Mapped[str] = mapped_column(String(10), default="IND", nullable=False, index=True)
    state_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    district_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name_canonical: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    geom_4326 = mapped_column(Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True), nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    dataset: Mapped["GeospatialDataset"] = relationship("GeospatialDataset", back_populates="boundaries")

    __table_args__ = (
        Index("ix_admin_boundaries_level_state", "level", "state_code"),
        Index("ix_admin_boundaries_level_district", "level", "district_code"),
    )


# ============================================================================
# 22. HISTORICAL HAZARD RECORDS (Step 17 Flood Inventory Reference Layer)
# ============================================================================
class HistoricalHazardRecord(Base):
    __tablename__ = "historical_hazard_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("geospatial_datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    hazard_type: Mapped[str] = mapped_column(String(100), default="HISTORICAL_FLOOD", nullable=False, index=True)
    source_event_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_date_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    event_date_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    state_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    district_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    cause: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    severity_reported: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    impact_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_live_status: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Strictly False for historical inventory
    geom_4326 = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True), nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    dataset: Mapped["GeospatialDataset"] = relationship("GeospatialDataset", back_populates="hazard_records")

    __table_args__ = (
        Index("ix_hist_hazard_type_event", "hazard_type", "source_event_id"),
    )
