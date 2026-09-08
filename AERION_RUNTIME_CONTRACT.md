# AERION v1 — Unified Runtime Contract Documentation

**Status**: FROZEN ML ADAPTATION LAYER  
**Author**: Antigravity (Google DeepMind)  
**Date**: 2026-09-08  
**Architecture Layer**: Phase 1 (Normalization & Unified Contracts)  

---

## 1. Purpose & Scope

The AERION v1 Runtime Contract establishes a stable, persistence-agnostic, and serialization-safe runtime interface above the frozen ML models and validated perception pipelines.

It bridges low-level tensor/matrix inference routines and high-level mission orchestrators without modifying model weights, altering dataset labels, or requiring third-party web frameworks.

```
+-------------------------------------------------------------------------+
|                              FROZEN ML                                  |
|  - VisDrone YOLOv8s         - Unified Drone YOLOv8s                     |
|  - Satellite YOLOv8n-OBB    - Siamese ResNet18 Damage Model             |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                      EXISTING RUNTIME ADAPTERS                          |
|  - drone_detector.py        - satellite_detector.py                     |
|  - damage_inference.py      - border_pipeline.py                        |
|  - intelligence_engine.py   - protocols.py                              |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                         AERION NORMALIZATION                            |
|  (aerion_runtime_normalizer.py)                                         |
|  - normalize_drone_result()                                             |
|  - normalize_satellite_result()                                         |
|  - normalize_damage_result()                                            |
|  - normalize_border_result()                                            |
|  - normalize_intelligence_result()                                      |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                       AERION UNIFIED CONTRACTS                          |
|  (aerion_runtime_contracts.py)                                          |
|  - Point2D, BoundingBox, Detection                                      |
|  - TrackState, BorderAnalysis, DamageAnalysis                           |
|  - IntelligenceItem, SceneSummary                                       |
|  - AERIONAnalysisResult                                                 |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                         AERION ORCHESTRATOR                             |
|  (aerion_orchestrator.py)                                               |
|  - process_image()          - process_change_pair()                     |
|  - process_border_frame()   - generate_advisory_report()                |
+-------------------------------------------------------------------------+
```

---

## 2. Public Runtime Contracts (`aerion_runtime_contracts.py`)

All contracts are built with pure standard library `@dataclass` definitions and guarantee JSON-clean serialization.

### 2.1 Geometric Contracts

#### `Point2D`
Represents a 2D Cartesian point in image pixel coordinates.
* `x: float`: Horizontal coordinate.
* `y: float`: Vertical coordinate.
* `to_dict() -> Dict[str, float]`

#### `BoundingBox`
Axis-aligned 2D bounding box in pixel coordinates.
* `x1: float`: Left horizontal bound.
* `y1: float`: Top vertical bound.
* `x2: float`: Right horizontal bound.
* `y2: float`: Bottom vertical bound.
* Invariant: Enforces `x1 <= x2` and `y1 <= y2`. Raises `ValueError` on inverted coordinates.

### 2.2 Perception & Detection Contract

#### `Detection`
Represents a single detected entity across drone, satellite, and ground modes.
* `source: str`: Originating detector profile (`"drone"`, `"satellite"`, `"border"`).
* `class_id: int`: Model output category ID.
* `class_name: str`: Resolved taxonomy class label.
* `confidence: float`: Detection confidence score `[0.0, 1.0]`.
* `bbox: Optional[BoundingBox]`: Axis-aligned bounding box.
* `obb_points: Optional[List[Point2D]]`: Exactly 4 corner vertices for oriented bounding boxes.
* `track_id: Optional[int]`: Temporal identity from ByteTrack when tracking is active.
* `frame_number: Optional[int]`: Video sequence index.
* Rule: Preserves full OBB vertices without discarding them when deriving horizontal bboxes.

### 2.3 Damage Assessment Contract

#### `DamageAnalysis`
Summary of bi-temporal change detection and damage quantification.
* `before_width: int`, `before_height: int`: Baseline image resolution.
* `after_width: int`, `after_height: int`: Post-disaster image resolution.
* `probability_min: float`, `probability_max: float`, `probability_mean: float`: Distribution stats of damage logit probabilities `[0.0, 1.0]`.
* `threshold: float`: Decision threshold (frozen at `0.50`).
* `damage_pixels: int`: Number of damaged pixels (`prob >= threshold`).
* `total_pixels: int`: Total evaluated image pixels.
* `damage_ratio: float`: Fraction of damaged area `[0.0, 1.0]`.
* `damage_percentage: float`: Percentage of damaged area `[0.0, 100.0]`.
* `probability_map_available: bool`: Flag indicating probability tensor is cached in memory.
* `damage_mask_available: bool`: Flag indicating binary mask array is cached in memory.
* Note: Complete pixel arrays are **never** serialized into JSON payloads.

