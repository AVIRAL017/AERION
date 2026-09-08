# AERION v1 — Agent Handoff Document

**CURRENT PHASE**:  
Phase 2.3 — Operational Intelligence + Situation Engine Architecture (COMPLETE)

**NEXT PHASE**:  
Phase 3A — Backend Foundation + Configuration (NOT IMPLEMENTED YET)

**DATE OF HANDOFF**:  
2026-09-08

**OFFICIAL REPOSITORY**:  
`https://github.com/AVIRAL017/AERION.git`

**BASE GIT COMMIT**:  
`c3ab984` (AERION v1 — ML Frozen + Runtime Phase 1 Complete)

---

## 1. COMPLETED WORK SUMMARY

### Phase 1 Deliverables (Preserved & Authoritative):
1. `D:\mp-1\aerion_runtime_contracts.py` — Unified dataclass contracts for geometry (`Point2D`, `BoundingBox`), detections, tracking (`TrackState`), border analysis (`BorderAnalysis`), damage assessment (`DamageAnalysis`), intelligence items (`IntelligenceItem`), and top-level result envelope (`AERIONAnalysisResult`). Pure standard library, strictly JSON serializable.
2. `D:\mp-1\aerion_runtime_normalizer.py` — Runtime adapters transforming raw outputs from `drone_detector.py`, `satellite_detector.py`, `damage_inference.py`, `border_pipeline.py`, and `intelligence_engine.py` into unified contracts.
3. `D:\mp-1\aerion_orchestrator.py` — High-level runtime coordinator providing lazy model loading, mode validation, terrain context injection, unified perception execution, bi-temporal damage processing, streaming video border surveillance, and advisory protocol reporting.
4. `D:\mp-1\tests\__init__.py` — Root test package initializer.
5. `D:\mp-1\tests\runtime\__init__.py` — Runtime test suite package initializer.
6. `D:\mp-1\tests\runtime\test_contracts.py` — 12 unit tests validating contract initialization, invariants, and JSON serialization.
7. `D:\mp-1\tests\runtime\test_normalizers.py` — 5 unit tests validating normalization logic across all 5 subsystems.
8. `D:\mp-1\tests\runtime\test_orchestrator.py` — 5 unit tests validating orchestrator initialization, lifecycle, mode checks, and deterministic scoring.
9. `D:\mp-1\tests\runtime\test_real_integration.py` — 4 real integration tests running frozen models against genuine VisDrone, DOTA-v1.5, xBD, and border video assets.
10. `D:\mp-1\AERION_RUNTIME_CONTRACT.md` — Comprehensive architectural contract and interface specification.

### Phase 2, 2.1 & 2.2 Deliverables (Architecture & Subscription Corrections):
11. `D:\mp-1\AERION_SYSTEM_ARCHITECTURE.md` (v2.3.0) — Authoritative system architecture document covering frozen ML, in-memory normalization, Evidence Layer, Situation Engine, External Providers, and bounded Mistral advisory.
12. `D:\mp-1\AERION_API_CONTRACT.md` (v2.3.0) — Complete REST and WebSocket API specification, including situation management and live telemetry streaming endpoints.
13. `D:\mp-1\AERION_TECHNICAL_DEBT.md` (v2.3.0) — Definitive technical debt catalog covering DEBT-01 through DEBT-17.

