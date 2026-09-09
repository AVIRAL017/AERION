# AERION — Aerial Reconnaissance & Intelligence Operations Network

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141.1-009688.svg)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18.3.1-61DAFB.svg)](https://react.dev/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.6.0%2Bcu124-EE4C2C.svg)](https://pytorch.org/)
[![Status](https://img.shields.io/badge/Status-Phase%205%20Accepted-success.svg)]()

AERION is an advanced multi-modal defense and disaster situational awareness platform integrating aerial/drone computer vision, satellite oriented bounding box (OBB) object detection, bi-temporal Siamese structural damage assessment, real-time border surveillance geofencing, and protocol-grounded advisory incident intelligence.

---

## 1. Dual Operational Modes

### 1.1 Border Security & Geofence Surveillance Mode
- **Aerial Drone Perception**: High-resolution person and vehicle detection using frozen YOLOv8s models.
- **Multi-Object Tracking**: Trajectory persistence and motion vectors calculated via ByteTrack.
- **Geofencing & Breach Detection**: Point-in-polygon containment, boundary projection, and dwell timing.
- **Honest Terminology**: All crossing activities are classified strictly as **`POTENTIAL UNAUTHORIZED CROSSING INDICATOR`** and require human operator verification. Never presents unconfirmed infiltration as established fact.

### 1.2 Disaster Response & Structural Assessment Mode
- **Bi-Temporal Damage Assessment**: Siamese ResNet18 + U-Net skip decoder analyzing pre- and post-disaster optical imagery (`512x512`), computing probability change maps and quantifying structural damage at frozen decision threshold `0.50`.
- **Topological Evacuation Routing**: Evaluates genuine road network corridors via OpenRouteService avoiding active flood and disaster hazard boundaries.
- **Shelter Coordination**: Tracks authorized civil protection shelters, capacities, and generator capabilities.
- **Road Accessibility Invariant**: Road segments are only marked `BLOCKED` when corroborated by verified damage or obstruction evidence.

---

## 2. Frozen Machine Learning Models

All four machine learning models are officially **FROZEN** with cryptographic SHA-256 hashes recorded in authoritative manifests:

| Model | Subsystem | Architecture | Resolution | SHA-256 Checksum |
| :--- | :--- | :--- | :--- | :--- |
| **Drone** | Aerial Land Surveillance | YOLOv8s | `1280x1280` | `343215ac779c1683eef66801b9d0fbf315361074ea71be4356bcb2a40d7a8a2f` |
| **Unified Drone** | Land + Maritime Aerial | YOLOv8s | `1280x1280` | `05281a43dc81ab015491fa1a7c821bdd9b9f13b1d78d80b2a0d549cf30a0a630` |
| **Satellite** | Satellite OBB Detection | YOLOv8n-OBB | `1024x1024` | `d96c42323b83826db9781981ef34c4c8673ddee9cf84ea0117e473ab040560dd` |
| **Damage** | Bi-Temporal Damage | Siamese ResNet18 | `512x512` | `0dc2d422693030f5e2446b54e58bda896bc3ecfc05a250e8df78bf2648d61f6b` |

**Frozen Runtime Thresholds**:
- Confidence: `0.25`
- IoU: `0.50`
- Damage Decision Threshold: `0.50`

---

## 3. Core Architectural Principles

1. **Zero Fabrication Policy**: Never invent fake detections, tracks, counts, coordinates, weather, risk scores, routes, shelters, or sensor readings. When data is unavailable, the system explicitly reports `UNAVAILABLE` or `INSUFFICIENT EVIDENCE`.
2. **Mistral AI is Advisory Only**: The LLM synthesizes concise 5-6 sentence operational advisories strictly bounded to verified facts. It is never the source of truth and is fail-safe with deterministic fallback protocols.
3. **Coordinate Separation**: Cartesian image/pixel space (`[0, 0]` to `[W, H]`) is strictly segregated from geospatial WGS84 EPSG:4326 geometry.
4. **Hardware Optimized**: Engineered to run reliably on an NVIDIA RTX 3050 (6 GB VRAM) using asynchronous GPU lock serialization and lazy model loading.
5. **No Secret Leaks**: Zero credentials or secret tokens tracked in Git.

---

## 4. Repository Structure

```text
D:\mp-1\
├── app/                              # FastAPI Backend Architecture
│   ├── api/                          # REST route controllers (/auth, /health, /router)
│   ├── core/                         # Config, security, errors, logging, jobs, GPU lock
│   ├── db/                           # PostgreSQL 16 + PostGIS models, sessions, repos
│   ├── runtime/                      # Adapter boundary isolating frozen ML orchestrator
│   ├── schemas/                      # Pydantic schemas (auth, evidence, situation, health)
│   └── services/                     # Application services (perception, situation engine)
├── frontend/                         # React 18 + TypeScript + Vite Desktop Client
│   ├── src/                          # Pages, components, api client, context, layout
│   └── package.json                  # Frontend dependencies
├── data/                             # Dataset Registry & Geospatial Metadata
│   ├── geospatial/                   # State, district, hazard, road metadata & layers
│   └── README.md                     # Comprehensive dataset policy
├── docs/                             # Structured System Documentation
│   ├── architecture/                 # System architecture & design contracts
│   ├── api/                          # REST API endpoint catalog
│   ├── ml/                           # Frozen model weights & runtime contracts
│   ├── geospatial/                   # Geospatial rules & boundary handling
│   ├── deployment/                   # Production deployment guide
│   └── phases/                       # Project progression log
├── tests/                            # Automated Verification Test Suite
│   ├── backend/                      # 83 backend unit and integration tests (PASS)
│   └── runtime/                      # 26 runtime ML contract & integration tests (PASS)
├── test_results/                     # Cryptographic freeze records & manifests
├── alembic/                          # PostGIS database migrations
├── .env.example                      # Production environment template
├── .gitignore                        # Git exclusion rules
└── requirements.txt                  # Python runtime dependencies
```

---

## 5. Development & Testing

### 5.1 Environment Setup
```powershell
# Activate local virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies if needed
pip install -r requirements.txt
```

### 5.2 Running the Backend
```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 5.3 Running the Frontend
```powershell
cd frontend
npm install
npm run dev
```

### 5.4 Test Suite Execution
```powershell
# Run backend test suite (83 tests)
python -m unittest discover -s tests/backend -p "test_*.py"

# Run runtime test suite (26 tests)
python -m unittest discover -s tests/runtime -p "test_*.py"

# Test frontend production build
cd frontend
npm run build
```

---

## 6. Security & Confidentiality

- **Never commit `.env`** or plaintext API keys.
- Store sensitive configuration variables in operating system environment variables or secure key vaults.
- Configure explicit origins in `ALLOWED_ORIGINS` for production deployment. Wildcards (`*`) are strictly blocked in production mode.
