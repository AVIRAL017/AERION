# AERION — Operational Intelligence & Situation Engine Architecture Specification

**Document Version**: 1.0.0  
**Phase**: Phase 2.3 — Operational Intelligence + Situation Engine Architecture  
**Status**: DESIGN SPECIFICATION ONLY (NO CODE IMPLEMENTATION IN THIS PHASE)  
**Baseline Git Commit**: `c3ab984`  
**Repository**: `https://github.com/AVIRAL017/AERION.git`  
**Target Milestone**: Phase 3A/3C (Evidence Layer + Situation Engine Implementation)  

---

## 1. Purpose & Architectural Vision

AERION transforms raw aerial perception into actionable, defensible, and real-world operational intelligence for two high-stakes missions:
1. **Border Security & Geofence Surveillance Mode**
2. **Disaster Response & Structural Assessment Mode**

The platform decouples raw neural evidence extraction from operational synthesis. Existing frozen machine learning models ([`visdrone_8s_1280_30ep`](file:///D:/mp-1/runs/detect/visdrone_8s_1280_30ep/weights/best.pt), [`unified_drone_20ep`](file:///D:/mp-1/runs/detect/unified_drone_20ep/weights/best.pt), [`train-6/best.pt`](file:///D:/mp-1/runs/obb/train-6/weights/best.pt), and [`best_model.pth`](file:///D:/mp-1/change_detection_runs_v2/best_model.pth)) act strictly as **immutable evidence producers**.

### 1.1 Capability Classification Taxonomy

To prevent claims of unvalidated capability, every system feature is strictly categorized into one of four states:

1. **`[IMPLEMENTED AND VALIDATED]`**: Fully implemented, passing automated tests at baseline commit `c3ab984`:
   * VisDrone YOLOv8s aerial drone detection (1280px)
   * Unified YOLOv8s aerial + maritime drone detection (1280px)
   * DOTA-v1.5 YOLOv8n-OBB oriented bounding box satellite detection (1024px)
   * Siamese ResNet18 + U-Net structural damage assessment (512px)
   * ByteTrack multi-object tracking in Cartesian image/pixel space
   * Ray-casting 2D point-in-polygon containment in pixel space
   * Background SSIM structural change matrix subtraction
   * Unified in-memory dataclass contracts and normalizers (`aerion_runtime_contracts.py`, `aerion_runtime_normalizer.py`, `aerion_orchestrator.py`)
   * Full test suite verification (26 unit and real integration tests passing)

2. **`[ARCHITECTURALLY DEFINED]`**: Thoroughly specified in formal contracts and schemas, pending implementation in scheduled backend phases:
   * Canonical Evidence Layer (`EvidenceRecord` provenance tracking)
   * Situation Engine (`SituationState`, `SituationEvent` immutable log)
   * Bounded Mistral AI advisory generation (strictly 5-6 sentences, temperature 0.20)
   * Strict coordinate separation architecture (Pixel space vs PostGIS WGS84)
   * PostgreSQL 16 + PostGIS relational/spatial schema (19 entities)
   * RESTful and WebSocket API endpoints under `/api/v1`

3. **`[REQUIRES EXTERNAL DATA]`**: Architecturally designed, but dependent on external data and credentials being collected independently by the operator:
   * Meteorological / weather feeds (Open-Meteo API credentials/endpoint)
   * Road network topological graph routing (OpenRouteService credentials/endpoint)
   * Vector and satellite map tiles (Mapbox token/credentials)
   * Civil protection emergency shelter registries, capacity, and real-time availability (authoritative municipality datasets)
   * Spatial hazard polygons and flood perimeters (India flood data, NDMA/CWC feeds)
   * Real-time road blockage feeds (external traffic / transport feeds)
   * Live drone telemetry (autopilot/MAVLink GPS, altitude, gimbal attitude for georeferencing)
   * Calibrated georeferenced imagery containing embedded CRS / transform matrices
   * Digital Elevation Models (DEM) rasters (Copernicus / SRTM for slope and line-of-sight terrain intelligence)

4. **`[FUTURE / NOT IMPLEMENTED]`**: Long-term conceptual extensions that are NOT implemented, NOT validated, and must NEVER be treated as operational fallbacks:
   * **Visual odometry navigation fallback**: No optical flow or inertial SLAM pipeline exists.
   * **Thermal / Infrared (IR) crossover & radiometry analysis**: Requires calibrated thermal camera hardware and radiometry pipeline.
   * **Automated RGB terrain intelligence without external DEM**: Terrain slope and line-of-sight cannot be inferred from RGB images alone.
   * **Longitudinal historical incident recurrence modeling**: Requires months of accumulated operational mission data in PostgreSQL.
   * **Hardware-level GPS spoofing / jamming detection**: Requires dedicated multi-constellation RF hardware.
   * **Local vLLM / self-hosted Mistral 7B inference server**: Deferred; Phase 3 uses hosted Mistral API with `open-mistral-nemo`.
   * **Distributed Celery + Redis GPU worker clusters**: Deferred to horizontal production scaling (Phase 4+).
   * **Production payment gateway recurring billing**: Deferred to commercial deployment.

---

### 1.2 The Conceptual Paradigm Shift

The legacy prototype flow:
```text
[Raw ML Output] ───► [Mistral LLM] ───► [Unstructured Narrative Report]
```
is **formally retired and replaced** by the AERION Evidence Pipeline:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           REAL EVIDENCE SOURCES                             │
│   Frozen ML Perception | Georeferenced Imagery | Weather | Roads | Hazards │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AERION EVIDENCE LAYER                             │
│       Canonical Evidence Normalization & Cryptographic Provenance Tracking   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AERION SITUATION ENGINE                            │
│     Rolling Situation State (Mutable)  │  Immutable Event Log (Audit Trail) │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DETERMINISTIC ANALYTICS                           │
│   Ray-Casting Containment | Threat Vectoring | SSIM Damage | Risk Formulations │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          OPERATIONAL INTELLIGENCE                           │
│   Evacuation Routing Analysis | Vulnerability Triage | Shelter Allocation   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STRUCTURED SITUATION REPORT (JSON)                       │
│             Authoritative, Defensible, Machine-Readable Contract            │
└───────────────────┬─────────────────────────────────────┬───────────────────┘
                    ▼                                     ▼
┌────────────────────────────────────────┐ ┌──────────────────────────────────┐
│          MISTRAL AI ADVISORY           │ │    DASHBOARD / OPERATOR UI       │
│  Explanatory Prose Grounded in Evidence│ │ Vector Map Layers | Alert Feed   │
└────────────────────────────────────────┘ └──────────────────────────────────┘
```

> [!IMPORTANT]
> **Mistral AI is NOT the source of truth.**  
> The structured operational report generated by the Situation Engine is the authoritative system output. Mistral provides plain-language operator explanations and tactical recommendations derived solely from verified and mathematically calculated operational evidence.

---

## 2. The AERION Real-Data Invariant

To ensure reliability in life-critical defense and disaster operations, the entire platform enforces one inviolable foundation:

> **CORE INVARIANT**:  
> **AERION MUST NEVER PRESENT FABRICATED, SIMULATED, ASSUMED, OR UNAVAILABLE INFORMATION AS VERIFIED REAL-WORLD INTELLIGENCE.**

### Strict Behavioral Rules:
1. **Detections**: Detection counts, class labels, and confidence values must derive strictly from actual ML inference on source imagery.
2. **Tracks**: Track identifiers, centroids, and movement paths must derive strictly from active tracker state ([`border_tracking.py`](file:///D:/mp-1/border_tracking.py)).
3. **Damage**: Damage percentages, damaged pixel counts, and damage ratios must derive strictly from frozen Siamese ResNet18 inference ([`damage_inference.py`](file:///D:/mp-1/damage_inference.py)).
4. **Geographic Coordinates**: Latitude and longitude may be emitted **only** when verified ground georeferencing metadata is present.
5. **Weather Observations**: Weather data must originate from an authoritative external weather provider.
6. **Temporal Consistency for Recorded Video**: Weather for recorded video **must** correspond to the historical recording timestamp, never the current system time.
7. **Evacuation Routes**: Evacuation routing must originate from a real road-network routing provider (e.g. openrouteservice). Straight lines between coordinates must **never** be labeled as evacuation routes.
8. **Emergency Shelters**: Shelters must originate from verified spatial database records; capacity and availability must never be fabricated.
9. **Environmental Hazards**: Hazard perimeters must derive from authoritative external datasets or explicit operator configuration.
10. **LLM Hallucination Guard**: Mistral cannot introduce new facts, infer unobserved casualties, declare unverified damages, or assume unmapped routes.
11. **Explicit Unavailability**: When external or sensor data is missing, the system must set status to `UNAVAILABLE` with an explicit reason string.
12. **Evidence Distinction**: All outputs must strictly distinguish between `OBSERVED`, `DERIVED`, `EXTERNALLY_PROVIDED`, and `ESTIMATED` facts.
13. **Zero Silent Conversions**:
    * Pixel coordinates $\to$ Never silently convert to arbitrary latitude/longitude.
    * Current weather $\to$ Never substitute for historical weather.
    * Euclidean line $\to$ Never represent as a drivable evacuation path.
    * Model-derived heuristic $\to$ Never label as a confirmed real-world event.
    * AI narrative prose $\to$ Never treat as measured physical fact.
14. **Terrain & Elevation**: Never assume or fabricate terrain conditions. When Digital Elevation Model (DEM) data is unavailable, set `terrain_status = UNAVAILABLE` and suppress terrain-dependent calculations. **Never assume flat terrain.**
15. **Vulnerability Factor Availability**: Unavailable vulnerability factors must **NEVER** be silently treated as zero or baseline defaults. A vulnerability score may ONLY be produced when all required inputs are verified and available. If any required factor is missing, return `UNAVAILABLE` or `INSUFFICIENT_EVIDENCE` and expose contributing factor statuses.
16. **GPS & Navigation Integrity**: When GPS telemetry is missing, degraded, or untrusted, set `geographic_status = UNVERIFIED`, retain native image-space pixel coordinates, suppress geographic spatial claims, and continue non-geographic intelligence. **Visual odometry is a future capability and must not be claimed as an operational fallback.**
17. **Strict Fallback Discipline**: Every degraded-mode fallback must either:
    * **A.** Use independently verified fallback data (e.g. local GeoTIFF metadata, validated local registry), or
    * **B.** Mark the capability `UNAVAILABLE` / `UNVERIFIED`.  
    No fallback may introduce fabricated coordinates, weather, terrain, routes, shelters, hazard states, or risk factors.

---

## 3. Evidence Provenance Model

Every operational claim, detection, or metric produced by AERION must trace back to an auditable `EvidenceRecord`.

### 3.1 Canonical Schema: `EvidenceRecord`
```text
EvidenceRecord
 ├── evidence_id: UUID (Unique identifier)
 ├── source_type: EvidenceSourceType (Enum)
 ├── source_name: str (e.g., "YOLOv8s_VisDrone", "Open-Meteo", "OpenRouteService")
 ├── source_reference: Optional[str] (File hash, API query URL, external record ID)
 ├── parent_asset_id: Optional[UUID] (Source image, video file, or GeoTIFF)
 ├── parent_event_id: Optional[UUID] (Triggering situation event)
 ├── observation_timestamp: datetime (When physical phenomenon occurred/was captured)
 ├── ingestion_timestamp: datetime (When system received/processed evidence)
 ├── monitoring_mode: str ("LIVE" | "RECORDED")
 ├── confidence: float (0.0 to 1.0; 1.0 for authoritative external provider)
 ├── verification_status: VerificationStatus (Enum)
 ├── data_quality: DataQuality (Enum)
 ├── freshness_seconds: float (Age of observation relative to ingestion)
 ├── geographic_status: GeographicStatus (Enum)
 ├── latitude: Optional[float] (WGS84 decimal degrees; NULL if unverified)
 ├── longitude: Optional[float] (WGS84 decimal degrees; NULL if unverified)
 ├── geometry: Optional[GeoJSONGeometry] (Point, Polygon, LineString; NULL if unverified)
 ├── coordinate_reference_system: Optional[str] ("EPSG:4326", "EPSG:3857", or "PIXEL_SPACE")
 ├── raw_payload: Dict[str, Any] (Original payload or contract dict)
 └── unavailable_reason: Optional[str] (Populated if data could not be verified)
```

### 3.2 Evidence Enumerations
* **`EvidenceSourceType`**:
  `ML_DETECTION`, `ML_TRACK`, `DAMAGE_MODEL`, `GPS`, `EXIF`, `GEOTIFF`, `GEOREFERENCED_IMAGE`, `OPERATOR_INPUT`, `WEATHER_API`, `MAP_PROVIDER`, `ROUTING_PROVIDER`, `SHELTER_DATA`, `HAZARD_DATA`, `GEOFENCE`, `HISTORICAL_DATA`, `SYSTEM_DERIVED`.
* **`VerificationStatus`**:
  * `VERIFIED`: Confirmed via authoritative telemetry, verified sensor, or official provider.
  * `PARTIALLY_VERIFIED`: Sensor data available but lacking secondary ground confirmation.
  * `ESTIMATED`: Algorithmically derived metric with explicit confidence bounds.
  * `UNAVAILABLE`: Data source was queried but could not provide valid information.
* **`DataQuality`**:
  `OPTIMAL`, `ACCEPTABLE`, `DEGRADED`, `STALE`, `UNRELIABLE`.
* **`GeographicStatus`**:
  * `VERIFIED`: Exact WGS84 coordinates confirmed by embedded GeoTIFF metadata or GPS.
  * `PARTIALLY_VERIFIED`: Approximate geographic bounding box known.
  * `ESTIMATED`: Dead-reckoning or telemetry interpolation.
  * `UNAVAILABLE`: Image/pixel space only. No geographic coordinate system exists.

---

## 4. Monitoring Modes: LIVE vs. RECORDED

AERION operates across two fundamentally distinct temporal operating modes. The platform enforces strict isolation between them:

| Operational Dimension | `LIVE` Mode | `RECORDED` Mode |
| :--- | :--- | :--- |
| **Input Source** | Real-time RTSP camera stream, live drone video downlink. | Uploaded MP4 video file, archived satellite GeoTIFF pair. |
| **Time Semantics** | Current wall-clock time ($t_{\text{now}}$). | Frame-encoded timestamp ($t_{\text{frame}}$) or file capture metadata. |
| **Weather Fetching** | Real-time current weather observation (`get_current_observation()`). | **Historical weather corresponding to frame timestamp** (`get_historical_observation(t)`). |
| **State Evolution** | Rolling in-memory window; active tracks added/dropped dynamically. | Complete deterministic video sweep; ordered chronological event log. |
| **Output Artifact** | Continuous WebSocket telemetry stream + rolling situation state. | Static historical event timeline + final comprehensive situation report. |
| **Dashboard Experience**| Live streaming detection canvas with dynamic threat alert triggers. | Video playback scrubber synchronized with temporal event log. |

> [!CAUTION]
> **Historical Weather Integrity Rule**:  
> For recorded video footage or historical imagery, AERION **must never query or display current weather**. The system must resolve the asset's historical timestamp and request historical weather matching that exact observation window. If historical weather is unavailable, the weather status must be set to `UNAVAILABLE`.

---

## 5. AERION Situation Engine

The Situation Engine is the core state coordinator of AERION. It separates continuous environment tracking into two distinct models:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AERION SITUATION ENGINE                            │
├──────────────────────────────────────┬──────────────────────────────────────┤
│       A. SITUATION STATE (Mutable)   │    B. IMMUTABLE EVENT LOG (Audit)    │
│  - Active tracks in scene            │  - [t0] Track #1 started             │
│  - Current threat priority breakdown │  - [t1] Geofence entered (Track #1)  │
│  - Active weather context            │  - [t2] Potential crossing indicator │
│  - Active geofence status            │  - [t3] High damage cluster detected │
│  - Current data quality indicators   │  - [t4] Route invalidated by flood   │
└──────────────────────────────────────┴──────────────────────────────────────┘
```

### 5.1 Situation State (Current / Rolling State)
Represents the live operational snapshot at timestamp $t$:
* Monitored bounding area / sector name
* Active track count, classified by entity type
* Current threat alert level (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `NOMINAL`)
* Active weather metrics (wind, visibility, precipitation)
* Active route status (passable, hazardous, blocked)

### 5.2 Immutable Event Log
A cryptographically traceable, append-only ledger of discrete operational milestones:
* **Event Structure**:
  ```text
  SituationEvent
   ├── event_id: UUID
   ├── situation_id: UUID
   ├── timestamp: datetime
   ├── event_type: SituationEventType (Enum)
   ├── severity: AlertLevel ("CRITICAL" | "HIGH" | "MEDIUM" | "LOW")
   ├── description: str
   ├── primary_track_id: Optional[int]
   ├── location_geometry: Optional[GeoJSONGeometry]
   ├── pixel_location: Optional[Point2D]
   ├── supporting_evidence_ids: List[UUID] (Foreign keys to EvidenceRecords)
   └── deterministic_metrics: Dict[str, float] (Score, velocity, dwell time)
  ```
* **Event Taxonomy**:
  `object_detected`, `track_started`, `track_updated`, `zone_entered`, `zone_exited`, `zone_dwell_exceeded`, `potential_unauthorized_crossing`, `damage_detected`, `hazard_detected`, `weather_updated`, `route_generated`, `route_invalidated`, `shelter_identified`.

---

## 6. Border Situation Engine & Vulnerability Framework

### 6.1 Mission Profile & Pipeline Inputs
The Border Situation Engine consumes:
* Detections from frozen YOLOv8s ([`drone_detector.py`](file:///D:/mp-1/drone_detector.py))
* Multi-target trajectories from ByteTrack ([`border_tracking.py`](file:///D:/mp-1/border_tracking.py))
* Geofence boundary definitions ([`border_zone.py`](file:///D:/mp-1/border_zone.py))
* Directional alignment & dwell intelligence ([`border_intelligence.py`](file:///D:/mp-1/border_intelligence.py))
* Event suppression & cooldown filters ([`border_event_filter.py`](file:///D:/mp-1/border_event_filter.py))
* External weather context & terrain context ([`terrain_context.py`](file:///D:/mp-1/terrain_context.py))

### 6.2 Entity Taxonomy
Detections and tracks map strictly to the established AERION v1 taxonomy:
* `person`: Dismounted individuals.
* `light_vehicle`: Cars, pickups, SUVs.
* `bus`: High-capacity passenger transports.
* `truck`: Logistics, heavy cargo, or armored vehicles.
* `motorbike`: High-speed crossing vectors.
* `other_transport`: Miscellaneous ground conveyances.

### 6.3 Movement States
Trajectories are categorized into deterministic motion vectors:
* `entering`: Trajectory crosses outer boundary into restricted geofence.
* `inside`: Target centroid resides within geofence polygon.
* `approaching`: Target outside geofence with velocity vector directed toward boundary.
* `exiting`: Target moving from inside to outside of geofence.
* `moving_away`: Target velocity vector diverging from boundary perimeter.
* `stationary`: Net displacement over trailing window $< 5$ pixels.
* `unknown`: Insufficient track history ($< 3$ frames).

### 6.4 Threat Terminology Rule: Potential Crossing Indicators
> [!IMPORTANT]
> **PROHIBITED TERMINOLOGY**: The system must **NEVER** automatically designate an alert as "confirmed infiltration" or "confirmed breach".  
> Automated computer vision cannot confirm operator intent or legal authorization. The system must label events as:  
> **`"potential unauthorized-crossing indicator"`**  
> A confirmed infiltration requires independent on-the-ground verification by human security personnel.

### 6.5 Transparent Border Vulnerability Score Formulation & Data Availability Rule

The deterministic threat calculation is owned entirely by the analytical layer, never by Mistral AI.

#### Strict Input Availability Rule (Zero Silent Default Invariant)
> [!CAUTION]
> **NO SILENT ZEROES OR DEFAULT CONSTANTS**:  
> Factors such as **terrain concealment**, **thermal/environmental crossover**, and **historical incident recurrence** are **NOT** currently guaranteed to exist as verified operational evidence in AERION v1.  
> The engine must **NEVER** silently treat unavailable factors as zero, baseline constants, or assumed averages. Doing so fabricates artificial confidence and masks sensor blindness.  
> A vulnerability score may **ONLY** be produced when all required inputs for the active operational profile are available and explicitly documented.  
> **If ANY required input is missing or unverified, the engine MUST return**:  
> `vulnerability_score = null`  
> `vulnerability_status = "INSUFFICIENT_EVIDENCE"` (or `"UNAVAILABLE"`)  
> The Situation Report must explicitly expose all contributing factors, their individual availability, and the overall `data_quality`.

#### Factor Breakdown & Minimum Verified Requirements:

| Factor ($S_i$) | Required / Optional | Operational Source | Status If Missing |
| :--- | :--- | :--- | :--- |
| **Zone Breach Status** ($S_1$) | **MANDATORY** | Direct ray-casting ([`BorderZoneAnalyzer`](file:///D:/mp-1/border_zone.py)) | If geofence missing $\implies$ `INSUFFICIENT_EVIDENCE` |
| **Approach Velocity** ($S_2$) | **MANDATORY** | Tracker velocity vector dot product | If track $<3$ frames $\implies$ `INSUFFICIENT_EVIDENCE` |
| **Target Class Weight** ($S_3$) | **MANDATORY** | YOLOv8s detection class assignment | If detection unclassified $\implies$ `INSUFFICIENT_EVIDENCE` |
| **Track Dwell Duration** ($S_4$) | **MANDATORY** | ByteTrack frame counter | If track lost $\implies$ `INSUFFICIENT_EVIDENCE` |
| **Trajectory Persistence** ($S_5$)| **MANDATORY** | Track history stability ratio | If track lost $\implies$ `INSUFFICIENT_EVIDENCE` |
| **Terrain Concealment** ($S_6$) | **EXTERNAL** | Digital Elevation Model (DEM) / Land Cover | **NOT ASSUMED**. If DEM missing $\implies$ factor = `UNAVAILABLE` |
| **Weather / Environmental** ($S_7$)| **EXTERNAL** | Verified Weather API observation | **NOT ASSUMED**. If weather offline $\implies$ factor = `UNAVAILABLE` |
| **Historical Recurrence** ($S_8$) | **FUTURE** | Multi-mission longitudinal PostGIS history | **NOT ASSUMED**. Marked `FUTURE / NOT IMPLEMENTED` |

#### Operational Profiles & Score Calculation:
1. **Core Kinetic Profile** (Evaluates only verified perception factors $S_1$ to $S_5$ when external data is absent):
   $$\text{Core Kinetic Score} = \sum_{i=1}^{5} (W_i \cdot S_i) \quad \text{where } \sum W_i = 1.0$$
   * `Zone Breach Status` ($W = 0.40$)
   * `Approach Velocity` ($W = 0.25$)
   * `Target Class Weight` ($W = 0.15$)
   * `Track Dwell Duration` ($W = 0.10$)
   * `Trajectory Persistence` ($W = 0.10$)
2. **Composite Sector Profile** (Requires verified external DEM and weather data):
   * Can ONLY be evaluated if $S_6$ (Terrain) and $S_7$ (Weather) are verified from authentic external providers.
   * If either $S_6$ or $S_7$ is missing, Composite Sector Score is **NOT CALCULATED**; the system outputs `vulnerability_status = "INSUFFICIENT_EVIDENCE"` for the composite score, reports the Core Kinetic Score separately, and logs missing external dependencies.

#### Authoritative Thresholds (Only applicable when score is valid):
* **Critical**: $V \ge 0.75$ $\implies$ Immediate tactical alert dispatched.
* **High**: $0.50 \le V < 0.75$ $\implies$ Heightened monitoring alert.
* **Medium**: $0.25 \le V < 0.50$ $\implies$ Track active; operator advisory.
* **Low / Nominal**: $V < 0.25$ $\implies$ Logged background activity.

---

## 7. Disaster Situation Engine & Evacuation Intelligence

### 7.1 Mission Profile & Pipeline Inputs
The Disaster Situation Engine operates on satellite and aerial surveillance to triage regional destruction:
* Bi-temporal change detection maps from Siamese ResNet18 ([`damage_inference.py`](file:///D:/mp-1/damage_inference.py))
* Aerial damage and rescuee detections from YOLOv8s / YOLOv8n-OBB
* External road-network accessibility from Routing Provider
* Emergency shelter capacities and availability from Shelter Provider
* Real-time flood, wildfire, or seismic hazard perimeters from Hazard Provider
* Meteorological conditions (wind speed, precipitation, cloud cover)

### 7.2 Structured Damage Classification
Damage quantification reports four unambiguous categories:
1. **`OBSERVED`**: Exact damaged pixel count and ratio evaluated by Siamese ResNet18:
   $$\text{Damage Ratio} = \frac{\text{Damaged Pixels } (\text{prob} \ge 0.50)}{\text{Total Pixels In Scope}}$$
2. **`DERIVED`**: Priority tiering calculated deterministically:
   $$\text{Priority} = 0.5 \cdot (\text{Class Weight} \cdot \text{Confidence}) + 0.5 \cdot \text{Change Score}$$
3. **`EXTERNALLY_PROVIDED`**: Authoritative flood zone polygons, road closures, and shelter registries.
4. **`ESTIMATED`**: Estimated population displaced, based strictly on census density multiplied by affected residential footprint.
5. **`UNAVAILABLE`**: Explicitly stated when building footprints, road graphs, or sensor channels cannot be resolved.

### 7.3 Road Accessibility vs. Blockage Architecture
The Siamese ResNet18 change detection model detects structural damage and pixel-level building/earth change, but does **NOT** independently prove that a road is physically blocked. The Disaster Situation Engine strictly distinguishes between three sequential operational evaluations:
1. `damage_detected`: Local pixel change / structural damage footprint identified by Siamese ResNet18 or aerial detector.
2. `road_accessibility_assessment`: Spatial geometric intersection between damage footprint polygons and road network vector graphs.
3. `confirmed_road_blockage`: Declared **only** when corroborated by real road/blockage/hazard evidence (e.g. verified municipal road closure feeds, on-scene civil defense reports, or definitive physical obstacle confirmation).
* **Strict Negative Invariant**: Damage near a road must **never** automatically set `road_blocked = true`.
* **Insufficient Evidence Invariant**: In the absence of corroborating real road/blockage/hazard evidence, the system marks `road_status = UNKNOWN` or `road_status = UNAVAILABLE`.

### 7.4 Evacuation Route Intelligence
AERION generates evacuation route candidates by querying a real routing provider and evaluating route safety:
* **Candidate Routes**:
  * **Fastest Feasible Route**: Minimum travel duration across open roads.
  * **Safest Feasible Route**: Maximum clearance distance from active hazard perimeters (e.g. rising floodwaters or structural collapse zones), even if total distance is greater.
* **Route Rejection Rule**:  
  If verified road data is missing or if all candidate paths intersect verified lethal hazards, the engine marks:
  `route_status = UNAVAILABLE` with reason: `"Evacuation route unavailable: verified road network impassable or hazard boundaries intersect all feasible paths."`  
  **A straight line must NEVER be drawn and labeled as an evacuation route.**

---

## 8. External Provider Abstraction Contracts

To ensure vendor independence and allow datasets/keys to be supplied progressively in Phase 3F, all external services sit behind strict abstract interfaces:

### 8.1 `WeatherProvider` Contract
```python
class WeatherProvider(ABC):
    @abstractmethod
    def get_current_observation(self, lat: float, lon: float) -> WeatherObservation:
        """Fetch current weather for live monitoring missions."""
        pass

    @abstractmethod
    def get_historical_observation(self, lat: float, lon: float, timestamp: datetime) -> WeatherObservation:
        """Fetch historical weather matching the recorded asset timestamp."""
        pass

    @abstractmethod
    def get_forecast(self, lat: float, lon: float, hours_ahead: int) -> List[WeatherObservation]:
        """Fetch near-term forecast for disaster evacuation planning."""
        pass
```
* **Observation Payload**: `source`, `observation_time`, `temperature_c`, `precipitation_mm`, `wind_speed_kmh`, `wind_direction_deg`, `visibility_km`, `weather_code`, `verification_status`, `unavailable_reason`.

### 8.2 `MapProvider` Contract
* **Candidate**: Mapbox / MapLibre GL.
* **Boundary**: Provides vector tiles, satellite base layers, hillshading, and client-side rendering.
* **Strict Rule**: The MapProvider **never** owns or validates operational facts. All detections, tracks, geofences, and damage masks are owned by AERION and layered over the map as GeoJSON features.

### 8.3 `RoutingProvider` Contract
* **Candidate**: openrouteservice (ORS) / OpenStreetMap network.
* **Method**: `calculate_routes(origin: Point2D, destination: Point2D, avoid_polygons: List[Polygon]) -> List[RouteCandidate]`
* **Payload**: `route_id`, `geometry` (GeoJSON LineString), `distance_meters`, `duration_seconds`, `road_segments`, `hazard_intersections`, `risk_tier`, `validity_status`.

### 8.4 `ShelterProvider` & `HazardProvider` Contracts
* **Shelter Entity**: `shelter_id`, `name`, `location` (Point), `capacity_max`, `capacity_current`, `status` (`OPEN`, `FULL`, `CLOSED`), `verification_status`. Capacity is never guessed.
* **Hazard Entity**: `hazard_id`, `hazard_type` (`FLOOD`, `WILDFIRE`, `LANDSLIDE`, `STRUCTURAL_COLLAPSE`, `BLOCKED_ROAD`), `boundary_geom` (Polygon / MultiPolygon), `severity`, `valid_from`, `valid_until`, `source`.

---

## 9. The Mistral AI Advisory Boundary

Mistral AI operates strictly as an **Explanatory Advisory Layer**. It is decoupled from the authoritative calculation of operational facts.

### 9.1 Mistral Architecture Pipeline
```text
Structured Situation Report
        ↓
Deterministic prompt/context builder
        ↓
Mistral API
        ↓
open-mistral-nemo
        ↓
Bounded AI Advisory
```
* **Validated Integration**: AERION's validated Mistral integration uses `open-mistral-nemo` through the hosted Mistral API.
* **Advisory-Only**: Mistral remains strictly advisory-only, providing concise, human-readable situational context.
* **Local vLLM / 7B Prohibited in Phase 3**: Local vLLM inference or self-hosted Mistral 7B servers are documented strictly as future optional deployment strategies (`FUTURE / NOT IMPLEMENTED`) and must **NOT** be part of the required Phase 3 backend. Do not add another GPU-resident model to the local development environment (protecting the RTX 3050 6 GB VRAM ceiling).

### 9.2 Boundary Rules:
1. **Input Restrictions**: Mistral receives only the verified structured JSON emitted by the Situation Engine.
2. **Output Scope**: Mistral generates concise (5–6 sentences, temperature 0.20) plain-language operator advisories, translating mathematical metrics into operational context.
3. **Strict Negative Constraints**:
   * Mistral **cannot** calculate, adjust, or override priority scores or vulnerability indices.
   * Mistral **cannot** invent unverified coordinates, casualties, suspect identities, or property damage.
   * Mistral **cannot** declare a border crossing "confirmed" when the engine designates it as a "potential indicator".
   * Mistral **must** explicitly state when data is unavailable (e.g. `"Ground weather and road conditions are currently unavailable; tactical dispatch should proceed with visual scout verification."`).
   * If the Mistral API fails or times out, the advisory defaults to deterministic standard protocol text from [`protocols.py`](file:///D:/mp-1/protocols.py).

---

## 10. Data Quality & Observability Model

Every Situation Report exposes a top-level `data_quality` block enabling operators to judge the reliability of the operational picture at a glance:

```json
{
  "data_quality": {
    "overall_quality": "ACCEPTABLE",
    "geographic_verification": "VERIFIED",
    "sensor_freshness_seconds": 1.2,
    "weather_available": true,
    "routing_available": false,
    "shelter_data_available": false,
    "hazard_data_available": true,
    "missing_data_fields": [
      "road_network_accessibility",
      "emergency_shelter_registries"
    ],
    "operational_limitations": "Evacuation routing is degraded due to missing road network data. Tactical decisions must rely on manual map recon."
  }
}
```

---

## 11. Failure & Degraded Operational Modes

AERION is built to operate under contested communications, sensor outages, and cloud disconnects. Under the **Real-Data Invariant**, every degraded-mode fallback must either:
- **A.** Use independently verified fallback data, or
- **B.** Explicitly mark the capability `UNAVAILABLE` or `UNVERIFIED`.  
**No fallback may introduce fabricated coordinates, weather, terrain, routes, shelters, hazard states, or risk factors.**

| Failure / Degradation Mode | Subsystem Affected | System Response & Output State (Strict Fallback Rule) |
| :--- | :--- | :--- |
| **GPS Missing / Invalid / Untrusted** | Geospatial Positioning | Sets `geographic_status = UNVERIFIED`. Retains native Cartesian image-space coordinates (`pixel_bbox`, `pixel_polygon`, `pixel_center`). Suppresses verified geographic claims. Continues non-geographic intelligence (tracking, dwell, pixel damage ratio). **Visual odometry is documented as `FUTURE / NOT IMPLEMENTED` and is NOT used.** |
| **DEM / Elevation Data Missing** | Terrain Intelligence | Sets `terrain_status = UNAVAILABLE`. Suppresses terrain-dependent calculations (slope concealment, line-of-sight masking). Unrelated intelligence continues normally. **Never assumes flat terrain.** |
| **Vulnerability Inputs Missing** | Situation Engine | Sets `vulnerability_score = null`, `vulnerability_status = "INSUFFICIENT_EVIDENCE"`. Situation report exposes contributing factors with explicit availability states (`VERIFIED` vs `UNAVAILABLE`). **Never defaults missing factors to zero.** |
| **Weather API Outage / Timeout** | Weather Engine | Detections & tracking continue unimpeded. Sets `weather.verification_status = UNAVAILABLE`. Omits flight suitability calculations. **Never assumes standard 15°C or calm weather.** No alternate provider is claimed as an implemented fallback; provider abstraction supports future provider substitution without silent switching. |
| **Routing Provider Down / Unreachable**| Evacuation Routing | Structural damage assessment completes normally. Sets `evacuation_routes = UNAVAILABLE`. **A straight Euclidean line is NEVER drawn or labeled as an evacuation route.** |
| **Shelter Database Missing / Stale** | Disaster Relief | Affected disaster zone mapped normally. Sets `shelters = UNAVAILABLE` (or `STALE_REGISTRY` if cached with warning banner). **No placeholder shelters are invented.** |
| **Hazard Provider Unreachable** | Spatial Hazards | System relies strictly on local Siamese damage inference (`OBSERVED`). External hazard feeds marked `UNAVAILABLE`. **Never assumes clear or hazard-free zones.** |
| **Mistral API Failure / Timeout** | AI Advisory | Operational report, deterministic metrics, and alerts emitted normally. Advisory defaults to deterministic standard protocol text from [`protocols.py`](file:///D:/mp-1/protocols.py). |
| **GPU VRAM Pressure (6 GB Ceiling)** | ML Runtime | Orchestrator enforces single-model serialization, clears CUDA cache (`torch.cuda.empty_cache()`), or queues task. |
| **Video Drop / Frame Loss** | Border Tracker | ByteTrack holds track states across buffer interval (`lost_track_buffer = 30`). Flags stale tracks; does not fabricate positions. |
| **Cloud Storage S3 Outage** | Artifact Ingestion | Pipeline falls back to verified local disk storage (`D:\mp-1\storage`). Processing does not halt. |

---

## 12. Source Authority Hierarchy

When contradictory signals appear across sensors, algorithms, and models, decisions resolve strictly according to the five-tier authority pyramid:

```text
       ▲
      / \     TIER 1: Direct Verified Sensor & Model Output
     /   \    (YOLOv8s, ResNet18, ByteTrack, Verified GPS Hardware)
    /─────\
   /       \  TIER 2: Ground Truth Asset Metadata
  /         \ (GeoTIFF embedded transforms, calibrated camera matrices)
 /───────────\
/             \ TIER 3: Authoritative External APIs (Open-Meteo, ORS, Gov GIS)
───────────────
/               \ TIER 4: Deterministic Mathematical Formulations (SSIM, Formulas)
─────────────────
/                 \ TIER 5: Generative AI Explanations (Mistral Advisory)
───────────────────
```

> **The Golden Hierarchy Rule**:  
> No lower tier may ever overwrite, fabricate, or contradict evidence originating from a higher tier.
