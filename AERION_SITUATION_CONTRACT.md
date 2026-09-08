# AERION — SITUATION CONTRACT SPECIFICATION
## Phase 2.3 Operational Intelligence & Situation Engine Contracts
**Baseline**: Commit `c3ab984` | **Status**: ARCHITECTURE SPECIFICATION ONLY (ML Frozen, Backend Not Implemented)

---

## 1. Executive Overview & Design Principles

This document defines the authoritative, typed data contracts for the **AERION Situation Engine** and **Evidence Layer**. All interfaces are specified in:
1. **JSON Schema (Draft 2020-12)**
2. **Python Typed Contracts (Pydantic v2 / Dataclasses)**
3. **TypeScript v5 Interface Definitions**

### Core Invariants Enforced by These Contracts
1. **Zero Fabrication Invariant**: No field may contain fabricated, placeholder, or defaulted real-world coordinates, weather readings, or risk assessments. Missing data must be explicitly represented via nullable fields or status enumerations (`UNAVAILABLE`, `NOT_RECORDED`, `PENDING_GEOREFERENCE`).
2. **Coordinate Separation Invariant**: Pixel coordinates (`PixelPolygon`, `PixelPoint`) and Geospatial coordinates (`GeoPolygon`, `GeoPoint` in EPSG:4326) are strictly separate types and never mixed.
3. **Evidence Provenance Invariant**: Every assessment, event, detection, and summary metric must link back to one or more `evidence_ids` in an immutable `EvidenceRecord`.
4. **Border Terminology Invariant**: Unauthorized border movements are labeled `POTENTIAL_UNAUTHORIZED_CROSSING_INDICATOR` or `UNIDENTIFIED_CROSSING_INDICATOR`. The term `CONFIRMED_INFILTRATION` is strictly prohibited without independent ground confirmation.
5. **Disaster Observation Invariant**: All disaster metrics must declare their derivation modality: `OBSERVED`, `DERIVED`, `EXTERNALLY_PROVIDED`, `ESTIMATED`, or `UNAVAILABLE`.
6. **Mistral AI Advisory Boundary**: Mistral outputs are restricted to `executive_advisory` and `advisory_notes`. Mistral never generates detections, coordinates, counts, or risk scores.
7. **Road Accessibility & Blockage Invariant**: The damage model detects structural damage but does NOT independently prove that a road is blocked. The system strictly distinguishes `damage_detected`, `road_accessibility_assessment`, and `confirmed_road_blockage`. Damage near a road must never automatically set `road_blocked = true`. In the absence of corroborating real road/blockage/hazard evidence, the system marks `road_status = UNKNOWN` or `UNAVAILABLE`.

---

## 2. Common Types & Enumerations

### 2.1 Enumerations (Python & TypeScript)

```python
from enum import Enum
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

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

class MovementClassification(str, Enum):
    STATIONARY = "STATIONARY"
    CONVERGING_ON_LINE = "CONVERGING_ON_LINE"
    PARALLEL_PATROL = "PARALLEL_PATROL"
    DEEP_TERRAIN_INGRESS = "DEEP_TERRAIN_INGRESS"
    UNKNOWN = "UNKNOWN"
```

### 2.2 TypeScript Definitions for Common Types

```typescript
export type Modality = "OBSERVED" | "DERIVED" | "EXTERNALLY_PROVIDED" | "ESTIMATED" | "UNAVAILABLE";

export type EvidenceSourceType = 
  | "FROZEN_MODEL_VISDRONE_YOLO"
  | "FROZEN_MODEL_UNIFIED_DRONE_YOLO"
  | "FROZEN_MODEL_DOTA_OBB_YOLO"
  | "FROZEN_MODEL_SIAMESE_DAMAGE"
  | "DRONE_TELEMETRY"
  | "SATELLITE_METADATA"
  | "EXIF_GEOTAG"
  | "WEATHER_API"
  | "ROUTING_ENGINE"
  | "SHELTER_REGISTRY"
  | "ELEVATION_API"
  | "MAP_TILE_PROVIDER"
  | "OPERATOR_INPUT";

export type VerificationState = "UNVERIFIED" | "CALCULATED" | "CORROBORATED" | "GROUND_CONFIRMED" | "REJECTED";
export type OperationMode = "BORDER_SECURITY" | "DISASTER_RESPONSE";
export type TemporalMode = "LIVE_STREAM" | "RECORDED_FOOTAGE" | "STATIC_IMAGE" | "TIME_SERIES";
export type ThreatLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | "UNKNOWN";
export type DisasterType = "EARTHQUAKE" | "FLOOD" | "WILDFIRE" | "CYCLONE" | "LANDSLIDE" | "INDUSTRIAL_ACCIDENT" | "UNKNOWN";
export type RouteType = "FASTEST_FEASIBLE" | "SAFEST_FEASIBLE";
export type RouteStatus = "ACTIVE" | "BLOCKED" | "DEGRADED" | "UNAVAILABLE";
export type ShelterStatus = "OPEN" | "APPROACHING_CAPACITY" | "FULL" | "DAMAGED_CLOSED" | "UNKNOWN";
export type MovementClassification = "STATIONARY" | "CONVERGING_ON_LINE" | "PARALLEL_PATROL" | "DEEP_TERRAIN_INGRESS" | "UNKNOWN";

export interface GeoPoint {
  latitude: number;   // WGS-84 decimal degrees [-90.0, 90.0]
  longitude: number;  // WGS-84 decimal degrees [-180.0, 180.0]
  altitude_m?: number | null;
}

export interface PixelPoint {
  x: number;          // Pixel X coordinate [0.0, width]
  y: number;          // Pixel Y coordinate [0.0, height]
}

export interface GeoPolygon {
  type: "Polygon";
  coordinates: [number, number][][]; // [longitude, latitude] pairs in EPSG:4326
}

export interface PixelBoundingBox {
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
  confidence: number;
  class_name: string;
}
```

