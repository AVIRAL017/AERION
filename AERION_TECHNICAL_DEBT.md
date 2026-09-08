# AERION v1 — Authoritative Technical Debt Register

**Document Version**: 2.3.0  
**Baseline Git Commit**: `c3ab984`  
**Current Phase**: Phase 2.3 (Operational Intelligence + Situation Engine Architecture)  
**Maintenance Policy**: Items recorded here are **KNOWN TECHNICAL DEBT**. They must not be modified, refactored, or arbitrarily cleaned up during Phase 2.3. They will be addressed in designated future phases under controlled conditions.

---

## 1. Technical Debt Classification Taxonomy

Technical debt items are partitioned into two distinct categories:
1. **`[SECURITY-RELEVANT]`**: Critical architectural security and credential handling vulnerabilities. These are NOT ordinary cleanup items; they **must be addressed as mandatory foundations during initial Phase 3 backend construction**.
2. **`[ENGINEERING / REFACTORING]`**: Code hygiene, test ergonomics, and operational optimizations that can be addressed incrementally without compromising platform security.

---

## 2. Technical Debt Item Catalog

| ID | Issue Description | Category | Severity | Impact | Recommended Resolution Phase | Safe to Fix in Phase 2.3? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **DEBT-01** | **Scoring Threshold Divergence** | Engineering | **HIGH** | Legacy script `priority_scoring.py` uses `0.70 / 0.40 / 0.20`, while `intelligence_engine.py` and the ML Manifest use `0.75 / 0.50 / 0.25`. Calling the legacy module yields divergent threat buckets. | **Phase 3** (Deprecate `priority_scoring.py` in favor of `intelligence_engine.py` and `AERIONOrchestrator`). | **NO** (Preserves frozen legacy test behavior). |
| **DEBT-02** | **Damage Model Import-Time Execution** | Engineering | **HIGH** | Lines 29-54 of `damage_inference.py` execute upon module import, instantly loading 164 MB weights into GPU memory and printing logs. | **Phase 3** (Encapsulate loading inside `DamageDetector` class during FastAPI startup). | **NO** (Orchestrator mitigates via lazy import). |
| **DEBT-03** | **Hardcoded Machine-Specific Test Paths** | Engineering | **MEDIUM** | `test_drone_detector.py` and `test_satellite_detector.py` hardcode literal paths `C:\Users\avira\yolo_project\datasets\...`. Fails on other machines. | **Phase 3** (Introduce workspace-relative test fixtures or mock images). | **NO** (Existing root tests must remain untouched). |
| **DEBT-04** | **Plaintext Secret Handling (`.env`)** | **SECURITY-RELEVANT** | **HIGH** | `MISTRAL_API_KEY` exists in plaintext in `d:\mp-1\.env`. Guarded by `.gitignore`, but lacks centralized Pydantic settings parsing, key rotation, and production secret injection. | **Phase 3 Foundation** (Must be resolved as part of initial backend foundation). | **NO** (Local `.env` must remain for offline work; no secret exposure). |
| **DEBT-05** | **GPU Memory Ceiling (6 GB VRAM Constraint)** | Engineering | **HIGH** | Target GPU possesses 6 GB VRAM. Concurrently running drone (1280px), satellite (1024px), and damage (512px) in the same process risks CUDA Out-Of-Memory. | **Phase 3 / Phase 4** (Enforce serialized task execution and lazy model unloading). | **NO** (Phase 1 lazy loading manages this for single tasks). |
| **DEBT-06** | **In-Memory-Only Persistence** | Engineering | **HIGH** | Detections, tracks, geofence breaches, and dwell times vanish on process termination. No historical records exist. | **Phase 3** (Implement PostgreSQL + PostGIS relational and spatial persistence layer). | **NO** (Phase 2.3 is architecture design only). |
| **DEBT-07** | **Static Hardcoded Geofencing** | Engineering | **MEDIUM** | Geofence coordinates are defined as hardcoded tuples (`ZONE_POLYGON`) in source files rather than managed dynamically via API. | **Phase 3** (Implement `geofences` table in PostGIS with separate pixel and WGS84 columns). | **NO** (Existing border pipeline requires static default). |
| **DEBT-08** | **Redundant Video Filename Extension** | Engineering | **LOW** | Test video is named `border_test_urban.mp4.mp4`, with the double extension hardcoded in 4 test scripts. | **Phase 3** (Normalize filename and update referencing tests simultaneously). | **NO** (Avoid breaking existing scripts). |
| **DEBT-09** | **Hardcoded Windows Drive Literals (`D:\mp-1`)** | Engineering | **MEDIUM** | Older scripts and model freeze JSONs embed `D:\mp-1\...`. Moving project to another volume or Linux container breaks lookups. | **Phase 3** (Introduce centralized path resolver with container environment variable overrides). | **NO** (Model freeze hashes cover these manifests). |
| **DEBT-10** | **Absence of Standardized PyTest Framework** | Engineering | **LOW** | Virtual environment lacks `pytest`. Legacy root tests use custom script execution loops with print output instead of test assertions. | **Phase 3** (Add `pytest` to `requirements.txt` and standardize unit/integration suites). | **NO** (Phase 1 unit tests use built-in `unittest`). |
| **DEBT-11** | **Project Branding Divergence in Logs** | Engineering | **LOW** | Older console prints output `GEOSHIELD AI`, while official contracts, manifests, and documentation designate platform as `AERION v1`. | **Phase 3** (Standardize logging formatters across all components). | **NO** (Cosmetic only; zero runtime functional impact). |
| **DEBT-12** | **Missing API Security Middleware** | **SECURITY-RELEVANT** | **CRITICAL** | API layer lacks CORS filtering, JWT authentication middleware, RBAC authorization, request rate limiting, and safe error masking. | **Phase 3A Foundation** (Mandatory baseline before exposing services). | **NO** (API layer is not yet implemented). |
| **DEBT-13** | **Absence of Real Weather / Meteorological Integration** | Engineering | **HIGH** | Current system has zero weather awareness. Environmental factors (wind, visibility, precipitation) are unmeasured. | **Phase 3F [REQUIRES EXTERNAL DATA]** (Implement `Open-Meteo` adapter with live/historical queries). | **NO** (External adapter deferred to Phase 3F). |
| **DEBT-14** | **Absence of Real Road Network Graph Routing** | Engineering | **HIGH** | Evacuation routing cannot be calculated from image pixels; straight Euclidean lines risk directing evacuees into hazards. | **Phase 3F [REQUIRES EXTERNAL DATA]** (Implement `OpenRouteService` road graph adapter with dynamic hazard avoidance). | **NO** (Routing adapter deferred to Phase 3F). |
| **DEBT-15** | **Unbounded Mistral Prompting & Advisory Invariants** | Engineering | **HIGH** | Early prototype invoked Mistral with ad-hoc prompts, risking hallucination, unverified assertions, and unbound text length. | **Phase 3G** (Implement strict prompt builder with deterministic fact injection and 6-sentence limit). | **NO** (Mistral pipeline deferred to Phase 3G). |
| **DEBT-16** | **Volatile Operational Situation State** | Engineering | **HIGH** | Operational context, tracking histories, sector scores, and alert logs are not persisted across frames or sessions. | **Phase 3C** (Implement `Situation Engine` backed by PostgreSQL `situations` and `situation_events`). | **NO** (Situation engine implementation deferred to Phase 3C). |
| **DEBT-17** | **Absence of Authoritative Shelter & Hazard Registries** | Engineering | **MEDIUM** | No structured store exists for civil protection shelters or spatial hazard perimeters. | **Phase 3B / Phase 3F [REQUIRES EXTERNAL DATA]** (Implement `shelters` and `hazard_zones` tables in PostGIS). | **NO** (Persistence deferred to Phase 3B). |
| **DEBT-18** | **Absence of Visual Odometry Navigation Fallback** | Engineering | **LOW** | No optical flow or visual SLAM pipeline exists to estimate camera trajectory if GPS fails. | **FUTURE / NOT IMPLEMENTED** (Do NOT claim as fallback; system operates in native pixel space). | **NO** (Future capability only). |
| **DEBT-19** | **Absence of Hardware GPS Spoofing Detection** | Engineering | **LOW** | No multi-constellation RF hardware or signal-integrity monitor exists to verify GPS validity. | **FUTURE / NOT IMPLEMENTED** (If GPS is untrusted, set `geographic_status = UNVERIFIED`). | **NO** (Future capability only). |
| **DEBT-20** | **Absence of Thermal / Infrared Radiometric Pipeline** | Engineering | **LOW** | System possesses no thermal sensor models; infrared crossover risk cannot be measured from RGB. | **FUTURE / NOT IMPLEMENTED** (Suppress crossover penalty; never default to zero). | **NO** (Future capability only). |
| **DEBT-21** | **Absence of Longitudinal Incident Recurrence Modeling**| Engineering | **LOW** | Historical patrol recurrence requires months of accumulated mission logs in PostGIS. | **FUTURE / NOT IMPLEMENTED** (Omit recurrence factor from vulnerability calculations). | **NO** (Future capability only). |


