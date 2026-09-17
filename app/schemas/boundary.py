"""
AERION — Boundary Domain Abstraction & Contracts (Phase D)
Provides a reusable boundary abstraction supporting:
- DEMO_VULNERABILITY_BOUNDARY (Synthetic Pentagon, strictly non-authoritative)
- OPERATIONAL_GEOFENCE (Tactical sensor boundary)
- INTERNATIONAL_BORDER (Authoritative national border)
- ADMINISTRATIVE_BOUNDARY (Survey of India / LGD administrative boundaries)

Zero-fabrication invariant:
- Demo Pentagon is never classified as an international border or administrative boundary.
- Evidence-gating: Vulnerability requires legitimate intersecting evidence.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BoundaryType(str, Enum):
    DEMO_VULNERABILITY_BOUNDARY = "DEMO_VULNERABILITY_BOUNDARY"
    OPERATIONAL_GEOFENCE = "OPERATIONAL_GEOFENCE"
    INTERNATIONAL_BORDER = "INTERNATIONAL_BORDER"
    ADMINISTRATIVE_BOUNDARY = "ADMINISTRATIVE_BOUNDARY"


class BoundaryAuthority(str, Enum):
    NON_AUTHORITATIVE = "NON_AUTHORITATIVE"
    OFFICIAL_SOURCE = "OFFICIAL_SOURCE"
    OPERATIONAL_LOCAL = "OPERATIONAL_LOCAL"


class BoundaryProvenance(str, Enum):
    SYNTHETIC_AERION_DEMO = "SYNTHETIC_AERION_DEMO"
    SURVEY_OF_INDIA = "SURVEY_OF_INDIA"
    OPERATOR_CONFIGURED = "OPERATOR_CONFIGURED"


class BoundaryStatus(str, Enum):
    DEMO = "DEMO"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    UNVERIFIED = "UNVERIFIED"


class BoundaryDefinition(BaseModel):
    """
    Authoritative boundary contract.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(description="Unique machine-readable boundary identifier")
    name: str = Field(description="Display name for the boundary")
    geometry: Dict[str, Any] = Field(description="GeoJSON Geometry (Polygon or MultiPolygon)")
    boundary_type: BoundaryType = Field(description="Semantic categorization of boundary")
    authority: BoundaryAuthority = Field(description="Authority level of source data")
    provenance: BoundaryProvenance = Field(description="Provenance lineage")
    status: BoundaryStatus = Field(description="Operational status")
    description: Optional[str] = Field(default=None, description="Detailed descriptive notes")
    disclaimer: str = Field(
        default="Synthetic demonstration geometry. Non-authoritative.",
        description="Mandatory semantic disclaimer",
    )


# ============================================================================
# SYNTHETIC DEMO PENTAGON DEFINITION
# Deterministic 5-sided closed polygon in Northern Sector (Jammu reference)
# Coordinates are explicitly synthetic for testing spatial intersection.
# Coordinates format in GeoJSON: [longitude, latitude]
# Exactly 5 sides (6 coordinate tuples with first and last identical).
# ============================================================================
DEMO_PENTAGON_COORDINATES = [
    [74.80, 32.70],
    [74.90, 32.75],
    [74.95, 32.65],
    [74.88, 32.55],
    [74.78, 32.60],
    [74.80, 32.70],  # Closed 5-vertex polygon
]

DEMO_PENTAGON_BOUNDARY = BoundaryDefinition(
    id="demo-pentagon-vulnerability-01",
    name="Demo Pentagon",
    geometry={
        "type": "Polygon",
        "coordinates": [DEMO_PENTAGON_COORDINATES],
    },
    boundary_type=BoundaryType.DEMO_VULNERABILITY_BOUNDARY,
    authority=BoundaryAuthority.NON_AUTHORITATIVE,
    provenance=BoundaryProvenance.SYNTHETIC_AERION_DEMO,
    status=BoundaryStatus.DEMO,
    description="Synthetic 5-sided Area of Interest (AOI) polygon for vulnerability demonstration and spatial intersection testing.",
    disclaimer="DEMO BOUNDARY: Synthetic demonstration geometry. NON-AUTHORITATIVE. Not an international border or administrative frontier.",
)


class BoundaryEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: Optional[str] = Field(default=None, description="Analysis result ID to evaluate evidence against boundary")
    evidence_points: Optional[List[Dict[str, float]]] = Field(
        default=None,
        description="Optional list of points [{'latitude': lat, 'longitude': lon, 'weight': 1.0}] to test",
    )


class BoundaryEvaluationResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    boundary_id: str
    boundary_name: str
    boundary_type: str
    authority: str
    provenance: str
    status: str
    intersecting_evidence_count: int
    vulnerability_score: Optional[float] = None
    vulnerability_status: str = Field(description="'CALCULATED', 'INSUFFICIENT_EVIDENCE'")
    reason: str
    disclaimer: str