---

## 3. Evidence Layer Contract (`EvidenceRecord`)

The `EvidenceRecord` is the atomic, immutable building block for all situation inferences.

### 3.1 Python Pydantic Model

```python
class EvidenceRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str = Field(description="UUID v4 uniquely identifying this evidence record")
    parent_evidence_ids: List[str] = Field(default_factory=list, description="IDs of ancestor evidence records used in derivation")
    source_type: EvidenceSourceType = Field(description="Originating source system or model")
    created_at_utc: datetime = Field(description="UTC timestamp when evidence was ingested/produced")
    asset_timestamp_utc: Optional[datetime] = Field(default=None, description="Actual frame/capture timestamp (critical for recorded assets)")
    temporal_mode: TemporalMode = Field(description="Temporal characteristic of the source stream")
    
    # Coordinate References
    crs: Optional[str] = Field(default=None, description="Coordinate Reference System, e.g. 'EPSG:4326'. None if pixel only")
    geo_location: Optional[GeoPoint] = Field(default=None, description="Geospatial anchor if verified")
    geo_footprint: Optional[GeoPolygon] = Field(default=None, description="Geospatial boundary if calibrated")
    pixel_bbox: Optional[PixelBoundingBox] = Field(default=None, description="Raw bounding box in frame space")
    pixel_polygon: Optional[List[PixelPoint]] = Field(default=None, description="OBB or segmentation mask in pixel space")
    
    # Provenance & Quality
    raw_payload_uri: Optional[str] = Field(default=None, description="S3/Storage URI of raw source asset or inference output")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score from source model or provider")
    verification_state: VerificationState = Field(default=VerificationState.UNVERIFIED)
    modality: Modality = Field(description="Epistemological derivation modality")
    sensor_metadata: Dict[str, Any] = Field(default_factory=dict, description="Camera, focal length, altitude, GSD, or weather API meta")
```

### 3.2 JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://aerion.io/schemas/v1/evidence-record.json",
  "title": "EvidenceRecord",
  "type": "object",
  "required": [
    "evidence_id",
    "parent_evidence_ids",
    "source_type",
    "created_at_utc",
    "temporal_mode",
    "confidence",
    "verification_state",
    "modality"
  ],
  "properties": {
    "evidence_id": { "type": "string", "format": "uuid" },
    "parent_evidence_ids": { "type": "array", "items": { "type": "string", "format": "uuid" } },
    "source_type": { "$ref": "#/$defs/EvidenceSourceType" },
    "created_at_utc": { "type": "string", "format": "date-time" },
    "asset_timestamp_utc": { "type": ["string", "null"], "format": "date-time" },
    "temporal_mode": { "$ref": "#/$defs/TemporalMode" },
    "crs": { "type": ["string", "null"] },
    "geo_location": { "$ref": "#/$defs/GeoPoint" },
    "geo_footprint": { "$ref": "#/$defs/GeoPolygon" },
    "pixel_bbox": { "$ref": "#/$defs/PixelBoundingBox" },
    "confidence": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
    "verification_state": { "$ref": "#/$defs/VerificationState" },
    "modality": { "$ref": "#/$defs/Modality" },
    "sensor_metadata": { "type": "object" }
  },
  "additionalProperties": false
}
```

---

## 4. Situation State & Situation Event Contracts

The **Situation Engine** maintains a mutable working `SituationState` backed by an append-only sequence of immutable `SituationEvent` objects.

### 4.1 Situation Event Contract

```python
class SituationEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str = Field(description="UUID v4 of the situation event")
    situation_id: str = Field(description="UUID v4 of the parent situation")
    sequence_number: int = Field(ge=1, description="Monotonically increasing sequence number")
    event_timestamp_utc: datetime = Field(description="Event production timestamp")
    event_type: str = Field(description="Canonical event identifier, e.g., 'PERIMETER_ANOMALY_DETECTED', 'ROUTE_BLOCKED_IDENTIFIED'")
    threat_level: ThreatLevel = Field(description="Assessed event severity")
    evidence_ids: List[str] = Field(min_length=1, description="Causal evidence IDs supporting this event")
    
    # Event Geospatial Payload
    geo_point: Optional[GeoPoint] = Field(default=None)
    sector_id: Optional[str] = Field(default=None)
    
    # Descriptive & Structured Details
    description: str = Field(description="Deterministic human-readable event summary")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event-specific parameters, e.g. velocity, class distribution, damage index")
