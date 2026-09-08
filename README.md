# AERION — Aerial Reconnaissance & Intelligence Operations Network

**Project Status**: Phase 1 Complete — Frozen ML Perception & Unified Runtime Integration  
**Architecture Version**: AERION v1  
**Default Repository Branch**: `main`  

---

## 1. Executive Summary

AERION is an advanced multi-modal defense and disaster situational awareness platform integrating aerial/drone computer vision, satellite oriented bounding box (OBB) object detection, bi-temporal Siamese structural damage assessment, real-time border surveillance geofencing, and protocol-grounded advisory incident intelligence.

All four core machine learning models are officially **FROZEN** with cryptographic SHA-256 hashes recorded in authoritative freeze manifests.

---

## 2. Core Subsystems

### 2.1 Aerial Drone Surveillance
* **VisDrone-Only Primary**: YOLOv8s fine-tuned on custom 6-class aerial data at `1280x1280` resolution for land/border vehicle and person surveillance.
* **Unified Aerial/Maritime**: YOLOv8s fine-tuned on a 10-class unified aerial dataset combining VisDrone and SeaDronesSee for multi-domain land and maritime tracking.

### 2.2 Satellite Detection (Oriented Bounding Boxes)
* **DOTA-v1.5 YOLOv8n-OBB**: Detects 16 infrastructure, maritime, and vehicle classes using 4-corner oriented bounding box (OBB) geometry on tiled satellite imagery at `1024x1024` resolution.

### 2.3 Disaster Damage Assessment
* **Siamese ResNet18 + U-Net Skip Decoder**: Bi-temporal change detection neural network trained on the xBD / xView2 challenge dataset. Evaluates pre- and post-disaster satellite/aerial image pairs (`512x512`), computing probability maps and quantifying damaged structural area at decision threshold `0.50`.

### 2.4 Border Geofencing & Real-Time Tracking
* **ByteTrack Integration**: Multi-object trajectory tracking over temporal sliding windows.
* **Ray-Casting Geofence**: High-performance point-in-polygon containment, boundary Euclidean distance projection, approach vectors, dwell timing, and cooldown-filtered border threat alerts.

### 2.5 Deterministic Intelligence & Advisory Protocols
* **Threat Scoring Engine**: Mathematical combination of class-risk weights, model confidence, and localized Structural Similarity Index (SSIM) change signals.
* **Advisory RAG**: Operational guidance retrieval mapped to standard emergency/border protocols, with optional decoupled incident reporting via Mistral AI.

---

## 3. Runtime Layer Architecture (Phase 1)

Phase 1 provides a clean, persistence-agnostic, and serialization-safe runtime contract layer above the frozen ML models:

```
FROZEN MACHINE LEARNING MODELS
    ↓
EXISTING RUNTIME ADAPTERS (drone_detector, satellite_detector, damage_inference, border_pipeline)
    ↓
AERION NORMALIZATION (aerion_runtime_normalizer.py)
    ↓
AERION UNIFIED CONTRACTS (aerion_runtime_contracts.py)
    ↓
AERION ORCHESTRATOR (aerion_orchestrator.py)
```

### Key Modules:
* [`aerion_runtime_contracts.py`](aerion_runtime_contracts.py): Standard `@dataclass` contracts (`Point2D`, `BoundingBox`, `Detection`, `TrackState`, `BorderAnalysis`, `DamageAnalysis`, `IntelligenceItem`, `SceneSummary`, and `AERIONAnalysisResult`).
* [`aerion_runtime_normalizer.py`](aerion_runtime_normalizer.py): Type-safe adapters converting raw detector tensors and tracking outputs into unified dataclasses.
* [`aerion_orchestrator.py`](aerion_orchestrator.py): High-level operational façade with lazy model loading to preserve GPU memory (6 GB VRAM budget), mode enforcement, and unified analysis entry points.

---

## 4. Repository Structure

