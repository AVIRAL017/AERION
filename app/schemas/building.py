"""
AERION — Building Footprint Schemas & Contracts (Step 20)
Strict Pydantic models for building footprints, geometry, and spatial query responses.

Invariants:
1. Zero fabrication: building_type defaults to GENERAL unless source-provided.
2. Damage status: newly ingested buildings strictly default to NOT_ASSESSED.
3. Occupancy, structural soundness, and safety are NEVER fabricated.
4. Area calculation from geometry is explicitly marked DERIVED.
5. All proximity queries carry mandatory analytical disclaimers.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.evidence import EvidenceRecord, GeoPoint


class BuildingDamageStatus(str, Enum):
    NOT_ASSESSED = "NOT_ASSESSED"
    SOURCE_REPORTED = "SOURCE_REPORTED"
    MODEL_ASSESSED = "MODEL_ASSESSED"


class BuildingRecord(BaseModel):
    """
    Represents an individual building footprint record from PostGIS.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(description="Internal UUID of the building footprint record")
    dataset_id: str = Field(description="FK to geospatial_datasets provenance registry")
    source_record_id: Optional[str] = Field(default=None, description="Original feature ID from source (e.g. OSM_WAY_123)")
    building_type: str = Field(default="GENERAL", description="Building categorization from source")
    damage_status: BuildingDamageStatus = Field(
        default=BuildingDamageStatus.NOT_ASSESSED,
        description="Damage state. Strictly NOT_ASSESSED upon ingestion.",
    )
    area_m2: Optional[float] = Field(default=None, description="Footprint area in square meters")
    area_provenance: str = Field(default="DERIVED", description="Provenance of area measurement (DERIVED or EXTERNALLY_PROVIDED)")
    height: Optional[float] = Field(default=None, description="Height in meters if provided by source")
    levels: Optional[int] = Field(default=None, description="Number of building storeys if provided by source")
    address: Optional[str] = Field(default=None, description="Address or street description if provided")
    source_url: Optional[str] = Field(default=None, description="Upstream source URL")
    distance_to_query_km: Optional[float] = Field(default=None, description="Geodesic distance to query coordinate in km")
    geometry_geojson: Optional[Dict[str, Any]] = Field(default=None, description="GeoJSON representation of building polygon")
    metadata_json: Dict[str, Any] = Field(default_factory=dict, description="Original source tags and properties")
    created_at: datetime = Field(description="Record ingestion timestamp")


class BuildingQueryResponse(BaseModel):
    """
    Response model for building footprint queries (radius proximity or polygon intersection).
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    available: bool = Field(description="True if building footprint dataset is available and loaded")
    record_count: int = Field(description="Number of buildings returned")
    buildings: List[BuildingRecord] = Field(default_factory=list, description="Matching building footprint records")
    query_coordinates: Optional[GeoPoint] = Field(default=None, description="Center query coordinates if point query")
    radius_km: Optional[float] = Field(default=None, description="Query radius in kilometers")
    disclaimer: str = Field(
        default="Building footprints represent externally sourced geometry and do not establish occupancy, structural safety, or damage.",
        description="Mandatory semantic safety warning",
    )
    evidence: Optional[EvidenceRecord] = Field(default=None, description="Attached DERIVED EvidenceRecord")