### Phase 2.3 Deliverables (Operational Intelligence & Situation Engine Architecture):
14. `D:\mp-1\AERION_OPERATIONAL_INTELLIGENCE.md` — Complete paradigm specification:
    - **Capability Classification Taxonomy**: Rigorous 4-tier taxonomy explicitly distinguishing `[IMPLEMENTED AND VALIDATED]`, `[ARCHITECTURALLY DEFINED]`, `[REQUIRES EXTERNAL DATA]`, and `[FUTURE / NOT IMPLEMENTED]`. Visual odometry, thermal/IR radiometry, GPS spoofing detection, historical recurrence, and local vLLM are strictly `[FUTURE / NOT IMPLEMENTED]`; terrain intelligence (DEM rasters), shelter capacity/availability, real-time road blockage, hazard feeds, and live drone telemetry are strictly `[REQUIRES EXTERNAL DATA]`.
    - **Real-Data Invariant**: Zero fabrication of operational facts. Coordinate defaults (`(0,0)`), synthetic detections, fabricated weather readings, flat terrain assumptions, and simulated evacuation lines are strictly forbidden. Missing data is labeled explicitly as `UNAVAILABLE` or `UNVERIFIED`.
    - **Vulnerability Score Availability Rule**: Unavailable factors (terrain concealment, weather crossover, historical recurrence) must **NEVER** be silently treated as zero or baseline defaults. A vulnerability score may ONLY be produced when all required inputs are verified and available. If any required input is missing, the engine returns `vulnerability_score = null` and `vulnerability_status = "INSUFFICIENT_EVIDENCE"` (or `"UNAVAILABLE"`), exposing contributing factor statuses and data quality.
    - **GPS & Navigation Integrity**: When GPS is invalid, degraded, or untrusted, `geographic_status = UNVERIFIED`, native Cartesian pixel coordinates are retained, geographic spatial claims are suppressed, and non-geographic intelligence continues. **Visual odometry is documented as `FUTURE / NOT IMPLEMENTED` and is NOT used.**
    - **Terrain Conditions**: When DEM data is unavailable, `terrain_status = UNAVAILABLE` and terrain-dependent calculations are suppressed. **Never assume flat terrain.**
    - **Canonical Evidence Model**: `EvidenceRecord` structure with 16 source types, 5 epistemological modalities (`OBSERVED`, `DERIVED`, `EXTERNALLY_PROVIDED`, `ESTIMATED`, `UNAVAILABLE`), and strict coordinate separation.
    - **LIVE vs RECORDED Semantics**: Historical weather matching frame timestamps for recorded footage; live weather for real-time streams.
    - **Situation Engine**: Mutable `SituationState` backed by an append-only sequence of immutable `SituationEvent` records.
    - **Border Intelligence**: Standardized taxonomy (`POTENTIAL_UNAUTHORIZED_CROSSING_INDICATOR` rule; `CONFIRMED_INFILTRATION` strictly prohibited without independent ground confirmation).
    - **Disaster Intelligence**: Damage assessment, road accessibility evaluation (distinguishing `damage_detected`, `road_accessibility_assessment`, and `confirmed_road_blockage`), and dual evacuation route synthesis (`FASTEST_FEASIBLE` vs `SAFEST_FEASIBLE`) over real graph networks.
    - **External Provider Protocols**: `WeatherProvider`, `MapProvider`, `RoutingProvider`, `ShelterProvider`, `HazardProvider`.
    - **Mistral AI Advisory Boundary**: Strict 5-6 sentence limit translating pre-computed facts into natural language executive prose; never invents facts or calculates scores.
    - **Strict Degraded Modes**: 13 operational failure modes and graceful degradation handling satisfying the Real-Data Invariant (either use verified data or mark `UNAVAILABLE` / `UNVERIFIED`).
15. `D:\mp-1\AERION_SITUATION_CONTRACT.md` — Implementation-ready JSON Schemas (Draft 2020-12), Python Pydantic/dataclass models, and TypeScript v5 interfaces for:
    - `EvidenceRecord`
    - `SituationEvent` and `SituationState` (supporting nullable vulnerability scores and explicit status)
    - `BorderSituationReport` and `DisasterSituationReport`
    - `WeatherObservation` and `RouteAssessment`
    - `Shelter` and `HazardZone`
    - `MapLayerCollection` (GeoJSON FeatureCollections for Mapbox GL)
    - `LiveWebSocketSituationMessage`
    - `DegradedModeStatus` (exposing `geographic_status`, `terrain_status`, `vulnerability_status`)

---

## 2. FROZEN ML MODELS (IMMUTABLE)

All 4 ML models remain strictly frozen and cryptographically verified against freeze records. **DO NOT RETRAIN, RE-SAVE, CONVERT, OR MODIFY THESE WEIGHTS.**

1. **Drone (VisDrone-Only Primary)**:
   - Path: `D:\mp-1\runs\detect\visdrone_8s_1280_30ep\weights\best.pt`
   - Architecture: `YOLOv8s` | Resolution: `1280x1280` | Size: `21.54 MB`
   - SHA-256: `343215ac779c1683eef66801b9d0fbf315361074ea71be4356bcb2a40d7a8a2f`
2. **Drone (Unified Aerial + Maritime)**:
   - Path: `D:\mp-1\runs\detect\unified_drone_20ep\weights\best.pt`
   - Architecture: `YOLOv8s` | Resolution: `1280x1280` | Size: `21.56 MB`
   - SHA-256: `05281a43dc81ab015491fa1a7c821bdd9b9f13b1d78d80b2a0d549cf30a0a630`
3. **Satellite (DOTA-v1.5 Oriented Bounding Box)**:
   - Path: `D:\mp-1\runs\obb\train-6\weights\best.pt`
   - Architecture: `YOLOv8n-OBB` | Resolution: `1024x1024` | Size: `6.14 MB`
   - SHA-256: `d96c42323b83826db9781981ef34c4c8673ddee9cf84ea0117e473ab040560dd`
