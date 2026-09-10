"""
AERION — Geospatial Data Contracts & Schemas (Step 17)
Strict Pydantic schemas for dataset provenance, administrative boundaries,
historical hazard inventory, and query responses.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.evidence import EvidenceRecord, GeoPoint, GeoPolygon, utcnow


# ============================================================================
# 1. DATASET PROVENANCE CONTRACT
# ============================================================================
class DatasetProvenanceContract(BaseModel):
    """
    Standardized geospatial dataset provenance record adhering strictly to Phase C.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str = Field(description="Unique machine-readable dataset identifier")
    dataset_name: str = Field(description="Human-readable title of the dataset")
    source_name: str = Field(description="Originating agency or organization")
    source_url: Optional[str] = Field(default=None, description="Official source portal or reference URL")
    version: str = Field(description="Dataset release or edition version")
    acquisition_date: Optional[datetime] = Field(default=None, description="Acquisition or ingestion timestamp (UTC)")
    license: str = Field(description="Usage license (e.g. Government Open Data / Research)")
    attribution: str = Field(description="Mandatory attribution text")
    geographic_scope: str = Field(description="Scope, e.g. INDIA_NATIONAL, DISTRICT_LEVEL")
    geometry_type: str = Field(description="Primary geometry representation (MULTIPOLYGON, POLYGON, POINT)")
    crs: str = Field(description="Source Coordinate Reference System (e.g. EPSG:7755, EPSG:4326)")
    source_format: str = Field(description="Original file format (e.g. GeoJSON, Shapefile, CSV)")
    processing_status: str = Field(default="ACTIVE", description="Status e.g. ACTIVE, INGESTED, VERIFIED")
    checksum: str = Field(description="Cryptographic SHA-256 hash of the ingested source asset")
    notes: Optional[str] = Field(default=None, description="Limitations, disclaimers, or operational notes")
    metadata_json: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary source metadata properties")


# ============================================================================
# 2. ADMINISTRATIVE BOUNDARY RESOLUTION
# ============================================================================
class AdminUnitInfo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    level: str = Field(description="Administrative level (ADM0, ADM1, ADM2)")
    name: str = Field(description="Entity name (e.g. 'Andaman & Nicobar Island', 'Kamjong')")
    canonical_name: str = Field(description="Normalized canonical name")
    code: Optional[str] = Field(default=None, description="Administrative code or LGD code")
    country_code: str = Field(default="IND", description="ISO3 country code")
    source_agency: Optional[str] = Field(default=None, description="Source agency if present")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional properties")


class AdminBoundaryResolution(BaseModel):
    """
    Structured response for administrative containment queries.
    Zero fabrication: available is False if coordinates fall outside indexed coverage.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    available: bool = Field(description="True if coordinates were resolved to administrative boundaries")
    query_coordinates: GeoPoint = Field(description="Queried WGS84 coordinates")
    country: Optional[AdminUnitInfo] = Field(default=None, description="ADM0 Country level resolution")
    state: Optional[AdminUnitInfo] = Field(default=None, description="ADM1 State/UT level resolution")
    district: Optional[AdminUnitInfo] = Field(default=None, description="ADM2 District level resolution")
    evidence: Optional[EvidenceRecord] = Field(default=None, description="Attached AERION EvidenceRecord")
    provenance: Optional[DatasetProvenanceContract] = Field(default=None, description="Dataset metadata")


# ============================================================================
# 3. HISTORICAL HAZARD INVENTORY CONTRACT
# ============================================================================
class HistoricalHazardItem(BaseModel):
    """
    Represents an authoritative historical hazard event polygon.
    CRITICAL: Strictly reference evidence, NOT live status.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(description="Internal record UUID")
    hazard_type: str = Field(default="HISTORICAL_FLOOD", description="Nature of hazard")
    source_event_id: str = Field(description="Authoritative source FID / identifier")
    event_date_start: Optional[datetime] = Field(default=None, description="Recorded start timestamp")
    event_date_end: Optional[datetime] = Field(default=None, description="Recorded end timestamp")
    state_name: Optional[str] = Field(default=None, description="State name where event occurred")
    district_name: Optional[str] = Field(default=None, description="District name where event occurred")
    cause: Optional[str] = Field(default=None, description="Reported root cause (e.g. Heavy rains)")
    severity_reported: Optional[str] = Field(default="UNAVAILABLE", description="Reported severity or UNAVAILABLE")
    impact_summary: Optional[str] = Field(default=None, description="Summary of impacts if recorded")
    is_live_status: bool = Field(default=False, description="Strict invariant: always False for reference inventory")
    geometry_geojson: Optional[Dict[str, Any]] = Field(default=None, description="WGS84 GeoJSON geometry")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Raw properties")


class HistoricalHazardQueryResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    is_historical_reference_only: bool = Field(default=True, description="Enforces semantic distinction from live status")
    record_count: int = Field(description="Number of matching historical hazard polygons")
    records: List[HistoricalHazardItem] = Field(default_factory=list, description="Historical hazard features")
    query_point: Optional[GeoPoint] = Field(default=None, description="Center query location")
    radius_km: Optional[float] = Field(default=None, description="Search radius in kilometers")
    disclaimer: str = Field(
        default="Historical flood inventory is reference evidence and must not be interpreted as live flood status.",
        description="Mandatory semantic safety warning",
    )
    evidence: Optional[EvidenceRecord] = Field(default=None, description="Associated evidence item")


# ============================================================================
# 4. INTERNATIONAL BORDER CONTRACT
# ============================================================================
class BorderContractStatus(BaseModel):
    """
    Reports operational international boundary availability for Border Security Mode.
    Zero fabrication: explicit unavailable state when authoritative dataset is absent.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    operational_border_available: bool = Field(
        description="Whether an authoritative operational border geometry is loaded"
    )
    authoritative_source_name: Optional[str] = Field(
        default=None,
        description="Designated authority (e.g. 'Survey of India official boundary')",
    )
    status_message: str = Field(description="Operational status description")
    notes: str = Field(description="Border intelligence operational limitations")
