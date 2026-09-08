# AERION — RESTful API Specification & Contract Design

**Document Version**: 2.3.0  
**Phase**: Phase 2.3 — Operational Intelligence + Situation Engine Architecture  
**Status**: PLANNED DESIGN SPECIFICATION (NOT IMPLEMENTED YET)  
**Protocol Standards**: RESTful HTTP / JSON / SSE / WebSockets  
**Target Backend Framework**: FastAPI (Phase 3A Foundation)  
**Reference Runtime Contracts**: [`aerion_runtime_contracts.py`](aerion_runtime_contracts.py)  
**Reference Situation Contracts**: [`AERION_SITUATION_CONTRACT.md`](AERION_SITUATION_CONTRACT.md)  

---

## 1. Global API Standards

### 1.1 Base URL & Content Negotiation
* **Base URL**: `/api/v1`
* **Headers**:
  * `Content-Type: application/json`
  * `Accept: application/json`
  * `Authorization: Bearer <jwt_token>` (for authenticated endpoints)
  * `X-Request-ID: <uuid4>` (client-supplied or gateway-generated correlation ID)

### 1.2 Unified Success Response Envelope
All successful JSON endpoints return a standardized payload envelope:
```json
{
  "success": true,
  "data": {},
  "meta": {
    "timestamp": "2026-09-08T14:30:00.000Z",
    "request_id": "a93b4d96-c3ef-4f10-928d-19d263b65cb4",
    "version": "v1"
  }
}
```

### 1.3 Standardized Error Response Envelope
All error responses adhere to a consistent structure without exposing stack traces or environment variables:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Confidence threshold must be between 0.0 and 1.0.",
    "error_type": "ClientError",
    "details": [
      {
        "field": "confidence",
        "issue": "value_out_of_bounds",
        "provided": 1.5
      }
    ],
    "timestamp": "2026-09-08T14:30:00.000Z",
    "request_id": "a93b4d96-c3ef-4f10-928d-19d263b65cb4"
  }
}
```

#### Standard Error Codes:
* `AUTHENTICATION_REQUIRED` (401): Missing, malformed, or expired JWT.
* `PERMISSION_DENIED` (403): User lacks role or project membership.
* `SUBSCRIPTION_RESTRICTION` (402): Feature disabled on current plan tier.
* `USAGE_LIMIT_EXCEEDED` (429): Monthly allowance depleted.
* `RESOURCE_NOT_FOUND` (404): Asset, project, job, or geofence not found.
* `VALIDATION_ERROR` (422): Malformed payload or invariant violation.
* `PROCESSING_FAILURE` (500): Downstream perception or inference failure.
* `MODEL_UNAVAILABLE` (503): GPU worker memory exhaustion or loading timeout.

### 1.4 Conceptual Security Middleware Pipeline (Phase 3 Foundation)
Every API request is processed through layered security middleware before application logic executes:
1. **CORS Middleware**: Restricts browser requests strictly to allowed frontends (e.g. `localhost:3000` in dev, production Vercel domain).
2. **Authentication Middleware**: Extracts and verifies Bearer JWT tokens, ensuring valid signature and non-expired timestamp.
3. **Authorization Middleware**: Evaluates user role (`admin`, `operator`, `analyst`) and validates tenant boundary (`organization_id`).
4. **Request Validation**: Pydantic models validate data types, coordinate bounds, and file constraints prior to business execution.
5. **Rate Limiting Middleware**: Protects API endpoints and GPU resources from denial-of-service via an abstract `RateLimiter` interface (initial development-safe in-memory token-bucket / sliding-window implementation; Redis-backed implementation can be introduced later when Redis is adopted). Redis is NOT a mandatory prerequisite for initial backend security.
6. **Error Handling Middleware**: Catches unhandled exceptions and formats them into the standard error envelope without leaking stack traces or internal secrets.

### 1.5 Mandatory Request Lifecycle
```text
Request
  → CORS / Security Middleware
  → Authentication (Who you are)
  → Authorization (What you can touch)
  → Subscription Entitlement (What plan features are permitted)
  → Usage Validation (Metered quota check against monthly limit)
  → Application Service (Workflow logic & asset retrieval)
  → Runtime Execution (Frozen ML perception / change / tracking)
  → Persistence & Response Envelope