4. **Structural Damage Assessment (xBD Challenge)**:
   - Path: `D:\mp-1\change_detection_runs_v2\best_model.pth`
   - Architecture: `Siamese ResNet18 + U-Net Decoder` | Resolution: `512x512` | Size: `164.08 MB`
   - SHA-256: `0dc2d422693030f5e2446b54e58bda896bc3ecfc05a250e8df78bf2648d61f6b`

---

## 3. TECHNICAL DEBT CATALOG STATUS

All 21 technical debt items are cataloged in `D:\mp-1\AERION_TECHNICAL_DEBT.md`. They are preserved untouched in Phase 2.3 to maintain runtime stability:

| Debt ID | Title | Category | Severity | Scheduled Phase / Classification | Safe to Fix in Phase 2.3? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DEBT-01** | Priority Scoring Threshold Inconsistency | Engineering | MEDIUM | Phase 3E | **NO** |
| **DEBT-02** | Import-Time Model Loading in `damage_inference.py` | Engineering | HIGH | Phase 3E | **NO** |
| **DEBT-03** | Hardcoded Absolute Paths in Root Tests | Engineering | LOW | Phase 3I | **NO** |
| **DEBT-04** | Plaintext Secret Handling (`.env`) | **SECURITY-RELEVANT** | HIGH | **Phase 3A Foundation** | **NO** |
| **DEBT-05** | 6 GB VRAM Ceiling Under Concurrent Execution | Engineering | HIGH | **Phase 3A / 3E** | **NO** |
| **DEBT-06** | In-Memory-Only Persistence | Engineering | HIGH | Phase 3B | **NO** |
| **DEBT-07** | Static Hardcoded Geofencing | Engineering | MEDIUM | Phase 3B / 3C | **NO** |
| **DEBT-08** | Redundant Double File Extension (`.mp4.mp4`) | Engineering | LOW | Phase 3I | **NO** |
| **DEBT-09** | Hardcoded Windows Drive Literals (`D:\mp-1`) | Engineering | MEDIUM | Phase 3A | **NO** |
| **DEBT-10** | Absence of Standardized PyTest Framework | Engineering | LOW | Phase 3I | **NO** |
| **DEBT-11** | Project Branding Divergence in Logs | Engineering | LOW | Phase 3A | **NO** |
| **DEBT-12** | Missing API Security Middleware | **SECURITY-RELEVANT** | CRITICAL | **Phase 3A Foundation** | **NO** |
| **DEBT-13** | Absence of Real Weather Integration | Engineering | HIGH | **Phase 3F [REQUIRES EXTERNAL DATA]** | **NO** |
| **DEBT-14** | Absence of Real Road Network Graph Routing | Engineering | HIGH | **Phase 3F [REQUIRES EXTERNAL DATA]** | **NO** |
| **DEBT-15** | Unbounded Mistral Prompting & Advisory Invariants | Engineering | HIGH | **Phase 3G** | **NO** |
| **DEBT-16** | Volatile Operational Situation State | Engineering | HIGH | **Phase 3C** | **NO** |
| **DEBT-17** | Absence of Authoritative Shelter & Hazard Registries | Engineering | MEDIUM | **Phase 3B / 3F [REQUIRES EXTERNAL DATA]**| **NO** |
| **DEBT-18** | Absence of Visual Odometry Navigation Fallback | Engineering | LOW | **FUTURE / NOT IMPLEMENTED** | **NO** |
| **DEBT-19** | Absence of Hardware GPS Spoofing Detection | Engineering | LOW | **FUTURE / NOT IMPLEMENTED** | **NO** |
| **DEBT-20** | Absence of Thermal / Infrared Radiometric Pipeline | Engineering | LOW | **FUTURE / NOT IMPLEMENTED** | **NO** |
| **DEBT-21** | Absence of Longitudinal Incident Recurrence Modeling| Engineering | LOW | **FUTURE / NOT IMPLEMENTED** | **NO** |

---

## 4. DATABASE ARCHITECTURE STATUS

* **Current Implementation State**: **ZERO** database code, tables, migrations, or active database connections exist in `D:\mp-1`.
* **Design State**: Complete PostgreSQL 16 + PostGIS schema designed and documented in `AERION_SYSTEM_ARCHITECTURE.md`:
  - 19 entities: `organizations`, `users`, `projects`, `assets`, `geofences`, `analysis_jobs`, `analysis_results`, `detections`, `tracks`, `border_events`, `damage_analyses`, `usage_events`, `subscriptions`, `evidence_records`, `situations`, `situation_events`, `situation_reports`, `shelters`, `hazard_zones`.
  - Strict separation between image/pixel space columns and geospatial WGS84 columns.
  - GiST spatial indexing on georeferenced WGS84 columns (`geom_polygon_4326`, `geom_point_4326`).
