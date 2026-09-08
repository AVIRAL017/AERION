# AERION — Backend Foundation & Security Operational Guide

**Phase**: Phase 3A — Backend Foundation + Security  
**Status**: IMPLEMENTED & TESTED (WORKING TREE READY)  
**Framework**: FastAPI 0.141.1 / Uvicorn 0.52.4 / Pydantic 2.13.5  
**Runtime**: Python 3.13 (PyTorch 2.6.0+cu124 / Ultralytics 8.4.115)  
**Git Baseline**: `ada42b3`  

---

## 1. Architectural Overview

Phase 3A establishes the core backend foundation and security infrastructure for AERION without modifying or retraining the frozen ML models. It provides the application factory, configuration management, middleware pipeline, structured logging, error contract envelopes, GPU VRAM serialization mutex, in-memory rate limiting, in-memory background job scheduling, and a runtime adapter boundary.

```text
HTTP Request
     │
     ▼
[SecurityHeadersMiddleware]  ──► Injects X-Content-Type-Options, CSP, X-Frame-Options, etc.
     │
     ▼
[RequestIDMiddleware]        ──► Validates or generates X-Request-ID, binds to contextvar
     │
     ▼
[CORSMiddleware]             ──► Enforces strict origins (no wildcard in production)
     │
     ▼
[API Router / api_v1]        ──► Routes request to controllers/endpoints
     │
     ▼
[RuntimeService]             ──► Application service mediating domain execution
     │
     ▼
[RuntimeAdapter]             ──► LAZY orchestrator accessor + GPU mutex synchronization
     │
     ▼
[AERIONOrchestrator]         ──► Frozen ML perception & scoring (runs off-thread)
     │
     ▼
Standard Response Envelope   ──► { "success": true, "data": ..., "meta": ... }
```

---

## 2. Directory Structure

```text
app/
├── __init__.py               # Package marker and version identifier
├── main.py                   # FastAPI application factory (create_app) and ASGI entrypoint
├── api/
│   ├── __init__.py           # API router export
│   ├── health.py             # Non-blocking /health and /ready probe endpoints
│   └── router.py             # Central /api/v1 router assembly
├── core/
│   ├── __init__.py           # Core foundation primitives export
│   ├── config.py             # Pydantic Settings management and environment validation
│   ├── errors.py             # Unified error envelopes and exception handlers
│   ├── inference_lock.py     # Async GPU/inference mutex lock (6 GB VRAM protector)
│   ├── jobs.py               # In-process background job scheduling and lifecycle manager
│   ├── logging.py            # Structured JSON logger with request correlation & secret masking
│   ├── rate_limit.py         # Sliding-window in-memory rate limiter with TTL eviction
│   └── security.py           # Request ID, security headers, and CORS middleware
├── runtime/
│   ├── __init__.py           # Runtime package export
│   └── adapter.py            # Lazy loading wrapper around frozen AERIONOrchestrator
├── schemas/
│   ├── __init__.py           # Schema package export
│   ├── common.py             # Unified response envelopes and metadata blocks
│   ├── errors.py             # Authoritative error codes and error envelopes
│   └── health.py             # Liveness and readiness component schemas
└── services/
    ├── __init__.py           # Services package export
    └── runtime_service.py    # Boundary decoupling web routes from ML runtime
```

---

## 3. Configuration & Environment Variables