```

### 4.2 Situation State (Mutable Engine Frame)

```python
class SectorVulnerabilitySummary(BaseModel):
    sector_id: str
    sector_name: str
    vulnerability_score: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Null if required inputs are missing/unverified")
    vulnerability_status: str = Field(default="INSUFFICIENT_EVIDENCE", description="'CALCULATED', 'INSUFFICIENT_EVIDENCE', or 'UNAVAILABLE'")
    contributing_factors: Dict[str, Any] = Field(default_factory=dict, description="Factor breakdown: status ('VERIFIED', 'UNAVAILABLE', 'UNVERIFIED') and value")
    threat_level: ThreatLevel
    active_indicators_count: int = Field(ge=0)
    last_observation_utc: Optional[datetime] = None
    sensor_coverage_status: str = Field(description="'NOMINAL', 'DEGRADED', or 'BLIND_SPOT'")

class SituationState(BaseModel):
    situation_id: str = Field(description="UUID v4 of the active situation")
    mode: OperationMode = Field(description="Active operation mode")
    temporal_mode: TemporalMode = Field(description="Temporal mode of processing")
    session_id: str = Field(description="Associated user session or mission run")
    created_at_utc: datetime
    updated_at_utc: datetime
    active_frame_index: int = Field(default=0, ge=0)
    
    # Operational Status
    is_active: bool = Field(default=True)
    overall_threat_level: ThreatLevel = Field(default=ThreatLevel.LOW)
    overall_score: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Null if insufficient evidence; Vulnerability or Severity index")
    overall_score_status: str = Field(default="CALCULATED", description="'CALCULATED', 'INSUFFICIENT_EVIDENCE', or 'UNAVAILABLE'")
    
    # Active Aggregations
    active_evidence_count: int = Field(default=0, ge=0)
    active_event_count: int = Field(default=0, ge=0)
    latest_event_id: Optional[str] = None
    
    # Sector States
    sectors: List[SectorVulnerabilitySummary] = Field(default_factory=list)
