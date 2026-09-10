"""
AERION — Shelter & Evacuation-Point Contracts & Schemas (Step 18)
Provides strict Pydantic models for shelter records, operational status semantics,
capacity semantics, administrative enrichment, and proximity search responses.

Core Invariants:
1. Zero fabrication: If capacity, operational status, opening hours, or contact info
   are absent from the source, they must be represented as UNKNOWN or NOT_PROVIDED.
2. Operational Status:
   - CONFIRMED_OPERATIONAL (only when source explicitly confirms)
   - REPORTED_OPERATIONAL
   - CLOSED
   - UNKNOWN (default)
   - NOT_PROVIDED
3. Capacity Status:
   - VERIFIED
   - SOURCE_REPORTED
   - UNKNOWN
   - NOT_PROVIDED (default)
4. Distance is an objective spatial metric in km, never a fabricated "safety score".
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.evidence import EvidenceRecord, GeoPoint, utcnow
from app.schemas.geospatial import DatasetProvenanceContract


class OperationalStatus(str, Enum):
    CONFIRMED_OPERATIONAL = "CONFIRMED_OPERATIONAL"
    REPORTED_OPERATIONAL = "REPORTED_OPERATIONAL"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"
    NOT_PROVIDED = "NOT_PROVIDED"


class CapacityStatus(str, Enum):
    VERIFIED = "VERIFIED"
    SOURCE_REPORTED = "SOURCE_REPORTED"
    UNKNOWN = "UNKNOWN"
    NOT_PROVIDED = "NOT_PROVIDED"


class ShelterType(str, Enum):
    CYCLONE_SHELTER = "CYCLONE_SHELTER"
    FLOOD_RELIEF_CENTER = "FLOOD_RELIEF_CENTER"
    RELIEF_CAMP = "RELIEF_CAMP"
    COMMUNITY_CENTER = "COMMUNITY_CENTER"
    SCHOOL_REFUGE = "SCHOOL_REFUGE"
    EMERGENCY_FACILITY = "EMERGENCY_FACILITY"
    STADIUM = "STADIUM"
    HOSPITAL_REFUGE = "HOSPITAL_REFUGE"
    UNKNOWN = "UNKNOWN"


class ShelterRecord(BaseModel):
    """
    Standardized shelter & evacuation point record.
    Adheres strictly to the Zero Fabrication and Operational Uncertainty Invariants.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    shelter_id: str = Field(description="Unique shelter identifier")
    name: str = Field(description="Name of facility / shelter")
    location: GeoPoint = Field(description="Verified WGS-84 point geometry")
    shelter_type: ShelterType = Field(default=ShelterType.UNKNOWN, description="Structural / functional classification")
    operational_status: OperationalStatus = Field(default=OperationalStatus.UNKNOWN, description="Operational state")
    
    # Capacity
    capacity_total: Optional[int] = Field(default=None, description="Maximum occupant capacity or None if unknown")
    capacity_occupied: Optional[int] = Field(default=None, description="Current occupant count or None if unknown")
    capacity_status: CapacityStatus = Field(default=CapacityStatus.NOT_PROVIDED, description="Verification level of capacity")
    
    # Infrastructure & Services
    is_generator_powered: bool = Field(default=False, description="Backup electrical power available")
    medical_support_available: bool = Field(default=False, description="On-site medical personnel or supplies")
    accessibility: Optional[str] = Field(default=None, description="Wheelchair / physical accessibility details")
    contact_information: Optional[str] = Field(default=None, description="Official telephone or radio contact")
    opening_hours: Optional[str] = Field(default=None, description="Operating schedule or 24/7 indicator")
    services: List[str] = Field(default_factory=list, description="Available amenities (e.g. ['drinking_water', 'sanitation'])")
    address: Optional[str] = Field(default=None, description="Physical address or landmark description")
    
    # Administrative linkage (Step 17)
    state_code: Optional[str] = Field(default=None, description="ADM1 State code")
    district_code: Optional[str] = Field(default=None, description="ADM2 District code")
    state_name: Optional[str] = Field(default=None, description="Resolved state name")
    district_name: Optional[str] = Field(default=None, description="Resolved district name")

    # Spatial query enrichment
    distance_km: Optional[float] = Field(default=None, description="Geodesic distance from query point in kilometers")

    # Provenance
    source_registry: str = Field(description="Originating registry or organization")
    source_record_id: Optional[str] = Field(default=None, description="Stable identifier within source registry")
    source_url: Optional[str] = Field(default=None, description="Source registry URL")
    dataset_id: Optional[str] = Field(default=None, description="Associated geospatial_datasets ID")
    last_reported_utc: datetime = Field(description="Timestamp of last source report or observation")
    created_at_utc: datetime = Field(default_factory=utcnow, description="Record creation timestamp")
    metadata_json: Dict[str, Any] = Field(default_factory=dict, description="Raw source tags and properties")


class ShelterQueryResponse(BaseModel):
    """
    Structured response for shelter proximity and filtering queries.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    available: bool = Field(description="True if any shelter records were retrieved")
    record_count: int = Field(description="Number of shelter records returned")
    shelters: List[ShelterRecord] = Field(default_factory=list, description="List of matched shelter records")
    query_point: Optional[GeoPoint] = Field(default=None, description="Origin query coordinates")
    radius_km: Optional[float] = Field(default=None, description="Search radius in kilometers")
    disclaimer: str = Field(
        default="Presence of a shelter record does not establish that the shelter is currently operational. Distance is derived from coordinates; it is not a safety score.",
        description="Mandatory operational safety notice",
    )
    evidence: Optional[EvidenceRecord] = Field(default=None, description="Associated DERIVED EvidenceRecord")
    provenance: Optional[DatasetProvenanceContract] = Field(default=None, description="Dataset metadata")


class ShelterIngestionSummary(BaseModel):
    """
    Summary report produced following shelter data ingestion.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str
    total_source_records: int
    valid_records: int
    invalid_records: int
    inserted_records: int
    skipped_duplicates: int
    missing_coordinates: int
    missing_names: int
    missing_source_ids: int
    transformation_performed: str
    geometry_errors: int
    enriched_with_admin_boundaries: int
    ingestion_timestamp_utc: datetime = Field(default_factory=utcnow)
