# AERION — System Architecture & Component Interactions

**Document Version**: 2.3.0  
**Phase**: Phase 2.3 — Operational Intelligence + Situation Engine Architecture  
**Authority**: AERION Architecture Core  
**Canonical Path**: `docs/architecture/AERION_SYSTEM_ARCHITECTURE.md`  

---

> [!NOTE]
> This document details the end-to-end multi-tier architecture of AERION.
> For the authoritative primary contract references, see:
> - Root Architecture Master: [`AERION_SYSTEM_ARCHITECTURE.md`](../../AERION_SYSTEM_ARCHITECTURE.md)
> - Situation Engine Contract: [`AERION_SITUATION_CONTRACT.md`](../../AERION_SITUATION_CONTRACT.md)
> - Operational Intelligence Contract: [`AERION_OPERATIONAL_INTELLIGENCE.md`](../../AERION_OPERATIONAL_INTELLIGENCE.md)
> - API Contract: [`AERION_API_CONTRACT.md`](../../AERION_API_CONTRACT.md)
> - Runtime Contracts: [`aerion_runtime_contracts.py`](../../aerion_runtime_contracts.py)

---

## 1. Multi-Tier Architecture Overview

```text
[ CLIENT TIER ]
React 18 + TypeScript + Vite Dashboard (Orbital Precision UI)
  │
  │ HTTP REST / SSE / WebSocket (/api/v1)
  ▼
[ APPLICATION / API TIER ]
FastAPI 0.141.1 + Uvicorn
  ├── Security & Middlewares (CORS, RequestID, SecurityHeaders, RateLimiter)
  ├── Authentication & Authorization (Argon2id, JWT, RBAC)
  ├── Application Services (Image, Satellite, Damage, BorderVideo)
  ├── Situation Engine (SituationState, SituationEvents, VulnerabilityCalculator)
  └── Structured Intelligence Service (MistralAdvisoryClient, Fallback Protocols)
  │
  ├── GPU Inference Lock (asyncio.Lock serialization, 6GB VRAM protection)
  ▼
[ RUNTIME TIER — FROZEN ML ]
AERIONOrchestrator + RuntimeAdapter
  ├── VisDrone YOLOv8s 1280px (best.pt: 343215ac...)
  ├── Unified Aerial/Maritime YOLOv8s 1280px (best.pt: 05281a43...)
  ├── DOTA-v1.5 YOLOv8n-OBB 1024px (best.pt: d96c4232...)
  ├── Siamese ResNet18 Damage Model (best_model.pth: 0dc2d422...)
  └── ByteTrack Multi-Object Tracking & Ray-Casting Geofencing
  │
  ▼
[ PERSISTENCE & GEOSPATIAL TIER ]
PostgreSQL 16 + PostGIS (19 Relational Entities, GiST Indexing)
External Providers: Open-Meteo (Weather), OpenRouteService (Routing), Mapbox GL
Local Storage / AWS S3
```

---

## 2. Invariant Rules

1. **ML Frozen**: All four model weights are cryptographic constants and cannot be retrained or altered.
2. **Deterministic Grounding**: Detections, tracks, damage percentages, vulnerability scores, routes, and shelters are computed strictly from verified sensor feeds or authoritative databases.
3. **Mistral is Advisory Only**: AI synthesis is bounded to 5-6 sentences, temperature 0.20, and is strictly explanatory.
4. **Coordinate Separation**: Pixel/camera space is strictly segregated from geospatial WGS84 EPSG:4326.
5. **Road Accessibility Corroboration**: Road segments are only marked BLOCKED when corroborated by verified damage or obstruction evidence.