### 2.4 Tracking & Surveillance Contracts

#### `TrackState`
Enriched object trajectory and motion state over a sliding temporal window.
* `track_id: int`: Persistent track ID.
* `class_id: Optional[int]`, `class_name: Optional[str]`: Entity classification.
* `confidence: float`: Detection confidence.
* `bbox: BoundingBox`: Current spatial bounds.
* `center: Point2D`: Current centroid `(cx, cy)`.
* `previous_center: Optional[Point2D]`: Prior centroid position.
* `frames_seen: int`: Cumulative track duration.
* `movement_distance: float`: Frame-to-frame Euclidean pixel distance.
* `displacement: float`: Net displacement from start of tracking window.
* `direction: str`: Cardinal motion direction (`"north"`, `"south-east"`, `"stationary"`, etc.).
* `persistence: float`: Reliability metric `[0.0, 1.0]`.

#### `BorderAnalysis`
High-level geofencing threat metrics and alert filtering states.
* `track_id: Optional[int]`: Track identifier.
* `inside_restricted_zone: Optional[bool]`: Ray-casting polygon intersection flag.
* `distance_to_zone: Optional[float]`: Euclidean pixel distance to boundary.
* `previous_distance_to_zone: Optional[float]`: Boundary distance on preceding frame.
* `approach_score: Optional[float]`: Velocity toward geofence `1.0` if closing distance, `0.0` otherwise.
* `direction_relation: Optional[str]`: `"entering_zone"`, `"toward_boundary"`, `"deeper_inside"`, `"away_from_boundary"`, `"stationary"`, `"parallel"`.
* `direction_alignment: Optional[float]`: Boundary normal dot product `[-1.0, 1.0]`.
* `direction_score: Optional[float]`: Threat score contribution from motion vector.
* `zone_entry: Optional[bool]`: True on boundary breach transition.
* `zone_exit: Optional[bool]`: True on boundary departure transition.
* `zone_status: Optional[str]`: `"INSIDE"` or `"OUTSIDE"`.
* `zone_dwell_frames: Optional[int]`: Continuous duration inside restricted area.
* `zone_dwell_score: Optional[float]`: Normalized dwell time metric `[0.0, 1.0]`.
* `border_activity_score: Optional[float]`: Weighted composite score `[0.0, 1.0]`.
* `border_priority: Optional[str]`: Threat priority (`"CRITICAL"`, `"HIGH"`, `"MEDIUM"`, `"LOW"`).
* `movement_score: Optional[float]`, `movement_inside_score: Optional[float]`: Motion intensity metrics.
* `moving_away: Optional[bool]`: True if trajectory vector diverges from boundary.
* `border_candidate: Optional[bool]`: True if candidate filter triggered.
* `border_alert: Optional[bool]`: True if filtered alert confirmed (respects cooldown).
* `alert_level: Optional[str]`: Filtered alert tier (`"CRITICAL"`, `"HIGH"`, `"NONE"`).

### 2.5 Intelligence & Summary Contracts

#### `IntelligenceItem`
Deterministic threat evaluation grounded in SSIM change signal and standard protocols.
* `object_class: str`: Target taxonomy class.
* `confidence: float`: Detection confidence.
* `class_weight: Optional[float]`: Configured static risk weight.
* `change_score: Optional[float]`: SSIM background-to-local drop ratio `[0.0, 1.0]`.
* `priority_score: Optional[float]`: Composite score: `0.5 * (weight * conf) + 0.5 * change_score`.
* `priority: Optional[str]`: `"Critical"`, `"High"`, `"Medium"`, or `"Low"`.
* `mode: Optional[str]`: `"disaster"` or `"border"`.
* `protocol: Optional[str]`: Standard operational advisory retrieved from `protocols.py`.
* `ai_report: Optional[str]`: Advisory text summary from LLM (if generated).
* `ai_report_error: Optional[str]`: Error description if LLM service was unreachable.

#### `SceneSummary`
Count of detections categorized by priority tier.
* `critical: int`, `high: int`, `medium: int`, `low: int`

### 2.6 Primary Public Result Contract

#### `AERIONAnalysisResult`
The unified envelope returned by all high-level orchestrator calls:
```python
@dataclass
class AERIONAnalysisResult:
    project: str = "AERION"
    version: str = "v1"
    analysis_id: Optional[str] = None
    mode: str = "disaster"                   # "disaster" | "border"
    source_type: str = "image"               # "drone" | "satellite" | "video" | "change_detection"
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    frame_number: Optional[int] = None

    detections: List[Detection]              # All normalized detections
    tracks: List[TrackState]                 # Active tracking states (empty if static image)
    border_analysis: List[BorderAnalysis]    # Border geofence assessments (empty if disaster mode)
    damage_analysis: Optional[DamageAnalysis]# Siamese damage stats (None if perception only)
    intelligence: List[IntelligenceItem]     # Prioritized scene assessments
    summary: SceneSummary                    # Priority counts
    overall_status: str                      # "detections_available", "border_alerts_available", etc.
    metadata: Dict[str, Any]                 # System and terrain metadata
```