```

---

## 5. Border Situation Report Contract (`BorderSituationReport`)

Full JSON specification of the deterministic report synthesized for Border Security mode.

### 5.1 JSON Payload Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://aerion.io/schemas/v1/border-situation-report.json",
  "title": "BorderSituationReport",
  "type": "object",
  "required": [
    "report_id",
    "situation_id",
    "generated_at_utc",
    "operation_mode",
    "temporal_mode",
    "tactical_overview",
    "detections_summary",
    "potential_unauthorized_crossing_indicators",
    "sector_assessments",
    "environmental_impact",
    "mistral_advisory",
    "evidence_manifest",
    "confidence_and_limitations"
  ],
  "properties": {
    "report_id": { "type": "string", "format": "uuid" },
    "situation_id": { "type": "string", "format": "uuid" },
    "session_id": { "type": "string", "format": "uuid" },
    "generated_at_utc": { "type": "string", "format": "date-time" },
    "operation_mode": { "type": "string", "const": "BORDER_SECURITY" },
    "temporal_mode": { "$ref": "#/$defs/TemporalMode" },
    "tactical_overview": {
      "type": "object",
      "required": ["threat_level", "sectors_monitored_count", "high_risk_sectors_count", "vulnerability_status", "contributing_factors"],
      "properties": {
        "overall_vulnerability_score": { "type": ["number", "null"], "minimum": 0.0, "maximum": 100.0 },
        "vulnerability_status": { "type": "string", "enum": ["CALCULATED", "INSUFFICIENT_EVIDENCE", "UNAVAILABLE"] },
        "contributing_factors": { "type": "object" },
        "threat_level": { "$ref": "#/$defs/ThreatLevel" },
        "sectors_monitored_count": { "type": "integer", "minimum": 0 },
        "high_risk_sectors_count": { "type": "integer", "minimum": 0 },
        "sensor_health_ratio": { "type": "number", "minimum": 0.0, "maximum": 1.0 }
      }
    },
    "detections_summary": {
      "type": "object",
      "required": ["total_detections_count", "by_class", "by_verification_state"],
      "properties": {
        "total_detections_count": { "type": "integer", "minimum": 0 },
        "by_class": {
          "type": "object",
          "properties": {
            "pedestrian": { "type": "integer", "minimum": 0 },
            "people": { "type": "integer", "minimum": 0 },
            "car": { "type": "integer", "minimum": 0 },
            "van": { "type": "integer", "minimum": 0 },
            "truck": { "type": "integer", "minimum": 0 },
            "bus": { "type": "integer", "minimum": 0 },
            "motor": { "type": "integer", "minimum": 0 },
            "bicycle": { "type": "integer", "minimum": 0 },
            "awning_tricycle": { "type": "integer", "minimum": 0 },
            "small_vehicle": { "type": "integer", "minimum": 0 },
            "large_vehicle": { "type": "integer", "minimum": 0 },
            "plane": { "type": "integer", "minimum": 0 },
            "ship": { "type": "integer", "minimum": 0 },
            "helicopter": { "type": "integer", "minimum": 0 }
          }
        },
        "by_verification_state": {
          "type": "object",
          "properties": {
            "UNVERIFIED": { "type": "integer", "minimum": 0 },
            "CALCULATED": { "type": "integer", "minimum": 0 },
            "CORROBORATED": { "type": "integer", "minimum": 0 },
            "GROUND_CONFIRMED": { "type": "integer", "minimum": 0 }
          }
        }
      }
    },
    "potential_unauthorized_crossing_indicators": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "indicator_id",
          "evidence_ids",
          "detection_timestamp_utc",
          "sector_id",
          "classification",
          "threat_level",
          "distance_to_border_meters",
          "movement_state"
        ],
        "properties": {
          "indicator_id": { "type": "string", "format": "uuid" },
          "evidence_ids": { "type": "array", "items": { "type": "string", "format": "uuid" } },
          "detection_timestamp_utc": { "type": "string", "format": "date-time" },
          "sector_id": { "type": "string" },
          "geo_coordinate": { "$ref": "#/$defs/GeoPoint" },
          "pixel_coordinate": { "$ref": "#/$defs/PixelPoint" },
          "classification": { "type": "string" },
          "confidence": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
          "threat_level": { "$ref": "#/$defs/ThreatLevel" },
          "distance_to_border_meters": { "type": ["number", "null"] },
          "movement_state": { "$ref": "#/$defs/MovementClassification" },
          "velocity_estimate_mps": { "type": ["number", "null"] },
          "terrain_concealment_factor": { "type": "number", "minimum": 0.0, "maximum": 1.0 }
        }
      }
    },
    "sector_assessments": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["sector_id", "sector_name", "vulnerability_status", "contributing_factors", "threat_level", "active_indicators_count", "sensor_coverage_status"],
        "properties": {
          "sector_id": { "type": "string" },
          "sector_name": { "type": "string" },
          "vulnerability_score": { "type": ["number", "null"], "minimum": 0.0, "maximum": 100.0 },
          "vulnerability_status": { "type": "string", "enum": ["CALCULATED", "INSUFFICIENT_EVIDENCE", "UNAVAILABLE"] },
          "contributing_factors": { "type": "object" },
          "threat_level": { "$ref": "#/$defs/ThreatLevel" },
          "active_indicators_count": { "type": "integer", "minimum": 0 },
          "sensor_coverage_status": { "type": "string", "enum": ["NOMINAL", "DEGRADED", "BLIND_SPOT"] },
          "terrain_difficulty": { "type": "string", "enum": ["OPEN", "RUGGED", "DENSE_VEGETATION", "MOUNTAINOUS", "WATER_CROSSING", "UNAVAILABLE"] },
          "recommendation": { "type": "string" }
        }
      }
    },
    "environmental_impact": {
      "type": "object",
      "required": ["weather_available", "flight_suitability"],
      "properties": {
        "weather_available": { "type": "boolean" },
        "observation": { "$ref": "#/$defs/WeatherObservation" },
        "flight_suitability": { "type": "string", "enum": ["OPTIMAL", "MARGINAL", "GROUNDED", "UNAVAILABLE"] },
        "infrared_crossover_risk": { "type": ["boolean", "null"], "description": "Null if thermal hardware absent; FUTURE / NOT IMPLEMENTED" },
        "visibility_impact": { "type": "string" }
      }
    },
    "mistral_advisory": {
      "type": "object",
      "required": ["advisory_id", "generated_at_utc", "model_version", "tactical_advisory_text", "recommended_action_priority"],
      "properties": {
        "advisory_id": { "type": "string", "format": "uuid" },
        "generated_at_utc": { "type": "string", "format": "date-time" },
        "model_version": { "type": "string", "example": "open-mistral-nemo" },
        "tactical_advisory_text": { "type": "string", "maxLength": 1000 },
        "recommended_action_priority": {
          "type": "array",
          "items": { "type": "string" }
        },
        "advisory_disclaimer": {
          "type": "string",
          "const": "AI advisory is derived from automated sensor feeds and deterministic risk thresholds. Tactical deployment decisions require human operator verification."
        }
      }
    },
    "evidence_manifest": {
      "type": "object",
      "required": ["total_records", "evidence_ids", "source_breakdown"],
      "properties": {
        "total_records": { "type": "integer", "minimum": 0 },
        "evidence_ids": { "type": "array", "items": { "type": "string", "format": "uuid" } },
        "source_breakdown": { "type": "object" }
      }
    },
    "confidence_and_limitations": {
      "type": "object",
      "required": ["overall_confidence", "unverified_detections_count", "blind_spots", "data_quality_flags"],
      "properties": {
        "overall_confidence": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
        "unverified_detections_count": { "type": "integer", "minimum": 0 },
        "blind_spots": { "type": "array", "items": { "type": "string" } },
        "data_quality_flags": { "type": "array", "items": { "type": "string" } }
      }
    }
  },
  "additionalProperties": false
}
```