---

## 3. Detailed Debt Analysis & Resolution Strategy

### DEBT-01: Scoring Threshold Discrepancy
* **Root Cause**: `priority_scoring.py` was an early heuristic prototype. During subsequent validation and formal ML verification, the thresholds were standardized to `0.75 / 0.50 / 0.25` in `intelligence_engine.py` and recorded in `aerion_v1_ml_verification_manifest.json`.
* **Resolution Strategy**: In Phase 3, `intelligence_engine.py` is established as the sole authoritative threat scoring implementation. `priority_scoring.py` will be formally marked deprecated.

### DEBT-02: Damage Model Import-Time Execution
* **Root Cause**: `damage_inference.py` was written as a procedural standalone execution script where `torch.load()` and model instantiation occurred at file scope.
* **Resolution Strategy**: In Phase 3, refactor `damage_inference.py` so model loading is encapsulated within a `DamageModelRunner` class with an explicit `.load()` method. `AERIONOrchestrator` in Phase 1 already protects against this by importing `damage_inference` lazily only when `analyze_damage()` is called.

### DEBT-04: Plaintext Secret Handling (`.env`) [SECURITY-RELEVANT]
* **Root Cause**: An unversioned `.env` file exists in the project root containing credentials (such as `MISTRAL_API_KEY`). While safely excluded from Git via `.gitignore`, relying on ad-hoc environment reading risks accidental exposure, log leakage, or hardcoding in developer scripts.
* **Resolution Strategy**:
  1. **Phase 3 Foundation**: Implement a centralized `AERION_CONFIG` using Pydantic Settings (`BaseSettings`). Credentials are read securely from OS environment variables and never printed in logs or error traces.
  2. **Invariance**: The local `.env` remains strictly local and untracked. No credentials will ever be committed or hardcoded.
  3. **Future Production**: Transition to cloud secret managers (AWS Secrets Manager / ECS Task Secrets) in Phase 4.