---

## 3. Runtime Normalizers (`aerion_runtime_normalizer.py`)

Adapters mapping upstream data structures to contract instances:

1. **`normalize_drone_result(drone_result, frame_number, source)`**:
   Takes `DroneDetectionResult` (from `drone_detector.py`), maps bounding boxes to `BoundingBox`, and emits `Detection` instances with `source="drone"`.
2. **`normalize_satellite_result(satellite_result, frame_number, source)`**:
   Takes `SatelliteDetectionResult` (from `satellite_detector.py`), parses 4 corner points into `Point2D`, derives the enclosing `BoundingBox`, and preserves full `obb_points`.
3. **`normalize_damage_result(damage_output, threshold)`**:
   Takes `(before_img, after_img, prob_map, mask)` from `damage_inference.predict_damage()`, computes min/max/mean/count statistics, and builds `DamageAnalysis`.
4. **`normalize_border_result(border_output, frame_number, source, class_map)`**:
   Takes `List[Dict[str, Any]]` from `BorderPipeline.process_frame()`, separates fields into three parallel synchronized lists: `(detections, tracks, border_analyses)`.
5. **`normalize_intelligence_result(intelligence_output)`**:
   Takes `Dict[str, Any]` from `intelligence_engine.analyze_scene()`, maps scored items to `IntelligenceItem`, and tabulates `SceneSummary`.

---

## 4. Central Orchestrator (`aerion_orchestrator.py`)

### 4.1 Initialization & Resource Management
```python
orchestrator = AERIONOrchestrator(
    mode="disaster",               # "disaster" or "border"
    device=0,                      # GPU 0 (or "cpu")
    drone_model="visdrone_only",   # "visdrone_only" or "unified"
    confidence=0.25,
    iou=0.50,
    terrain_type="arid",           # Configured metadata
)
```
* **Lazy Loading**: Models are not loaded into VRAM on construction. The orchestrator defers loading until the specific subsystem method is invoked, protecting the 6 GB GPU memory budget.

### 4.2 Public Entry Points

* `detect_drone(image) -> DroneDetectionResult`: Direct call to frozen drone detector.
* `detect_satellite(image) -> SatelliteDetectionResult`: Direct call to frozen satellite OBB detector.
* `analyze_damage(before, after) -> DamageAnalysis`: Direct call to frozen Siamese ResNet18.
* `analyze_detections(detections, mode) -> Tuple[List[IntelligenceItem], SceneSummary]`: Deterministic priority ranking.
* `process_image(image, source_type, run_intelligence) -> AERIONAnalysisResult`: Complete perception + intelligence pipeline for static drone or satellite frames.
* `process_change_pair(before, after) -> AERIONAnalysisResult`: Complete bi-temporal disaster damage pipeline.
* `process_border_frame(frame, frame_number) -> AERIONAnalysisResult`: Real-time tracking + geofencing pipeline for video streams.
* `generate_advisory_report(detection) -> Dict[str, Any]`: Advisory LLM summary generation via Mistral API.

---

## 5. Authoritative vs Advisory Distinctions

| Subsystem / Field | Classification | Behavioral Rule |
| :--- | :--- | :--- |
| **Drone Detections** | **Authoritative** | Output strictly from frozen YOLOv8s weights. Never fabricated. |
| **Satellite OBB** | **Authoritative** | Output strictly from frozen YOLOv8n-OBB. Corner vertices immutable. |
| **Damage Metrics** | **Authoritative** | Output strictly from frozen Siamese ResNet18 (threshold 0.50). |
| **Tracking & Geofence** | **Authoritative** | Deterministic ray-casting geometry and ByteTrack associations. |
| **Priority Scoring** | **Authoritative** | Deterministic mathematical formula: `0.5 * (weight * conf) + 0.5 * change`. |
| **Configured Terrain** | **Metadata Only** | Static context dictionary configured by operator. **Not** an ML prediction. |
| **Mistral AI Reports** | **Advisory Only** | LLM text advisory. Can fail or be omitted without halting perception. |

---

## 6. Intentionally Excluded from Phase 1

To maintain architectural purity and obey project constraints, Phase 1 strictly excludes:
* **No Database**: No PostgreSQL, SQLite, or SQLAlchemy models.
* **No Vector Index**: No ChromaDB or embedding models.
* **No Web Server**: No FastAPI, Flask, or REST controllers.
* **No Frontend**: No React, Next.js, or HTML dashboards.
* **No Model Retraining**: Frozen weights are strictly read-only.