```text
D:\mp-1\
├── aerion_runtime_contracts.py      # Unified dataclass contracts & schemas
├── aerion_runtime_normalizer.py     # Subsystem output normalization adapters
├── aerion_orchestrator.py           # Central runtime mission orchestrator
├── drone_detector.py                # Frozen YOLOv8s drone inference adapter
├── satellite_detector.py            # Frozen YOLOv8n-OBB satellite inference adapter
├── damage_inference.py              # Frozen Siamese ResNet18 damage inference adapter
├── border_pipeline.py               # Composite YOLO + ByteTrack + Geofence pipeline
├── border_tracking.py               # Motion vector & trajectory calculation
├── border_zone.py                   # Ray-casting geofence & boundary projection
├── border_intelligence.py           # Threat scoring & approach analysis
├── border_event_filter.py           # Cooldown filtering & alert qualification
├── terrain_context.py               # Terrain operational environment metadata
├── intelligence_engine.py           # SSIM-grounded multi-detection scoring
├── protocols.py                     # Standard operational advisory knowledge base
├── report_generator.py              # Advisory LLM report generator (Mistral)
├── rag_intelligence.py              # Orchestration linking protocols and LLM
├── live_video_input.py              # Threaded non-blocking video stream buffer
├── video_input.py                   # Synchronous video capture abstraction
├── tests/
│   ├── runtime/
│   │   ├── test_contracts.py        # 12 contract & serialization unit tests
│   │   ├── test_normalizers.py      # 5 normalization unit tests
│   │   ├── test_orchestrator.py     # 5 orchestrator lifecycle unit tests
│   │   └── test_real_integration.py # 4 end-to-end frozen ML integration tests
├── test_results/
│   ├── model_freeze/                # Cryptographic freeze records for ML models
│   └── aerion_v1_ml_verification_manifest.json # Authoritative ML verification manifest
├── AERION_RUNTIME_CONTRACT.md       # Comprehensive runtime interface specification
├── AERION_AGENT_HANDOFF.md          # Autonomous agent continuity & handoff brief
├── .env.example                     # Environment template (NO SECRETS)
└── .gitignore                       # Strict exclusion of weights, datasets, videos, caches
```

---

## 5. Frozen Model Integrity Registry

| Model Target | Architecture | Resolution | SHA-256 Checksum | Freeze Status |
| :--- | :--- | :--- | :--- | :--- |
| **Drone (VisDrone-Only)** | YOLOv8s | 1280x1280 | `343215ac779c1683eef66801b9d0fbf315361074ea71be4356bcb2a40d7a8a2f` | **FROZEN** |
| **Drone (Unified)** | YOLOv8s | 1280x1280 | `05281a43dc81ab015491fa1a7c821bdd9b9f13b1d78d80b2a0d549cf30a0a630` | **FROZEN** |
| **Satellite (DOTA OBB)** | YOLOv8n-OBB | 1024x1024 | `d96c42323b83826db9781981ef34c4c8673ddee9cf84ea0117e473ab040560dd` | **FROZEN** |
| **Damage (ResNet18)** | Siamese ResNet18 | 512x512 | `0dc2d422693030f5e2446b54e58bda896bc3ecfc05a250e8df78bf2648d61f6b` | **FROZEN** |

*Note: Large model binaries (`*.pt`, `*.pth`) and raw datasets are excluded from Git version control and maintained on local storage.*

---

## 6. Execution & Testing

### Running Runtime Contract & Normalizer Tests
```bash
python -m unittest discover -s tests/runtime -p "test_*.py" -v
```

### Running Real End-to-End ML Integration Tests
```bash
python tests/runtime/test_real_integration.py -v
```

### Basic Orchestrator Usage
```python
from aerion_orchestrator import AERIONOrchestrator

# Initialize orchestrator for disaster analysis
orchestrator = AERIONOrchestrator(mode="disaster", device=0)

# Process an aerial image
result = orchestrator.process_image("path/to/aerial_image.jpg", source_type="drone")

# Convert to clean JSON
json_output = result.to_json(indent=2)
print(json_output)
```

---

## 7. Security Policy

* Do not commit `.env` files or API secrets.
* Copy `.env.example` to `.env` and populate `MISTRAL_API_KEY` for optional advisory reporting.
* Model inference and perception operate 100% locally and offline.
