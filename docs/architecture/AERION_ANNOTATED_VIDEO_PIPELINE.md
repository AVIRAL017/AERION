# AERION — Annotated Video Evidence Pipeline Architecture
**Document Version:** 1.0.0  
**Roadmap Step:** 16 — Annotated Video Evidence Pipeline  
**Status:** COMPLETE & VERIFIED  

---

## 1. Executive Summary & Purpose
The **Annotated Video Evidence Pipeline** provides deterministic, presentation-grade, tamper-evident annotated video evidence artifacts directly from AERION's frozen video perception detector and ByteTrack tracker.
It transforms recorded border surveillance footage into an authoritative MP4 video artifact showing the exact bounding boxes, class labels, confidences, tracking identifiers, historical pixel trajectory tails, and configured border zone boundaries without fabricating intelligence, interpolating future movements, or converting image-space coordinates into pseudo-geography.

---

## 2. Core Production Invariants
1. **Zero Fabrication**:
   - Detections, class labels, and confidence values strictly originate from the frozen perception detector for each processed frame.
   - Track IDs originate exclusively from ByteTrack via `BorderTracker`.
   - Trajectory tails are drawn exclusively from verified historical centroids in pixel coordinates (`history[track_id]`).
   - No future positions, velocity vectors, or unverified geographic coordinates are rendered.
2. **Frozen ML Immutability**:
   - Drone VisDrone YOLOv8s (`343215ac...`), Satellite DOTA OBB (`d96c4232...`), Siamese Damage ResNet-18 (`0dc2d422...`), and Unified Drone (`05281a43...`) models and hashes remain strictly unchanged.
3. **Source Video Immutability**:
   - The original ingested video file bytes are never overwritten or mutated.
   - Annotated output is stored as an independent derived artifact in `LocalArtifactStorage`.
4. **Memory Safety & Sequential Processing**:
   - Video frames are processed sequentially using generator streaming.
   - Decoded raw frames are never buffered in system RAM simultaneously.
   - Streaming write via OpenCV `VideoWriter` directly flushes processed frames to disk.
5. **No Database Schema Changes**:
   - Reuses existing `EvidenceRecord` table with `modality="DERIVED"` and `source_type="ANNOTATED_VISUAL_EVIDENCE_VIDEO"`.

---

## 3. Architecture & Data Flow

```
Raw Border Surveillance Video (.mp4)
                 ↓
      BorderVideoJobService (cv2.VideoCapture)
                 ↓
      Sequential Frame Decoding (1 frame in RAM)
                 ↓
      RuntimeManager.run_border_frame_inference
        ↳ Serialized GPU Mutex Lock
        ↳ AERIONOrchestrator.process_border_frame
        ↳ BorderPipeline (YOLOv8 + ByteTrack + BorderTracker)
        ↳ SituationEngine.ingest_runtime_result
                 ↓
      Real Detections & Tracker State
        ↳ Bounding boxes, class names, confidences
        ↳ Track IDs (e.g. ID:42)
        ↳ Trajectory history: tracker.history[track_id]
        ↳ Border zone boundary: pipeline.zone_polygon
                 ↓
      VideoAnnotationService.annotate_frame
        ↳ Bounded trajectory polyline (amber)
        ↳ Class-specific bounding box & badge (neon cyan/amber/red)
        ↳ Format: "CLASS CONF ID:<track_id>"
        ↳ Configured border zone boundary overlay
        ↳ Telemetry header watermark
                 ↓
      Streaming cv2.VideoWriter (fourcc='mp4v')
                 ↓
      LocalArtifactStorage.store_file
        ↳ Target: storage/<project_id>/annotated_video/<uuid>.mp4
        ↳ Cryptographic SHA-256 computed on completed disk bytes
                 ↓
      AnalysisPersistenceService (PostgreSQL 18.6)
        ↳ DBEvidenceRecord (modality="DERIVED", parent_evidence_ids)
                 ↓
      FastAPI Response Envelope (POST /api/v1/analysis/border/video)
        ↳ Returns artifact_key, sha256, fps, frame_count, codec
                 ↓
      Frontend BorderPage.tsx (React + TypeScript + Vite)
        ↳ Toggle: [ANNOTATED EVIDENCE] | [RAW INGEST]
        ↳ Autoritative derived video playback
        ↳ Badge: "BACKEND DERIVED VIDEO EVIDENCE (SHA-256 VERIFIED)"
```

