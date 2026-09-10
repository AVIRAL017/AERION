# AERION v1 — Batch 2 Grounded Intelligence & Mode Workflows Documentation
**Steps 24–26: Grounded Mistral Advisory, Disaster Mode E2E, and Border Security Mode E2E**

---

## 1. Executive Summary

Batch 2 connects AERION's verified perception, tracking, PostGIS spatial data layer, and external provider infrastructure into grounded, end-to-end operational intelligence pipelines for both platform modes:
1. **Step 24 (Grounded Mistral Intelligence)**: Integrated Mistral AI (`open-mistral-nemo`) as a bounded, advisory-only synthesizer. Mistral interprets verified structured evidence packages and adheres to strict anti-hallucination prompts. If the API is unconfigured, rate-limited, or unavailable, deterministic fallback advisories are generated without fabricating responses.
2. **Step 25 (Disaster Mode E2E)**: Built the complete Disaster Response workflow connecting bi-temporal Siamese damage detection, PostGIS hazard context (including Step 21 USGS seismicity records), emergency shelters, building footprints, critical infrastructure, real Open-Meteo weather, real road graph routing, and grounded advisory synthesis.
3. **Step 26 (Border Security Mode E2E)**: Built the complete Border Security workflow connecting aerial drone detection, ByteTrack tracking, persistence filtering, authoritative Survey of India boundary contract status (`NOT_ACQUIRED` invariant preserved), potential unauthorized crossing indicators, annotated visual artifacts, and grounded advisory synthesis.

---

## 2. Step 24 — Grounded Mistral Advisory Architecture

### 2.1 Advisory-Only Invariant
- **Advisory Role**: Mistral is strictly an advisory synthesizer. It is **never** a detector, classifier, geocoder, weather source, routing engine, or source of truth.
- **Evidence Traceability**: Every advisory maps directly to verified evidence record IDs (`evidence_references`), preventing fabricated operational conclusions.
- **Deterministic Fallback**: When `MISTRAL_API_KEY` is missing or the external API returns an error or timeout, the system generates a structured `NormalizedAdvisoryRecord` using deterministic protocol rules from `protocols.py` with explicit status (`AUTH_REQUIRED`, `TIMEOUT`, `PROVIDER_ERROR`).

### 2.2 Model Configuration
- **Model Designated**: `open-mistral-nemo` (configured via `MISTRAL_MODEL` in `.env` / `app/core/config.py`).
- **Endpoint**: `https://api.mistral.ai/v1/chat/completions`
- **Temperature**: `0.15` (low randomness for deterministic fidelity).
- **Credentials**: Retrieved securely via `SecretStr`; never printed, logged, committed, or exposed through client payloads.

### 2.3 Normalized Advisory Contract
```json
{
  "advisory_id": "6ac0e0bb-d2d9-454e-876d-c9af158abf5e",
  "mode": "BORDER_SECURITY",
  "summary": "Three detections have been registered in the designated area...",
  "priority": "HIGH",
  "key_findings": [
    "3 verified object detections recorded by frozen detector.",
    "1 Potential Unauthorized Crossing Indicator(s) evaluated.",
    "Authoritative boundary status: NOT_ACQUIRED."
  ],
  "evidence_references": ["ev-1", "ev-2"],
  "recommended_actions": ["Standard advisory: verify presence outside authorized zone."],
  "limitations": [
    "Local weather observation data is unavailable.",
    "Authoritative Survey of India international boundary data is not acquired."
  ],
  "generated_at_utc": "2026-09-10T22:39:50.123456Z",
  "model": "open-mistral-nemo",
  "provider_status": "AVAILABLE",
  "grounded": true,
  "disclaimer": "AI advisory is derived from automated sensor feeds..."
}
```

---

## 3. Step 25 — Disaster Mode E2E Workflow

### 3.1 Pipeline Flow
```
Pre/Post Disaster Imagery
         │
         ▼
Frozen Siamese Damage Model (threshold=0.50)
         │
         ▼
Damage Assessment (Pixels, Ratio, Percentage)
         │
         ▼
Georeferencing Check (EPSG:4326)
  ├─ [UNAVAILABLE] ──► Suppress spatial claims, mark weather/routing unavailable
  └─ [AVAILABLE]   ──► PostGIS Administrative Containment (ST_Contains)
                         │
                         ├─ USGS Seismicity & Flood Hazards (ST_DWithin)
                         ├─ Registered Shelters & Capacity (ST_DWithin)
                         ├─ Building Footprints & Infrastructure
                         ├─ Real Open-Meteo Weather (flight suitability)
                         └─ Real Road Graph Route to nearest open shelter
                                 │
                                 ▼
                   Deterministic Priority Scoring
                                 │
                                 ▼
                     Grounded Mistral Advisory
                                 │
                                 ▼
                 Persistent Result & Evidence Log
```

### 3.2 Key Invariants Enforced
- **Zero Coordinate Fabrication**: If coordinates are missing, `georeferencing_status = "UNAVAILABLE"`. No geographic locations are guessed.
- **Damage Probability vs Certainty**: The system reports that damage probability exceeds the configured threshold across $X\%$ of the region; it never states "Building $X$ is destroyed" without corroboration.
- **Road Blockage Rule**: Structural damage near a road does **not** mark the road as blocked without corroborating ground or hazard reports.

---

## 4. Step 26 — Border Security Mode E2E Workflow

### 4.1 Pipeline Flow
```
Aerial Video or Static Imagery
         │
         ▼
Frozen VisDrone / Unified Detector
         │
         ▼
ByteTrack Multi-Object Tracking & Persistence Filtering
         │
         ▼
BorderZone Evaluation (Point-in-Polygon & Dwell)
         │
         ▼
Authoritative Boundary Contract Check (Survey of India)
  └─ [NOT_ACQUIRED] ──► Proximity calculations suspended; no false frontier claims
         │
         ▼
Contextual Weather via Open-Meteo
         │
         ▼
Deterministic Threat/Priority Bucketing
         │
         ▼
Potential Unauthorized Crossing Indicator Generation
         │
         ▼
Grounded Mistral Advisory (Strict Terminology Rules)
         │
         ▼
Annotated Visual Evidence Artifact Generation & Persistence
```

### 4.2 Key Invariants Enforced
- **Indicator Terminology**: Detections are labeled strictly as `Potential Unauthorized Crossing Indicator`, **never** as uncorroborated "infiltration".
- **Boundary Truth**: Generic administrative boundaries (ADM0) are **never** substituted for authoritative Survey of India international borders. Status remains `NOT_ACQUIRED`.

---

## 5. Endpoints Reference

| Endpoint | Method | Mode | Description |
| :--- | :--- | :--- | :--- |
| `/api/v1/analysis/disaster/e2e` | `POST` | Disaster | Full end-to-end disaster analysis with damage inference, PostGIS hazards/shelters, real weather, real routing, and grounded advisory. |
| `/api/v1/analysis/border/e2e` | `POST` | Border | Full end-to-end border security analysis with tracking, boundary verification, crossing indicators, annotated artifacts, and grounded advisory. |

---

## 6. Verification Summary

- **Backend Test Discovery**: **195 / 195 tests passed** (`Ran 195 tests in 51.056s, OK`).
- **Runtime Inference Suite**: **26 / 26 tests passed** (`Ran 26 tests in 12.764s, OK`).
- **Frozen Model Weights**: 4/4 frozen model weights hashes strictly verified.
- **Frontend Build**: TypeScript check and Vite production bundle passed cleanly (`built in 25.22s`).