All settings are managed via `AERIONSettings` in `app/core/config.py` using `pydantic-settings`. Values are populated from environment variables or a local `.env` file.

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `APP_NAME` | string | `"AERION Platform"` | Service title |
| `ENVIRONMENT` | string | `"development"` | Mode: `development`, `test`, or `production` |
| `DEBUG` | boolean | `false` | Verbose debug flag (strictly forbidden in `production`) |
| `API_VERSION` | string | `"v1"` | API version identifier |
| `HOST` | string | `"127.0.0.1"` | Uvicorn host binding |
| `PORT` | integer | `8000` | Uvicorn port binding |
| `ALLOWED_ORIGINS` | list / string | `"http://localhost:3000,http://127.0.0.1:3000"` | Allowed CORS origins (wildcard `*` rejected in production) |
| `REQUEST_ID_HEADER` | string | `"X-Request-ID"` | Header used for correlation tracking |
| `MAX_REQUEST_ID_LENGTH` | integer | `64` | Maximum permissible length for client correlation IDs |
| `RATE_LIMIT_ENABLED` | boolean | `true` | Toggles backend rate limiting |
| `RATE_LIMIT_PER_MINUTE` | integer | `60` | Request quota per minute per key |
| `INFERENCE_TIMEOUT_SECONDS`| float | `60.0` | Maximum wait time for GPU mutex acquisition |
| `DEVICE` | string | `"0"` | PyTorch/CUDA device identifier (`"0"`, `"cuda:0"`, `"cpu"`) |
| `LAZY_LOAD_MODELS` | boolean | `true` | Guarantees zero eager loading during import/startup |

---

## 4. Local Development & Server Execution

### 4.1 Starting the FastAPI Development Server
Using Uvicorn inside the project virtual environment:

```powershell
.\venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive API documentation:
* Swagger UI: `http://127.0.0.1:8000/docs` (disabled in `production`)
* ReDoc: `http://127.0.0.1:8000/redoc` (disabled in `production`)
* OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

---

## 5. Health & Readiness Endpoints

### 5.1 Liveness Probe (`GET /health` and `GET /api/v1/health`)
Confirms the application process is running and the event loop is responsive.
* Does NOT touch the GPU.
* Does NOT instantiate ML models.
* Does NOT connect to databases or external APIs.