---

## 6. Disaster Situation Report Contract (`DisasterSituationReport`)

Full JSON specification of the deterministic report synthesized for Disaster Response mode.

### 6.1 JSON Payload Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://aerion.io/schemas/v1/disaster-situation-report.json",
  "title": "DisasterSituationReport",
  "type": "object",
  "required": [
    "report_id",
    "situation_id",
    "generated_at_utc",
    "operation_mode",
    "temporal_mode",
    "disaster_assessment",
    "infrastructure_damage",
    "evacuation_routes",
    "shelter_assessments",
    "environmental_conditions",
    "mistral_advisory",
    "evidence_manifest",
    "confidence_and_limitations"
  ],
  "properties": {
    "report_id": { "type": "string", "format": "uuid" },
    "situation_id": { "type": "string", "format": "uuid" },
    "session_id": { "type": "string", "format": "uuid" },
    "generated_at_utc": { "type": "string", "format": "date-time" },
    "operation_mode": { "type": "string", "const": "DISASTER_RESPONSE" },
    "temporal_mode": { "$ref": "#/$defs/TemporalMode" },
    "disaster_assessment": {
      "type": "object",
      "required": ["disaster_type", "severity_score", "threat_level", "affected_area_sq_km", "affected_area_modality"],
      "properties": {
        "disaster_type": { "$ref": "#/$defs/DisasterType" },
        "severity_score": { "type": "number", "minimum": 0.0, "maximum": 100.0 },
        "threat_level": { "$ref": "#/$defs/ThreatLevel" },
        "affected_area_sq_km": { "type": ["number", "null"] },
        "affected_area_modality": { "$ref": "#/$defs/Modality" },
        "active_hazard_zones_count": { "type": "integer", "minimum": 0 },
        "critical_infrastructure_risk_level": { "$ref": "#/$defs/ThreatLevel" }
      }
    },
    "infrastructure_damage": {
      "type": "object",
      "required": ["siamese_damage_evaluations_count", "damage_index_mean", "by_structural_state", "blocked_road_segments_count"],
      "properties": {
        "siamese_damage_evaluations_count": { "type": "integer", "minimum": 0 },
        "damage_index_mean": { "type": ["number", "null"], "minimum": 0.0, "maximum": 1.0 },
        "by_structural_state": {
          "type": "object",
          "properties": {
            "undamaged": { "type": "integer", "minimum": 0 },
            "minor_damage": { "type": "integer", "minimum": 0 },
            "major_damage": { "type": "integer", "minimum": 0 },
            "destroyed": { "type": "integer", "minimum": 0 }
          }
        },
        "blocked_road_segments_count": { "type": "integer", "minimum": 0 },
        "blocked_segments_modality": { "$ref": "#/$defs/Modality" }
      }
    },
    "evacuation_routes": {
      "type": "array",
      "items": { "$ref": "#/$defs/RouteAssessment" }
    },
    "shelter_assessments": {
      "type": "array",
      "items": { "$ref": "#/$defs/Shelter" }
    },
    "environmental_conditions": {
      "type": "object",
      "required": ["weather_available", "flight_suitability", "hazard_dispersion_direction_deg"],
      "properties": {
        "weather_available": { "type": "boolean" },
        "observation": { "$ref": "#/$defs/WeatherObservation" },
        "flight_suitability": { "type": "string", "enum": ["OPTIMAL", "MARGINAL", "GROUNDED", "UNAVAILABLE"] },
        "hazard_dispersion_direction_deg": { "type": ["number", "null"] },
        "adverse_conditions": { "type": "array", "items": { "type": "string" } }
      }
    },
    "mistral_advisory": {
      "type": "object",
      "required": ["advisory_id", "generated_at_utc", "model_version", "disaster_response_summary", "civil_protection_priorities"],
      "properties": {
        "advisory_id": { "type": "string", "format": "uuid" },
        "generated_at_utc": { "type": "string", "format": "date-time" },
        "model_version": { "type": "string", "example": "open-mistral-nemo" },
        "disaster_response_summary": { "type": "string", "maxLength": 1200 },
        "civil_protection_priorities": { "type": "array", "items": { "type": "string" } },
        "advisory_disclaimer": {
          "type": "string",
          "const": "AI advisory is synthesized from automated visual inspection and live open data. Evacuation routing and shelter commands must be verified by on-scene incident commanders."
        }
      }
    },
    "evidence_manifest": {
      "type": "object",
      "required": ["total_records", "evidence_ids", "source_breakdown"],
      "properties": {
        "total_records": { "type": "integer", "minimum": 0 },
        "evidence_ids": { "type": "array", "items": { "type": "string", "format": "uuid" } },
        "source_breakdown": { "type": "object" }
      }
    },
    "confidence_and_limitations": {
      "type": "object",
      "required": ["overall_confidence", "routing_data_status", "shelter_data_status", "unverified_damage_sites_count"],
      "properties": {
        "overall_confidence": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
        "routing_data_status": { "type": "string", "enum": ["LIVE_GRAPH_CONFIRMED", "DEGRADED_FALLBACK", "UNAVAILABLE"] },
        "shelter_data_status": { "type": "string", "enum": ["VERIFIED_REGISTRY", "STALE_REGISTRY", "UNAVAILABLE"] },
        "unverified_damage_sites_count": { "type": "integer", "minimum": 0 },
        "data_quality_flags": { "type": "array", "items": { "type": "string" } }
      }
    }
  },
  "additionalProperties": false
}
```

---

## 7. External Service Integration Contracts

### 7.1 Weather Observation Contract (`WeatherObservation`)

```python
class WeatherObservation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    observation_id: str = Field(description="UUID v4 of weather capture")
    provider_name: str = Field(description="e.g. Open-Meteo, NOAA")
    observation_timestamp_utc: datetime = Field(description="Actual meteorological reading timestamp")
    is_historical_reconstructed: bool = Field(description="True if historical weather fetched for recorded asset timestamp")
    
    # Location Anchor
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    
    # Physical Measurements
    temperature_celsius: Optional[float] = None
    wind_speed_mps: Optional[float] = None
    wind_gust_mps: Optional[float] = None
    wind_direction_deg: Optional[float] = Field(default=None, ge=0.0, le=360.0)
    visibility_meters: Optional[float] = Field(default=None, ge=0.0)
    precipitation_mm_hr: Optional[float] = Field(default=None, ge=0.0)
    cloud_cover_percentage: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    relative_humidity_percentage: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    barometric_pressure_hpa: Optional[float] = None
    
    # Operational Derivations
    flight_suitability: str = Field(description="'OPTIMAL', 'MARGINAL', 'GROUNDED', or 'UNAVAILABLE'")
    ground_trafficability_index: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="1.0 = dry/firm, 0.0 = impassable mud/flood")
    infrared_crossover_warning: bool = Field(default=False, description="True during thermal crossover periods (dawn/dusk)")
