"""
AERION — External Provider API Contracts & Normalized Schemas (Steps 22–23)
Defines normalized data transfer objects for Weather, Routing, and Geocoding
with strict provenance, explicit failure states, and zero-fabrication safety.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.evidence import EvidenceRecord, GeoPoint, GeoPolygon, utcnow


class ProviderStatus(str, Enum):
    """Explicit provider lifecycle and execution state."""
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    INVALID_REQUEST = "INVALID_REQUEST"
    PROVIDER_ERROR = "PROVIDER_ERROR"


# ============================================================================
# 1. NORMALIZED WEATHER CONTRACTS
# ============================================================================

class WeatherConditionClassification(str, Enum):
    OPTIMAL = "OPTIMAL"
    MARGINAL = "MARGINAL"
    GROUNDED = "GROUNDED"
    UNAVAILABLE = "UNAVAILABLE"


class NormalizedWeatherRecord(BaseModel):
    """
    Normalized weather observation conforming to Step 23 requirements.
    Zero-fabrication: unavailable fields remain None; never filled with fake data.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    observation_id: str = Field(description="Unique observation identifier")
    provider_name: str = Field(description="Source provider (e.g. Open-Meteo)")
    status: ProviderStatus = Field(default=ProviderStatus.AVAILABLE)
    observation_timestamp_utc: datetime = Field(description="Timestamp of meteorological reading")
    fetched_at_utc: datetime = Field(description="UTC timestamp when observation was retrieved")
    is_historical_reconstructed: bool = Field(default=False, description="True if historical weather for past timestamp")
    latitude: float
    longitude: float
    temperature_celsius: Optional[float] = None
    apparent_temperature_celsius: Optional[float] = None
    relative_humidity_percentage: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    precipitation_mm_hr: Optional[float] = Field(default=None, ge=0.0)
    precipitation_probability: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    weather_code: Optional[int] = None
    condition_description: Optional[str] = None
    wind_speed_mps: Optional[float] = None
    wind_direction_deg: Optional[float] = Field(default=None, ge=0.0, le=360.0)
    wind_gust_mps: Optional[float] = None
    visibility_meters: Optional[float] = Field(default=None, ge=0.0)
    cloud_cover_percentage: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    flight_suitability: WeatherConditionClassification = WeatherConditionClassification.OPTIMAL
    ground_trafficability_index: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    limitations: Optional[str] = None
    cached: bool = False
    evidence: Optional[EvidenceRecord] = None


# ============================================================================
# 2. NORMALIZED ROUTING CONTRACTS
# ============================================================================

class RouteProfile(str, Enum):
    DRIVING_CAR = "driving-car"
    EMERGENCY = "emergency"


class NormalizedRouteStep(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    step_index: int
    instruction: str
    name: str
    distance_meters: float
    duration_seconds: float


class NormalizedRouteRecord(BaseModel):
    """
    Normalized road network route assessment conforming to Step 23 requirements.
    CRITICAL INVARIANT: Zero straight-line routing. Routes are derived ONLY from genuine road graphs.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    route_id: str = Field(description="Unique route computation ID")
    provider_name: str = Field(description="Routing provider name (e.g. OpenRouteService, Mapbox)")
    status: ProviderStatus = Field(default=ProviderStatus.AVAILABLE)
    origin: GeoPoint
    destination: GeoPoint
    profile: RouteProfile = RouteProfile.DRIVING_CAR
    total_distance_meters: Optional[float] = None
    total_duration_seconds: Optional[float] = None
    elevation_ascent_meters: Optional[float] = None
    geometry_geojson: Optional[Dict[str, Any]] = None  # GeoJSON LineString
    steps: List[NormalizedRouteStep] = Field(default_factory=list)
    hazards_avoided_count: int = 0
    fetched_at_utc: datetime = Field(description="UTC timestamp when route was calculated")
    warnings: List[str] = Field(default_factory=list)
    is_evacuation_evaluated: bool = Field(default=False, description="True only if evaluated against hazard polygons")
    cached: bool = False
    evidence: Optional[EvidenceRecord] = None


# ============================================================================
# 3. NORMALIZED GEOCODING CONTRACTS
# ============================================================================

class NormalizedGeocodeResult(BaseModel):
    """
    Normalized forward or reverse geocoding result.
    Zero-fabrication: administrative boundaries are contextual metadata, not authoritative border geometry.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_name: str
    status: ProviderStatus = ProviderStatus.AVAILABLE
    query: Optional[str] = None
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    display_name: str
    locality: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    country: str = "India"
    country_code: str = "IN"
    postcode: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    fetched_at_utc: datetime
    raw_properties: Dict[str, Any] = Field(default_factory=dict)
    cached: bool = False
    evidence: Optional[EvidenceRecord] = None


# ============================================================================
# 4. NORMALIZED MISTRAL ADVISORY CONTRACTS (Step 24)
# ============================================================================

class AdvisoryPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class NormalizedAdvisoryRecord(BaseModel):
    """
    Normalized grounded advisory response conforming to Step 24 requirements.
    CRITICAL INVARIANT: Mistral is advisory only and NEVER a source of truth for detections.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    advisory_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mode: str = Field(description="'DISASTER_RESPONSE' or 'BORDER_SECURITY'")
    summary: str = Field(description="Executive concise summary of verified situation")
    priority: AdvisoryPriority = Field(default=AdvisoryPriority.MEDIUM)
    key_findings: List[str] = Field(default_factory=list, description="Findings directly tied to verified evidence")
    evidence_references: List[str] = Field(default_factory=list, description="IDs of evidence records grounding this advisory")
    recommended_actions: List[str] = Field(default_factory=list, description="Protocol-driven actionable recommendations")
    limitations: List[str] = Field(default_factory=list, description="Explicit statements of missing or unavailable data")
    generated_at_utc: datetime = Field(default_factory=utcnow)
    model: str = Field(default="open-mistral-nemo")
    provider_status: ProviderStatus = Field(default=ProviderStatus.AVAILABLE)
    grounded: bool = Field(default=True, description="Always True when strictly derived from verified AERION evidence")
    disclaimer: str = Field(
        default=(
            "AI advisory is derived from automated sensor feeds and deterministic risk thresholds. "
            "Tactical deployment and operational response decisions require human operator verification."
        )
    )