### DEBT-05: 6 GB VRAM Constraint
* **Root Cause**: Running Ultralytics YOLOv8s at 1280px resolution and PyTorch Siamese ResNet18 simultaneously consumes ~4.5 GB of VRAM. Spawning multiple workers or running concurrent pipelines on a local machine triggers CUDA Out-Of-Memory.
* **Resolution Strategy**: Phase 3 FastAPI backend will enforce controlled lazy model loading and serialized execution (`torch.cuda.empty_cache()`), loading only one heavy model at a time. The initial architecture supports `FastAPI -> Application Service -> AERION Runtime -> Controlled/Lazy GPU Execution` with a background job abstraction (`JobExecutor` / in-process `BackgroundTasks`). Distributed worker clusters (Celery + Redis) are strictly deferred to future scaling (Phase 4+). Multi-stream parallel inference will be deferred to future cloud GPU nodes (e.g. AWS `g4dn.xlarge` with 16 GB VRAM).

### DEBT-12: Missing API Security Middleware [SECURITY-RELEVANT]
* **Root Cause**: The current runtime exists as standalone Python modules. Exposing these modules directly over HTTP without security boundaries would allow unauthorized access, arbitrary request flood, and sensitive information leakage.
* **Resolution Strategy**:
  1. **Phase 3 Foundation (Phase 3A)**: When implementing FastAPI, construct the security boundary **from the very beginning**:
     - Strict CORS policy restricting allowed origins.
     - HTTP Bearer JWT authentication middleware verifying token integrity and expiration.
     - Role-Based Access Control (RBAC) middleware verifying user tenancy and permissions.
     - Rate limiting middleware (IP and tenant based) via abstract `RateLimiter` interface (initial development-safe in-memory token-bucket / sliding window implementation; Redis-backed implementation deferred to when Redis is adopted) to prevent denial of service and GPU resource exhaustion.
     - Exception handling middleware intercepting all unhandled errors and formatting them into `AERIONErrorEnvelope` without exposing internal paths or stack traces.
  2. Under no circumstances should unauthenticated or unthrottled endpoints be deployed.