---

## 4. Codec & Container Specification
- **Primary Codec**: `mp4v` (MPEG-4 Part 2) in standard `.mp4` container.
- **Rationale**: Tested and verified out of the box in OpenCV on Windows environments without external GPL/commercial DLL dependencies (e.g., OpenH264 DLL).
- **Fallback Chain**: `mp4v` → `avc1` → `XVID`.
- **Verified Output**: Produces fully valid, seekable, playable MP4 files verifiable by OpenCV `VideoCapture` and browser HTML5 video elements.

---

## 5. Artifact Storage & Metadata
Derived video artifacts are stored via `LocalArtifactStorage` under:
```
storage/<project_id>/annotated_video/<uuid>.mp4
```
**Metadata Recorded & Returned:**
- `artifact_key`: Canonical tenant-relative storage key (e.g. `00000000-0000-0000-0000-000000000001/annotated_video/<uuid>.mp4`)
- `sha256`: Cryptographic SHA-256 hash computed on written disk bytes
- `file_size_bytes`: Integer size of the final video file
- `mime_type`: `video/mp4`
- `width` / `height`: Decoded video dimensions
- `fps`: Effective frames per second
- `frame_count`: Number of processed frames written to artifact
- `source_frame_count`: Total frames present in original source video
- `codec`: Fourcc string identifier (`mp4v`)
- `duration_seconds`: Video duration calculated from `frame_count / fps`
- `unique_tracks_count`: Count of distinct track IDs observed across all processed frames
- `total_detections_count`: Sum of all detections across processed frames

---

## 6. Evidence Lineage & PostgreSQL Persistence
- Persisted in PostgreSQL table `evidence_records`:
  - `id`: Unique UUIDv4
  - `project_id`: Tenant UUID
  - `parent_evidence_ids`: Array of parent detection `evidence_id` UUIDs
  - `source_type`: `ANNOTATED_VISUAL_EVIDENCE_VIDEO`
  - `temporal_mode`: `RECORDED_FOOTAGE`
  - `modality`: `DERIVED`
  - `confidence`: `1.0` (indicates verified generation)
  - `verification_state`: `CALCULATED`
  - `raw_payload_uri`: Canonical `artifact_key`
  - `sensor_metadata`:
    - `artifact_type`: `"annotated_video"`
    - `detection_count`: Total detections in analyzed frames
    - `analysis_id`: Associated analysis UUID

---

## 7. Security Controls
1. **Path Traversal Defense**: All video file paths are sanitized via `sanitize_local_path`. Traversal strings (`../`) and null bytes (`\0`) are strictly rejected.
2. **File Size Bounds**: Videos exceeding 150 MB ceiling are rejected prior to decoding.
3. **MIME / Extension Enforcement**: Only permitted extensions (`.mp4`, `.avi`, `.mov`, `.mkv`) are accepted.
4. **Information Disclosure Prevention**: Absolute filesystem paths are never returned over HTTP; only relative keys and metadata are exposed.
5. **Deterministic Cleanup**: Temporary video files and scratch folders are unlinked and cleaned in `finally` blocks.

---

## 8. Real Validation Results (Measured)
- **Source Video Asset**: `D:\mp-1\border_test_videos\border_test_urban.mp4.mp4`
- **Source Properties**: 3840x2160 (4K UHD), 24.0 FPS, 725 frames
- **Execution Run**: Sequential bounded run (30 frames, stride=5) with real frozen YOLOv8 detector and ByteTrack
- **Measured Outputs**:
  - **Processed Frames**: 30
  - **Output Dimensions**: 3840 x 2160
  - **Effective FPS**: 4.8
  - **Processing Time**: 19.57 s
  - **Total Detections**: 1,080
  - **Unique Track IDs**: 77
  - **Codec**: `mp4v`
  - **Artifact Size**: 10,102,991 bytes (~9.63 MB)
  - **SHA-256 Digest**: `8e1f960ee04745bbe2fe15db5e66673a993e3d3bf1c10bd27dae1e52553a2e48`
  - **Visual Verification**: Extracted frames 0, 10, 20, 29 confirmed presence of telemetry header, cyan/amber bounding boxes and badges (`PERSON <conf> ID:<id>`, `CAR <conf> ID:<id>`), trajectory tails, and configured border zone boundary.