* **Next Action**: Implement via SQLAlchemy 2.0 (async) + Alembic migrations in Phase 3B.

---

## 5. TEST VERIFICATION SUITE (ALL PASSING)

```powershell
# 1. Runtime Contract & Normalization Unit Tests (22 tests)
& d:\mp-1\venv\Scripts\python.exe -m unittest discover -s tests/runtime -p "test_*.py" -v

# 2. Real Integration Tests with Frozen Models (4 tests)
& d:\mp-1\venv\Scripts\python.exe tests/runtime/test_real_integration.py -v
```
All Phase 1 tests pass with zero regressions (26 passed, 0 failed).

---

## 6. PHASE 3 IMPLEMENTATION ROADMAP (CORRECTED PHASE ORDER)

> [!IMPORTANT]
> **CRITICAL PHASE ORDERING PRINCIPLE**:
> Security and internal data contracts must be fully established and hardened **before** exposing external application services or integrating third-party provider APIs.

```
[Phase 3A: Backend Foundation + Security]
                   ↓
[Phase 3B: PostgreSQL + PostGIS]
                   ↓
[Phase 3C: Evidence + Situation Engine]
                   ↓
[Phase 3D: Authentication/Authorization Hardening]
                   ↓
[Phase 3E: Runtime + Application Services]
                   ↓
[Phase 3F: Weather + Geospatial + Routing + Hazard/Shelter Integrations]
                   ↓
[Phase 3G: Structured Intelligence + Mistral API Advisory]
                    ↓
[Phase 3H: Usage + FREE/PRO Entitlements]
                    ↓
[Phase 3I: Backend Validation]
                    ↓
[Next: Frontend Operations Dashboard]
                    ↓
[Next: AWS / Vercel Cloud Deployment]
                    ↓
[Next: Final End-to-End Integration]
```

### Phase 3A: Backend Foundation + Security
* Create FastAPI application factory (`app/main.py`).
* Implement Pydantic Settings (`AERION_CONFIG`) resolving `.env` without printing secrets (`DEBT-04`).
* Implement core security middleware: CORS origin validation, security headers, abstract `RateLimiter` interface with development-safe in-memory token-bucket / sliding window implementation (`DEBT-12`), and safe error masking. Redis is NOT a mandatory prerequisite for initial Phase 3A security.
* Enforce VRAM serialized GPU execution mutex to protect the 6 GB ceiling (`DEBT-05`).

### Phase 3B: PostgreSQL + PostGIS
* Set up async SQLAlchemy 2.0 engine and Alembic migration environment.
* Implement ORM models for all 19 entities defined in `AERION_SYSTEM_ARCHITECTURE.md`.
* Enforce strict coordinate column separation (pixel space JSON vs WGS84 `geometry` columns).
* Create GiST spatial indexes and initial baseline migration.

### Phase 3C: Evidence + Situation Engine
* Implement `EvidenceRecord` builder wrapping outputs from Phase 1 runtime.
* Implement `SituationEngine` managing mutable `SituationState` and persisting immutable `SituationEvent` records (`DEBT-16`).
* Implement deterministic Border Vulnerability Calculator ($V_{\text{core}}$ kinetic score). Enforce: missing required inputs $\implies$ `vulnerability_score = null`, `status = "INSUFFICIENT_EVIDENCE"`. Never silently default to zero.
* Implement deterministic Disaster Damage & Road Accessibility Evaluator distinguishing: (1) `damage_detected` (local pixel change/structural damage mask), (2) `road_accessibility_assessment` (spatial intersection of damage footprint with road vector graph), and (3) `confirmed_road_blockage` (requires real road/blockage/hazard evidence; damage near a road never automatically sets `road_blocked = true`; if sufficient evidence is unavailable $\implies$ `road_status = UNKNOWN / UNAVAILABLE`).

### Phase 3D: Authentication/Authorization Hardening
* Implement user identity management, password hashing (Argon2id), and Bearer JWT token issuance/refresh.
* Implement Role-Based Access Control (RBAC: `admin`, `operator`, `analyst`) and multi-tenant organization boundary checks.
* Enforce token verification across all non-public API routers.