```

### 7.2 Route Assessment Contract (`RouteAssessment`)

```python
class RouteSegment(BaseModel):
    segment_index: int
    name: str
    distance_meters: float
    duration_seconds: float
    is_blocked: bool
    hazard_proximity_meters: Optional[float]
    geo_line: List[GeoPoint]

class RouteAssessment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    route_id: str = Field(description="UUID v4 of assessed route")
    route_type: RouteType = Field(description="FASTEST_FEASIBLE or SAFEST_FEASIBLE")
    status: RouteStatus = Field(description="ACTIVE, BLOCKED, DEGRADED, or UNAVAILABLE")
    origin: GeoPoint
    destination: GeoPoint
    destination_shelter_id: Optional[str] = None
    
    # Quantitative Routing Metrics
    total_distance_meters: Optional[float] = None
    total_duration_seconds: Optional[float] = None
    elevation_gain_meters: Optional[float] = None
    
    # Road Network & Hazard Interaction
    hazards_avoided_count: int = Field(default=0, ge=0)
    critical_narrow_passes_count: int = Field(default=0, ge=0)
    road_segments: List[RouteSegment] = Field(default_factory=list)
    geometry_geojson: Optional[Dict[str, Any]] = Field(default=None, description="GeoJSON LineString (EPSG:4326)")
    
    # Evidence & Routing Engine Provenance
    routing_engine_name: str = Field(description="e.g. openrouteservice, osrm, valhalla")
    engine_response_timestamp_utc: datetime
    evidence_ids: List[str] = Field(min_length=1, description="Evidence records (hazard zones, damaged nodes) used in route synthesis")