### DEBT-13: Absence of Real Weather / Meteorological Integration
* **Root Cause**: Early prototypes assumed static weather or ignored meteorological variables. Drone flight safety, optical sensor visibility, and infrared thermal crossover directly depend on live temperature, wind speed, and precipitation.
* **Resolution Strategy**: In Phase 3F [REQUIRES EXTERNAL DATA], implement `OpenMeteoWeatherProvider` adhering to `WeatherProvider` protocol. Crucially, honor temporal semantics: query historical weather records matching video/image capture timestamps for recorded media, and live forecast/current readings for live streams. If Open-Meteo is unavailable $\implies$ `weather_status = UNAVAILABLE`. No alternate provider is claimed as an implemented fallback; provider abstraction supports future provider substitution without silent switching.

### DEBT-14: Absence of Real Road Network Graph Routing
* **Root Cause**: Early disaster prototypes had no road network representation, which risks falling back on dangerous straight-line Euclidean distance approximations.
* **Resolution Strategy**: In Phase 3F [REQUIRES EXTERNAL DATA], integrate `OpenRouteService` road graph routing engine. When structural damage or flood hazard polygons are identified, dynamically inject these as obstacle polygons into the routing engine's avoidance parameters. Partition routes into `FASTEST_FEASIBLE` and `SAFEST_FEASIBLE`. If routing is offline or unreferenced, explicitly set `status = UNAVAILABLE` rather than drawing misleading straight lines.

### DEBT-15: Unbounded Mistral Prompting & Advisory Invariants
* **Root Cause**: Standard LLM generation without strict guardrails risks generating hallucinated coordinates, unauthorized threat escalations, or verbose summaries.
* **Resolution Strategy**: In Phase 3G, implement a deterministic prompt constructor injecting strictly verified JSON facts from `BorderSituationReport` or `DisasterSituationReport`. The system queries the hosted Mistral API using `open-mistral-nemo` with a rigid 5-6 sentence ceiling and temperature 0.20. Mistral operates strictly as an advisory-only layer and falls back to `protocols.py` on timeout. Local vLLM / self-hosted Mistral 7B inference is strictly an optional future deployment strategy (`FUTURE / NOT IMPLEMENTED`) and NOT part of Phase 3.

### DEBT-16: Volatile Operational Situation State
* **Root Cause**: Phase 1 orchestrator returns one-off dictionaries without maintaining rolling mission state or chronological event sequences.
* **Resolution Strategy**: In Phase 3C, implement `SituationEngine` managing in-memory `SituationState` and persisting state snapshots and `SituationEvent` records into PostgreSQL.

### DEBT-17: Absence of Authoritative Shelter & Hazard Registries
* **Root Cause**: No database tables or schemas exist to track civil protection shelters, generator power, medical capabilities, or active spatial hazard perimeters.
* **Resolution Strategy**: In Phase 3B / Phase 3F [REQUIRES EXTERNAL DATA], implement `shelters` and `hazard_zones` tables in PostGIS, linking real-time occupancy and status updates to evacuation routing algorithms.

