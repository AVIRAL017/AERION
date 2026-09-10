"""
AERION — Critical Infrastructure Schemas & Contracts (Step 20)
Strict Pydantic models for critical infrastructure facilities, operational status,
administrative enrichment, and spatial query responses.

Invariants:
1. Operational status strictly defaults to UNKNOWN for externally provided reference data.
2. Capacity, emergency readiness, and availability for evacuation are NEVER fabricated.
3. Administrative enrichment resolves state and district codes via PostGIS spatial containment.
4. Preserves original source attributes and tags without alteration.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.evidence import EvidenceRecord, GeoPoint


class InfrastructureType(str, Enum):
    HOSPITAL = "HOSPITAL"
    FIRE_STATION = "FIRE_STATION"
    POLICE_STATION = "POLICE_STATION"
    SCHOOL = "SCHOOL"
    EMERGENCY_FACILITY = "EMERGENCY_FACILITY"
    POWER_FACILITY = "POWER_FACILITY"
    WATER_FACILITY = "WATER_FACILITY"
    BRIDGE = "BRIDGE"
    OTHER = "OTHER"


class InfrastructureOperationalStatus(str, Enum):
    CONFIRMED_OPERATIONAL = "CONFIRMED_OPERATIONAL"
    SOURCE_REPORTED = "SOURCE_REPORTED"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"
    NOT_PROVIDED = "NOT_PROVIDED"


class CriticalInfrastructureRecord(BaseModel):
    """
    Represents an individual critical infrastructure facility.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(description="Internal UUID of the infrastructure record")
    dataset_id: str = Field(description="FK to geospatial_datasets provenance registry")
    source_record_id: Optional[str] = Field(default=None, description="Original feature ID from source (e.g. OSM_NODE_123)")
    name: str = Field(description="Facility name")
    infrastructure_type: InfrastructureType = Field(description="Primary categorization of facility")
    subtype: Optional[str] = Field(default=None, description="Detailed subtype from source tags")
    operational_status: InfrastructureOperationalStatus = Field(
        default=InfrastructureOperationalStatus.UNKNOWN,
        description="Operational condition. Strictly UNKNOWN unless verified.",
    )
    address: Optional[str] = Field(default=None, description="Address or street location")
    state_code: Optional[str] = Field(default=None, description="Administrative ADM1 state code")
    state_name: Optional[str] = Field(default=None, description="Enriched ADM1 state name")
    district_code: Optional[str] = Field(default=None, description="Administrative ADM2 district code")
    district_name: Optional[str] = Field(default=None, description="Enriched ADM2 district name")
    latitude: float = Field(description="Latitude in decimal degrees")
    longitude: float = Field(description="Longitude in decimal degrees")
    distance_to_query_km: Optional[float] = Field(default=None, description="Geodesic distance to query coordinate in km")
    source_url: Optional[str] = Field(default=None, description="Upstream source URL")
    geometry_geojson: Optional[Dict[str, Any]] = Field(default=None, description="GeoJSON representation of feature")
    metadata_json: Dict[str, Any] = Field(default_factory=dict, description="Original source tags and properties")
    created_at: datetime = Field(description="Record ingestion timestamp")


class InfrastructureQueryResponse(BaseModel):
    """
    Response model for critical infrastructure spatial queries.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    available: bool = Field(description="True if critical infrastructure dataset is available and loaded")
    record_count: int = Field(description="Number of facilities returned")
    facilities: List[CriticalInfrastructureRecord] = Field(default_factory=list, description="Matching infrastructure records")
    query_coordinates: Optional[GeoPoint] = Field(default=None, description="Center query coordinates")
    radius_km: Optional[float] = Field(default=None, description="Query radius in kilometers")
    disclaimer: str = Field(
        default="Critical infrastructure records do not establish current operational status unless the source explicitly provides such status.",
        description="Mandatory semantic safety warning",
    )
    evidence: Optional[EvidenceRecord] = Field(default=None, description="Attached DERIVED EvidenceRecord")