```

### 7.3 Shelter & Hazard Zone Contracts

```python
class Shelter(BaseModel):
    shelter_id: str
    name: str
    geo_location: GeoPoint
    status: ShelterStatus
    capacity_total: int = Field(ge=0)
    capacity_occupied: int = Field(ge=0)
    is_generator_powered: bool
    medical_support_available: bool
    last_reported_utc: datetime
    modality: Modality
    source_registry: str

class HazardZone(BaseModel):
    hazard_id: str
    hazard_type: str = Field(description="'FLOOD_POLYGON', 'FIRE_PERIMETER', 'COLLAPSED_STRUCTURE_BUFFER', 'UNEXPLODED_ORDNANCE'")
    threat_level: ThreatLevel
    geo_boundary: GeoPolygon
    identified_at_utc: datetime
    active: bool
    evidence_ids: List[str]
```

---

## 8. Map Rendering Contract (`MapLayerCollection`)

The Next.js frontend map engine (Mapbox GL JS / Deck.gl) requires strictly standardized GeoJSON FeatureCollections with embedded tactical styling properties.

```typescript
export interface TacticalStyle {
  "circle-color"?: string;
  "circle-radius"?: number;
  "circle-stroke-width"?: number;
  "circle-stroke-color"?: string;
  "fill-color"?: string;
  "fill-opacity"?: number;
  "line-color"?: string;
  "line-width"?: number;
  "line-dasharray"?: number[];
  "icon-image"?: string;
}

export interface TacticalFeatureProperties {
  feature_id: string;
  feature_type: "DETECTION" | "HAZARD_ZONE" | "ROUTE" | "SHELTER" | "SECTOR_BOUNDARY";
  evidence_ids: string[];
  threat_level?: ThreatLevel;
  confidence?: number;
  label: string;
  tooltip_markdown: string;
  style: TacticalStyle;
  [key: string]: any;
}

export interface TacticalFeatureCollection {
  type: "FeatureCollection";
  layer_id: string;
  layer_name: string;
  visible_by_default: boolean;
  features: Array<{
    type: "Feature";
    id: string;
    geometry: {
      type: "Point" | "MultiPoint" | "LineString" | "MultiLineString" | "Polygon" | "MultiPolygon";
      coordinates: any;
    };
    properties: TacticalFeatureProperties;
  }>;
}

export interface MapLayerCollection {
  situation_id: string;
  updated_at_utc: string;
  crs: "EPSG:4326";
  layers: {
    detection_layer: TacticalFeatureCollection;
    hazard_layer: TacticalFeatureCollection;
    route_layer: TacticalFeatureCollection;
    shelter_layer: TacticalFeatureCollection;
    sector_layer: TacticalFeatureCollection;
  };
}
```

---

## 9. Live WebSocket Telemetry Contract (`LiveWebSocketSituationMessage`)

Real-time situation updates transmitted over `WSS /api/v1/ws/situations/{id}`.

### 9.1 WebSocket Message Union (TypeScript)

```typescript
export type WebSocketMessageType = 
  | "SITUATION_FRAME_UPDATE"
  | "EVIDENCE_INGESTED"
  | "EVENT_TRIGGERED"
  | "METRIC_ALERT"
  | "ADVISORY_GENERATED"
  | "HEARTBEAT";

export interface BaseWebSocketMessage {
  message_id: string;
  timestamp_utc: string;
  situation_id: string;
  message_type: WebSocketMessageType;
}

export interface SituationFrameUpdateMessage extends BaseWebSocketMessage {
  message_type: "SITUATION_FRAME_UPDATE";
  payload: {
    frame_index: number;
    active_threat_level: ThreatLevel;
    active_score: number;
    new_detections_count: number;
    new_evidence_count: number;
  };
}

export interface EvidenceIngestedMessage extends BaseWebSocketMessage {
  message_type: "EVIDENCE_INGESTED";
  payload: {
    evidence_id: string;
    source_type: EvidenceSourceType;
    confidence: number;
    verification_state: VerificationState;
    has_georeference: boolean;
  };
}