```
*Note: Authentication, Authorization, Subscription Entitlement, and Usage Enforcement are strictly separate architectural concerns. Middleware is not implemented in Phase 2.1.*

---

## 2. Authentication & User Management

### 2.1 `POST /api/v1/auth/login`
* **Purpose**: Authenticate user credentials and issue JSON Web Tokens.
* **Auth**: Public.
* **Request Schema**:
  ```json
  {
    "email": "analyst@defense.gov",
    "password": "SecurePassword123!"
  }
  ```
* **Response Schema (200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "access_token": "eyJhbGciOi...",
      "token_type": "Bearer",
      "expires_in_seconds": 900,
      "user": {
        "id": "u-1234",
        "email": "analyst@defense.gov",
        "role": "operator",
        "organization_id": "org-5678"
      }
    }
  }
  ```

### 2.2 `POST /api/v1/auth/refresh`
* **Purpose**: Exchange valid HTTP-only refresh token for a new access token.
* **Auth**: Refresh Cookie.
* **Response Schema (200 OK)**: New `access_token` and lifetime.

---

## 3. Project & Asset Management

### 3.1 `POST /api/v1/projects`
* **Purpose**: Create a new operational surveillance or disaster mission container.
* **Auth**: Authenticated (`operator`, `admin`).
* **Request Schema**:
  ```json
  {
    "name": "Northern Sector Border Surveillance",
    "mode": "border",
    "description": "Perimeter geofencing on sector 4B"
  }
  ```
* **Response Schema (201 Created)**: Project record with UUID.

### 3.2 `POST /api/v1/assets/upload-url`
* **Purpose**: Obtain a pre-signed S3 / storage URL for direct client multipart upload.
* **Auth**: Authenticated.
* **Request Schema**:
  ```json
  {
    "project_id": "proj-9012",
    "filename": "recon_flight_04.jpg",
    "asset_type": "drone_image",
    "file_size_bytes": 14285710,
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  }
  ```