### Phase 3E: Runtime + Application Services
* Implement Application Service layer coordinating missions, assets, and geofences.
* Implement Runtime Manager wrapping `AERIONOrchestrator` with controlled lazy model loading and explicit CUDA cache eviction (`torch.cuda.empty_cache()`).
* Support initial controlled execution flow: `FastAPI -> Application Service -> AERION Runtime -> Controlled/Lazy GPU Execution`.
* Define background job abstraction interface (`JobExecutor` / in-process `BackgroundTasks` with serialized GPU execution lock protecting the 6 GB VRAM constraint). Distributed worker infrastructure (Celery/Redis/ARQ) is NOT mandatory and deferred to future horizontal scaling (`DEBT-05`).
* Implement core storage service abstraction (Local filesystem, AWS S3, MinIO) for GeoTIFFs, videos, and damage masks (core application infrastructure, decoupled from billing/entitlements).
* Encapsulate `damage_inference.py` loading inside `DamageModelRunner` class (`DEBT-02`).
* Deprecate legacy `priority_scoring.py` in favor of `intelligence_engine.py` (`DEBT-01`).

### Phase 3F: Weather + Geospatial + Routing + Hazard/Shelter Integrations [REQUIRES EXTERNAL DATA]
* Implement `OpenMeteoWeatherProvider` with historical timestamp matching for recorded footage (`DEBT-13`).
* Provider failure rule: if Open-Meteo is unavailable $\implies$ `weather_status = UNAVAILABLE`. No alternate provider is claimed as an implemented fallback; provider abstraction supports future provider substitution without silent switching.
* Implement `OpenRouteServiceRoutingProvider` with obstacle polygon avoidance and dual candidate routing (`FASTEST_FEASIBLE` vs `SAFEST_FEASIBLE`) (`DEBT-14`). If routing is unreachable $\implies$ `evacuation_routes = UNAVAILABLE`.
* Implement `ShelterRegistry` and `HazardZone` spatial query services (`DEBT-17`). If unavailable $\implies$ `shelters = UNAVAILABLE`.
* Enforce degraded mode fallbacks and `DegradedModeStatus` reporting: if GPS untrusted $\implies$ `geographic_status = UNVERIFIED` (native pixel space; visual odometry is `FUTURE / NOT IMPLEMENTED`); if DEM missing $\implies$ `terrain_status = UNAVAILABLE` (never assume flat ground).

### Phase 3G: Structured Intelligence + Mistral API Advisory
* Implement deterministic prompt/context constructor strictly injecting structured report facts (`DEBT-15`).
* Implement hosted Mistral API client calling `open-mistral-nemo` through the Mistral API with bounded 5-6 sentence limit and temperature 0.20.
* Advisory-only: Mistral never calculates scores, counts targets, or invents coordinates. Falls back to deterministic standard protocols from `protocols.py` on timeout/failure.
* Preserve execution pipeline: `Structured Situation Report -> Deterministic prompt/context builder -> Mistral API -> open-mistral-nemo -> Bounded AI Advisory`.
* Local vLLM / self-hosted Mistral 7B inference server is strictly an optional future deployment strategy (`FUTURE / NOT IMPLEMENTED`) and NOT part of Phase 3. No extra GPU-resident models on the local development machine (protecting RTX 3050 6 GB VRAM).

### Phase 3H: Usage + FREE/PRO Entitlements
* Implement architectural entitlement boundary: `plan`, `price`, configurable `entitlements`, configurable `usage_limits`.
* Finalized pricing: `FREE` = ₹0/month, `PRO` = ₹9/month.
* Usage limits and feature entitlements remain configurable and strictly TBD pending empirical cost benchmarking (PRO is bounded, NOT unlimited volume).
* Implement auditable usage metering via `usage_events` logging table.
* Payment adapter hooks (Razorpay, Stripe) remain strictly deferred.
* Do NOT invent or finalize quotas, standard limits, watermarked reports, restricted reports, priority queues, or full report export (these remain future/TBD product decisions).

### Phase 3I: Backend Validation
* End-to-end API integration tests using `httpx.AsyncClient`.
* Frozen model SHA-256 integrity validation and zero-regression testing.
* Degraded mode and failover simulation tests (missing weather, missing routing, untrusted GPS, missing DEM).
* Normalize double file extension (`border_test_urban.mp4.mp4` $\to$ `border_test_urban.mp4`) and standardize test fixtures (`DEBT-03`, `DEBT-08`, `DEBT-10`).

---

## 7. CRITICAL INVARIANT: PHASE 3A IS NOT IMPLEMENTED

> [!IMPORTANT]
> **PHASE 3A IS NOT IMPLEMENTED.**
> Phase 2.3 is strictly an ARCHITECTURE AND CONTRACT DESIGN PHASE. No FastAPI routers, PostgreSQL tables, Alembic migrations, or application code have been written. The codebase remains at the clean Phase 1 runtime baseline (`c3ab984`).