export interface EventTriggeredMessage extends BaseWebSocketMessage {
  message_type: "EVENT_TRIGGERED";
  payload: {
    event_id: string;
    event_type: string;
    threat_level: ThreatLevel;
    description: string;
    geo_point?: GeoPoint | null;
  };
}

export interface AdvisoryGeneratedMessage extends BaseWebSocketMessage {
  message_type: "ADVISORY_GENERATED";
  payload: {
    advisory_id: string;
    advisory_text: string;
    priorities: string[];
    generated_at_utc: string;
  };
}

export interface HeartbeatMessage extends BaseWebSocketMessage {
  message_type: "HEARTBEAT";
  payload: {
    server_time_utc: string;
    connected_clients: number;
    engine_state: "RUNNING" | "DEGRADED" | "IDLE";
  };
}

export type LiveWebSocketSituationMessage =
  | SituationFrameUpdateMessage
  | EvidenceIngestedMessage
  | EventTriggeredMessage
  | AdvisoryGeneratedMessage
  | HeartbeatMessage;
```

---

## 10. Data Quality & Degraded Modes Contract

To guarantee operational transparency under adverse network or sensor conditions, every situation response includes a standardized `DegradedModeStatus` object.

```python
class DegradedModeStatus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    is_degraded: bool = Field(description="True if any sub-service is operating in fallback or unavailable state")
    active_fallbacks: List[str] = Field(default_factory=list, description="List of active fallback mechanisms, e.g. 'OFFLINE_ROUTING_FALLBACK'")
    
    # Subsystem Availability & Verification States
    geographic_status: str = Field(default="VERIFIED", description="'VERIFIED', 'UNVERIFIED' (untrusted/spoofed/uncalibrated), or 'UNAVAILABLE'")
    terrain_status: str = Field(default="AVAILABLE", description="'AVAILABLE' or 'UNAVAILABLE' (DEM missing; never assumed flat)")
    vulnerability_status: str = Field(default="CALCULATED", description="'CALCULATED', 'INSUFFICIENT_EVIDENCE', or 'UNAVAILABLE'")
    
    # Subsystem Availability Flags
    weather_service_available: bool = True
    elevation_service_available: bool = True
    routing_engine_available: bool = True
    shelter_registry_available: bool = True
    map_tiles_available: bool = True
    gpu_inference_available: bool = True
    mistral_advisory_available: bool = True
    
    # Operational Guidance for Operator
    degraded_warning_messages: List[str] = Field(default_factory=list)
```

---

## 11. Architectural Verification & Compliance Checklist

| Contract Requirement | Specification Section | Verification Rule |
| :--- | :--- | :--- |
| **Strict Coordinate Separation** | Section 2.2, 3.1 | `GeoPoint` (lat/lon) and `PixelPoint` (x/y) cannot be cast implicitly. |
| **Evidence Traceability** | Section 3.1, 4.1, 5.1 | Every situation event and report detection must contain at least one valid UUID in `evidence_ids`. |
| **No Infiltration Fabrication** | Section 2.1, 5.1 | Border events use `POTENTIAL_UNAUTHORIZED_CROSSING_INDICATOR`. `CONFIRMED_INFILTRATION` rejected without ground confirmation. |
| **Evacuation Route Routing** | Section 7.2 | Evacuation routes require real routing engine (`openrouteservice`). Euclidean straight lines are illegal. |
| **Historical Weather Honored** | Section 7.1 | Recorded footage checks `is_historical_reconstructed` and matches asset timestamp. |
| **Mistral Bounded to Advisory** | Section 5.1, 6.1 | Mistral generates only text advice. Detections, counts, and scores originate exclusively from deterministic code. |
| **Hardware Boundary** | Section 10 | 6 GB VRAM budget strictly monitored; degraded status signals GPU pressure. |
| **No Silent Vulnerability Defaults**| Section 4.2, 5.1 | If required score inputs are missing, `vulnerability_score = null` and `vulnerability_status = "INSUFFICIENT_EVIDENCE"`. Never silently defaults to zero. |
| **GPS Untrusted / Spoofed Rule** | Section 10 | When GPS is untrusted or missing, `geographic_status = UNVERIFIED` and system operates strictly in Cartesian pixel space. Visual odometry is `FUTURE / NOT IMPLEMENTED`. |
| **DEM Unavailable Rule** | Section 10 | When DEM is missing, `terrain_status = UNAVAILABLE`. Never assumes flat terrain. |
| **Real-Data Invariant on Fallbacks**| Section 10, 11 | Every fallback must either use independently verified data or mark capability `UNAVAILABLE` / `UNVERIFIED`. No fake data substituted. |

---
**End of AERION Situation Contract Specification**