* **Response Schema (200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "asset_id": "ast-3456",
      "upload_url": "https://storage.aerion.internal/upload/ast-3456?signature=...",
      "headers": {
        "Content-Type": "image/jpeg"
      },
      "expires_at": "2026-09-08T14:45:00.000Z"
    }
  }
  ```

---

## 4. Static Perception & Image Analysis

### 4.1 `POST /api/v1/analysis/image`
* **Purpose**: Execute perception inference on a single static aerial or satellite frame.
* **Auth**: Authenticated.
* **Request Schema**:
  ```json
  {
    "project_id": "proj-9012",
    "asset_id": "ast-3456",
    "source_type": "drone",
    "confidence_threshold": 0.25,
    "iou_threshold": 0.50,
    "run_intelligence": true,
    "terrain_context": "arid"
  }
  ```
* **Runtime Mapping**: Maps directly to [`AERIONOrchestrator.process_image()`](aerion_orchestrator.py).
* **Response Schema (200 OK)**:
  Returns the serialized [`AERIONAnalysisResult`](aerion_runtime_contracts.py#L471) envelope:
  ```json
  {
    "success": true,
    "data": {
      "project": "AERION",
      "version": "v1",
      "analysis_id": "fa71295b-302a-4dbf-a365-5c1cf7e96b9d",
      "mode": "disaster",
      "source_type": "drone",
      "image_width": 1920,
      "image_height": 1080,
      "frame_number": null,
      "detections": [
        {
          "source": "drone",
          "class_id": 0,
          "class_name": "person",
          "confidence": 0.8952,
          "bbox": { "x1": 750.4, "y1": 323.1, "x2": 826.6, "y2": 378.0 },
          "obb_points": null,
          "track_id": null,
          "frame_number": null
        }
      ],
      "tracks": [],
      "border_analysis": [],
      "damage_analysis": null,
      "intelligence": [
        {
          "object_class": "person",
          "confidence": 0.8952,
          "class_weight": 0.8,
          "change_score": 0.0,
          "priority_score": 0.3581,
          "priority": "Medium",
          "mode": "disaster",
          "protocol": "Standard advisory: prioritize search-and-rescue verification..."
        }
      ],
      "summary": { "critical": 0, "high": 0, "medium": 1, "low": 0 },
      "overall_status": "detections_available",
      "metadata": {
        "configured_terrain": { "environment": "arid/open" }
      }
    }
  }
  ```

---

## 5. Bi-Temporal Disaster Damage Assessment

### 5.1 `POST /api/v1/analysis/damage`
* **Purpose**: Process pre-disaster and post-disaster image pairs through Siamese ResNet18.
* **Auth**: Authenticated.
* **Request Schema**:
  ```json
  {
    "project_id": "proj-9012",
    "before_asset_id": "ast-pre-01",
    "after_asset_id": "ast-post-01",
    "threshold": 0.50,
    "run_intelligence": true
  }
  ```
* **Runtime Mapping**: Maps directly to [`AERIONOrchestrator.process_change_pair()`](aerion_orchestrator.py).
* **Response Schema (200 OK)**:
  Returns [`AERIONAnalysisResult`](aerion_runtime_contracts.py#L471) with populated [`DamageAnalysis`](aerion_runtime_contracts.py#L154):
  ```json
  {
    "success": true,
    "data": {
      "analysis_id": "8b51dcf8-654e-4e4b-9721-a3f2c5e5bf50",
      "mode": "disaster",
      "source_type": "change_detection",
      "damage_analysis": {
        "before_width": 512,
        "before_height": 512,
        "after_width": 512,
        "after_height": 512,
        "probability_min": 0.0,
        "probability_max": 0.9421,
        "probability_mean": 0.1425,
        "threshold": 0.50,
        "damage_pixels": 25410,
        "total_pixels": 262144,
        "damage_ratio": 0.096932,
        "damage_percentage": 9.6932,
        "probability_map_available": true,
        "damage_mask_available": true
      },
      "summary": { "critical": 1, "high": 0, "medium": 0, "low": 0 },
      "overall_status": "damage_analysis_available"
    }
  }
  ```

---

## 6. Real-Time Border Surveillance & Geofencing

### 6.1 `POST /api/v1/geofences`
* **Purpose**: Define a restricted polygon perimeter boundary in camera-space pixel coordinates and/or georeferenced WGS84 space.
* **Coordinate Rules**:
  * `pixel_polygon` defines image/pixel space coordinates (mandatory for video analytics).
  * `geom_polygon_wgs84` defines geospatial coordinates (latitude/longitude in WGS84 EPSG:4326), populated ONLY when georeferencing is available.
  * **DO NOT automatically convert image pixels into latitude/longitude.** If no georeferencing exists, set `is_georeferenced = false` and omit geographic geometry.
* **Auth**: Authenticated (`operator`, `admin`).
* **Request Schema**:
  ```json
  {
    "project_id": "proj-9012",
    "name": "Restricted Perimeter Zone North",
    "is_georeferenced": false,
    "pixel_polygon": [
      { "x": 900.0, "y": 200.0 },
      { "x": 1200.0, "y": 200.0 },
      { "x": 1200.0, "y": 700.0 },
      { "x": 900.0, "y": 700.0 }
    ],
    "geom_polygon_wgs84": null,
    "dwell_threshold": 5
  }
  ```
* **Response Schema (201 Created)**: Geofence metadata with assigned UUID.

### 6.2 `POST /api/v1/analysis/border/stream` (WebSocket Ingest)
* **Purpose**: Low-latency video frame tracking and geofence breach alert streaming.
* **Protocol**: `WSS /api/v1/ws/border/{project_id}`
* **Frame Message (Binary or Base64 JSON)**:
  ```json
  { "frame_number": 45, "image_b64": "..." }
  ```
* **Stream Broadcast (JSON)**:
  Maps to [`AERIONOrchestrator.process_border_frame()`](aerion_orchestrator.py):
  ```json
  {
    "frame_number": 45,
    "active_tracks_count": 3,
    "alerts": [
      {
        "track_id": 12,
        "class_name": "motorbike",
        "alert_level": "CRITICAL",
        "border_priority": "CRITICAL",
        "direction_relation": "entering_zone",
        "border_activity_score": 0.8654,
        "center": { "x": 950.2, "y": 310.5 }
      }
    ],
    "overall_status": "border_alerts_available"
  }
  ```

---

## 7. Operational Intelligence & Advisory RAG

### 7.1 `POST /api/v1/intelligence/advisory`
* **Purpose**: Query standard operational protocols and optionally invoke Mistral AI for incident reporting.
* **Auth**: Authenticated (`operator`, `analyst`).
* **Request Schema**:
  ```json
  {
    "mode": "disaster",
    "object_class": "building_damage",
    "confidence": 0.92,
    "priority_score": 0.825,
    "priority": "Critical",
    "location": "Guatemala Volcano Sector 03",
    "change_detected": "Severe structural collapse detected via Siamese ResNet18"
  }
  ```
* **Runtime Mapping**: Maps to [`AERIONOrchestrator.generate_advisory_report()`](aerion_orchestrator.py).
* **Response Schema (200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "protocol": "Standard advisory: dispatch structural assessment team, evacuate adjacent buildings if damage is severe...",
      "ai_report": "Incident Report: Building damage detected with 0.92 confidence. Assigned priority level is Critical...",
      "ai_report_error": null
    }
  }
  ```