**Example Response (HTTP 200)**:
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "timestamp": "2026-09-08T22:30:00.000Z",
    "version": "v1"
  },
  "meta": {
    "timestamp": "2026-09-08T22:30:00.000Z",
    "request_id": "c71a39f6-2e8c-4a7b-84cf-3932a39d8e41",
    "version": "v1"
  }
}
```

### 5.2 Readiness Probe (`GET /ready` and `GET /api/v1/ready`)
Reports the verified operational state of all platform components. In Phase 3A, it honestly reports unimplemented future systems rather than fabricating fake health metrics.

**Example Response (HTTP 200)**:
```json
{
  "success": true,
  "data": {
    "ready": true,
    "timestamp": "2026-09-08T22:30:00.000Z",
    "version": "v1",
    "components": {
      "process": {
        "status": "ready",
        "details": "FastAPI application active in development mode."
      },
      "config": {
        "status": "ready",
        "details": "Pydantic settings loaded and environment validated."
      },
      "inference_lock": {
        "status": "ready",
        "details": "GPU mutex active (locked=False, waiters=0)."
      },
      "models": {
        "status": "lazy_unloaded",
        "details": "Perception and damage models deferred to on-demand execution to protect 6 GB VRAM."
      },
      "database": {
        "status": "not_implemented",
        "details": "PostgreSQL + PostGIS persistence planned for Phase 3B."
      },
      "providers": {
        "status": "not_implemented",
        "details": "External providers (Open-Meteo, OpenRouteService, Mapbox) planned for Phase 3F."
      },
      "mistral": {
        "status": "not_implemented",
        "details": "Mistral AI executive advisory planned for Phase 3G."
      }
    }
  },
  "meta": {
    "timestamp": "2026-09-08T22:30:00.000Z",
    "request_id": "c71a39f6-2e8c-4a7b-84cf-3932a39d8e41",
    "version": "v1"
  }
}
```

---

## 6. Core Subsystem Architecture & Limitations

### 6.1 GPU / Inference Mutex (`InferenceLock`)
* **Purpose**: Hardware inference on the laptop RTX 3050 operates within a strict 6 GB VRAM ceiling. Concurrent loading or simultaneous forward passes of YOLOv8 and Siamese ResNet18 lead to CUDA Out-Of-Memory (OOM) fatal crashes.
* **Mechanism**: An `asyncio.Lock` with timeout protection and cancellation safety ensures that only one task accesses GPU hardware at any given instant.
* **Limitations**: Operates process-locally within the current Python event loop. Distributed locking across multi-worker clusters will be handled in Phase 3E/Phase 4.

### 6.2 Rate Limiter (`InMemoryRateLimiter`)
* **Purpose**: Protects API endpoints from abuse and DoS floods using an abstract `RateLimiter` interface.
* **Mechanism**: Sliding-window log tracking per-client timestamps with bounded memory capacity and TTL key eviction.
* **Limitations**: Operates strictly in-memory within a single process. It does NOT synchronize state across separate worker processes or container replicas. Redis-backed distributed rate limiting will satisfy this identical `RateLimiter` ABC in Phase 3E.

### 6.3 Background Jobs (`JobManager`)
* **Purpose**: Handles non-blocking asynchronous task delegation (e.g. video processing or large imagery tiling).
* **Mechanism**: Asynchronous task scheduling using `asyncio.create_task` with structured lifecycle tracking (`queued`, `running`, `completed`, `failed`, `cancelled`).
* **Limitations**: Job records reside in volatile memory and do not survive process restarts. Persistent database-backed task queues (Celery/PostgreSQL) belong to Phase 3E.

### 6.4 Lazy Loading Guarantee
* Importing `app.main` or creating an application instance via `create_app()` does **NOT** import `torch`, `ultralytics`, or load any model weights. Models remain entirely unloaded until an inference endpoint explicitly triggers perception execution.

---

## 7. What Is Intentionally NOT Implemented Yet

To adhere to incremental architectural boundaries, the following components are explicitly reserved for subsequent phases:
* **Phase 3B**: PostgreSQL 16, PostGIS, SQLAlchemy 2.0 async engine, Alembic migrations, database models, repository persistence.
* **Phase 3C**: Tactical evidence engine, situation scoring engine, chronological situation event log, spatial GeoJSON map layers.
* **Phase 3D**: User registration, password hashing (Argon2id), JWT authentication, refresh cookies, RBAC, tenant isolation.
* **Phase 3E**: Unified runtime & application services, persistent Celery/Redis workers, S3/MinIO object storage abstraction.
* **Phase 3F**: External providers (Open-Meteo weather API, OpenRouteService topological road graph routing, Mapbox vector tiles).
* **Phase 3G**: Mistral AI executive advisory generation via `open-mistral-nemo`.
* **Phase 3H**: FREE (₹0/mo) vs PRO (₹9/mo) entitlement enforcement and usage metering events.
* **Phase 3I**: End-to-end integration and load validation.

---

## 8. Verification & Test Execution

### 8.1 Run All Backend Foundation Tests
```powershell
.\venv\Scripts\python -m unittest discover -s tests/backend -p "test_*.py" -v
```
*Result*: **46 / 46 tests passed (0 failures, 0 errors)**.

### 8.2 Run Runtime Regression Suite
```powershell
.\venv\Scripts\python -m unittest discover -s tests/runtime -p "test_*.py" -v
```
*Result*: **26 / 26 tests passed (0 regressions)**.

### 8.3 Verify Frozen Model SHA-256 Hashes
```powershell
.\venv\Scripts\python -c "
import hashlib
from pathlib import Path

models = {
    'VisDrone': ('runs/detect/visdrone_8s_1280_30ep/weights/best.pt', '343215ac779c1683eef66801b9d0fbf315361074ea71be4356bcb2a40d7a8a2f'),
    'Unified': ('runs/detect/unified_drone_20ep/weights/best.pt', '05281a43dc81ab015491fa1a7c821bdd9b9f13b1d78d80b2a0d549cf30a0a630'),
    'Satellite OBB': ('runs/obb/train-6/weights/best.pt', 'd96c42323b83826db9781981ef34c4c8673ddee9cf84ea0117e473ab040560dd'),
    'Damage': ('change_detection_runs_v2/best_model.pth', '0dc2d422693030f5e2446b54e58bda896bc3ecfc05a250e8df78bf2648d61f6b'),
}

for name, (path, expected) in models.items():
    h = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    print(f'{name}: {\"MATCH [OK]\" if h == expected else \"MISMATCH [FAIL]\"}')
"
```
*Result*: **All 4 frozen model hashes matched 100%**.