### 7.2 `POST /api/v1/situations`
* **Purpose**: Initialize an active operational situation bound to a mission project, temporal mode, and session.
* **Auth**: Authenticated (`operator`, `admin`).
* **Request Schema**:
  ```json
  {
    "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "mode": "BORDER_SECURITY",
    "temporal_mode": "LIVE_STREAM",
    "session_id": "e7b0a724-c189-43c2-8bb1-e37894982631",
    "initial_sectors": [
      { "sector_id": "SEC-01", "name": "North Ridgeline", "difficulty": "RUGGED" }
    ]
  }
  ```
* **Response Schema (201 Created)**: Returns the initialized `SituationState` object (refer to [`AERION_SITUATION_CONTRACT.md`](AERION_SITUATION_CONTRACT.md#42-situation-state-mutable-engine-frame)).

### 7.3 `GET /api/v1/situations/{id}`
* **Purpose**: Retrieve the active mutable situation state, composite threat score, sector status summaries, and degraded mode flags.
* **Auth**: Authenticated.
* **Response Schema (200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "situation_id": "7b0b2e81-d703-4682-ba92-a1f94c929a50",
      "mode": "BORDER_SECURITY",
      "temporal_mode": "LIVE_STREAM",
      "overall_threat_level": "HIGH",
      "overall_score": 68.5,
      "overall_score_status": "CALCULATED",
      "active_frame_index": 1420,
      "active_evidence_count": 89,
      "active_event_count": 12,
      "sectors": [
        {
          "sector_id": "SEC-01",
          "sector_name": "North Ridgeline",
          "vulnerability_score": 74.2,
          "vulnerability_status": "CALCULATED",
          "contributing_factors": {
            "breach_status": { "status": "VERIFIED", "value": 1.0 },
            "approach_velocity": { "status": "VERIFIED", "value": 0.85 },
            "target_class": { "status": "VERIFIED", "value": 0.8 },
            "dwell_duration": { "status": "VERIFIED", "value": 0.6 },
            "trajectory_persistence": { "status": "VERIFIED", "value": 0.9 },
            "terrain_concealment": { "status": "UNAVAILABLE", "value": null },
            "weather_penalty": { "status": "UNAVAILABLE", "value": null }
          },
          "threat_level": "HIGH",
          "active_indicators_count": 3,
          "sensor_coverage_status": "NOMINAL"
        }
      ],
      "degraded_status": {
        "is_degraded": false,
        "active_fallbacks": [],
        "geographic_status": "VERIFIED",
        "terrain_status": "UNAVAILABLE",
        "vulnerability_status": "CALCULATED",
        "weather_service_available": true,
        "routing_engine_available": true
      }
    }
  }
  ```

### 7.4 `GET /api/v1/situations/{id}/report`
* **Purpose**: Synthesize the authoritative, schema-conforming Situation Report (`BorderSituationReport` or `DisasterSituationReport`) including deterministic calculations, verified evidence manifest, and bounded Mistral executive advisory text.
* **Auth**: Authenticated.
* **Response Schema (200 OK)**: Full schema conformity with [`BorderSituationReport`](AERION_SITUATION_CONTRACT.md#5-border-situation-report-contract-bordersituationreport) or [`DisasterSituationReport`](AERION_SITUATION_CONTRACT.md#6-disaster-situation-report-contract-disastersituationreport).

### 7.5 `GET /api/v1/situations/{id}/events`
* **Purpose**: Retrieve the immutable chronological sequence of tactical situation events (`SituationEvent`).
* **Auth**: Authenticated.
* **Query Parameters**:
  * `min_threat_level` (Optional: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
  * `limit` (Default: `50`, Max: `500`)
  * `since_sequence_number` (Optional: for client cursor synchronization)
* **Response Schema (200 OK)**: Array of `SituationEvent` objects referencing causal `evidence_ids`.

### 7.6 `GET /api/v1/situations/{id}/map-layers`
* **Purpose**: Retrieve tactical GeoJSON FeatureCollections (`MapLayerCollection`) ready for instant rendering on the Next.js / Mapbox GL dashboard.
* **Auth**: Authenticated.
* **Response Layers**: `detection_layer`, `hazard_layer`, `route_layer`, `shelter_layer`, `sector_layer` with pre-computed tactical styles (`circle-color`, `line-color`, `fill-opacity`).

### 7.7 `GET /api/v1/situations/{id}/weather`
* **Purpose**: Retrieve current or historical reconstructed meteorological conditions anchor-aligned to the active frame's georeference and timestamp.
* **Auth**: Authenticated.
* **Temporal Semantics**: For `RECORDED_FOOTAGE`, queries historical archive matching frame timestamp; for `LIVE_STREAM`, queries live weather. Returns `WeatherObservation`.

### 7.8 `GET /api/v1/situations/{id}/routes`
* **Purpose**: Retrieve evaluated evacuation routes (`RouteAssessment`) computed across real topological road graphs via OpenRouteService, partitioned into `FASTEST_FEASIBLE` and `SAFEST_FEASIBLE` candidates with dynamic hazard polygon avoidance.
* **Auth**: Authenticated.
* **Response Schema (200 OK)**: Array of `RouteAssessment` objects.

### 7.9 `WSS /api/v1/ws/situations/{id}`
* **Purpose**: Bi-directional real-time WebSocket telemetry stream delivering live frame updates, ingested evidence notifications, threshold event alerts, and advisory broadcasts.
* **Auth**: Ticket-based authentication (`?token=<ephemeral_ws_token>`).
* **Protocol Schema**: Adheres to [`LiveWebSocketSituationMessage`](AERION_SITUATION_CONTRACT.md#9-live-websocket-telemetry-contract-livewebsocketsituationmessage).
* **Message Types Emitted**:
  * `SITUATION_FRAME_UPDATE`: Emitted per processed video/data frame with active score and threat tier.
  * `EVIDENCE_INGESTED`: Emitted when new high-confidence evidence is registered.
  * `EVENT_TRIGGERED`: Emitted when a tactical threshold is crossed (e.g. `POTENTIAL_UNAUTHORIZED_CROSSING_INDICATOR`).
  * `ADVISORY_GENERATED`: Emitted when Mistral finishes advisory text generation.
  * `HEARTBEAT`: Emitted every 15 seconds to monitor connection health.

---

## 8. Usage Metering & Subscription Management

### 8.1 `GET /api/v1/usage/summary`
* **Purpose**: Retrieve current monthly quota consumption for the user's organization.
* **Auth**: Authenticated.
* **Quota Status**: Specific monthly quotas are **TBD** and configurable. The numeric values below are **illustrative hypothetical examples only** and do not represent final product decisions.
* **Response Schema (200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "plan": "FREE",
      "billing_period": {
        "start": "2026-09-01T00:00:00.000Z",
        "end": "2026-10-01T00:00:00.000Z"
      },
      "usage": {
        "drone_images_processed": 42,
        "drone_images_limit": 100,
        "satellite_tiles_processed": 8,
        "satellite_tiles_limit": 25,
        "damage_pairs_processed": 2,
        "damage_pairs_limit": 10,
        "video_minutes_processed": 3.5,
        "video_minutes_limit": 5.0
      }
    },
    "meta": {
      "note": "Quota limits shown are illustrative examples; production limits remain TBD pending empirical cost benchmarking."
    }
  }
  ```

### 8.2 `POST /api/v1/subscriptions/upgrade`
* **Purpose**: Transition organization from `FREE` to `PRO` (Plan price: ₹9/month, configurable).
* **Subscription Rules & Invariants**:
  * **Finalized Plans**: Exactly two plans exist: `FREE` (₹0/month) and `PRO` (₹9/month).
  * **PRO IS NOT UNLIMITED VOLUME**: The `PRO` tier usage limits are strictly **TBD** pending empirical cost benchmarking (GPU, CPU, storage, video, satellite, change detection, Mistral RAG, AWS egress).
  * **Configurable Entitlement Boundary**: Phase 3H implements only the architectural entitlement boundary (`plan`, `price`, `entitlements`, `usage_limits`) and `usage_events` auditable logging. Do **NOT** invent or finalize quotas, standard limits, watermarked reports, restricted reports, priority queues, or full report export (these remain future/TBD product decisions). No hard-coded quotas.
  * **Payment Integration Deferred**: No Stripe, Razorpay, payment gateways, checkout sessions, invoices, webhooks, or automatic recurring billing are implemented. Updating a plan in PostgreSQL is a database state transition only; it is **never** equivalent to a verified real-world payment.
  * **ML Runtime Subscription-Agnostic Rule**: Do NOT scatter plan checks throughout ML/runtime code. The following modules remain completely subscription-agnostic: `aerion_orchestrator.py`, `aerion_runtime_normalizer.py`, `aerion_runtime_contracts.py`, `drone_detector.py`, `satellite_detector.py`, `damage_inference.py`, `border_pipeline.py`, `intelligence_engine.py`.
  * **Conceptual Request Flow**: `User -> Authentication -> Authorization -> Subscription -> Entitlement -> Usage Validation -> Application Service -> AERION Runtime`.
* **Auth**: Authenticated (`admin`).
* **Request Schema**:
  ```json
  {
    "target_plan": "PRO",
    "currency": "INR"
  }
  ```
* **Response Schema (200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "organization_id": "org-5678",
      "plan": "PRO",
      "price_inr": 9,
      "currency": "INR",
      "limits_tier": "pro_tier",
      "status": "active"
    }
  }
  ```
