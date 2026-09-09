# AERION — Annotated Visual Evidence Pipeline Architecture
**Document Version:** 1.0.0  
**Roadmap Step:** 15 — Annotated Visual Evidence  
**Status:** COMPLETE & VERIFIED  

---

## 1. Purpose
The **Annotated Visual Evidence Pipeline** converts perception outputs from AERION's frozen ML models (`AERIONAnalysisResult`) into persistent, tamper-evident visual artifacts.

### Key Architectural Invariants:
- **Presentation & Evidence Only**: The annotation layer **NEVER** performs detection or modifies detector thresholds, classes, or outputs. It is strictly a consumer of runtime detection contracts.
- **Source Immutability**: The source image is never overwritten. The generated annotated image is stored as an independent, derived artifact.
- **Truthful Geometry**:
  - Drone detections are rendered with axis-aligned bounding rectangles and confidence values formatted cleanly without mutating source floating-point values.
  - Satellite detections preserve the 4-corner Oriented Bounding Box (OBB) polygon geometry in pixel space. They are **never** collapsed to axis-aligned boxes.
  - Coordinates remain in pixel space. Georeferencing is never fabricated.
- **Honest Zero-Detection State**: When zero detections are produced, no artificial boxes are generated. A restrained visual indicator (`"NO DETECTIONS (COUNT = 0)"`) is rendered, truthfully representing the operational result.

---

## 2. Architecture & Data Flow

```
Frozen ML Detector (YOLOv8 / DOTA OBB / Siamese)
                       ↓
            AERION Runtime Contract
                       ↓
              AERIONAnalysisResult
                       ↓
               AnnotationService
         [app/services/annotation_service.py]
                       ↓
            LocalArtifactStorage
           [storage/<project_id>/annotated_image/<uuid>.jpg]
                       ↓
               Evidence Record
        [modality="DERIVED", parent_evidence_ids]
                       ↓
        FastAPI Response Envelope & Frontend
  [Preview Base64 + SHA-256 Verified Artifact Key]
```

---

## 3. Input & Output Contracts

### Input Contract:
`AnnotationService.annotate_and_store(source_image_path, analysis_result, project_id)`
- `source_image_path`: Path or string pointing to valid aerial/satellite source image (sanitized via `sanitize_local_path`).
- `analysis_result`: Valid `AERIONAnalysisResult` dataclass containing perception results.
- `project_id`: Tenant UUID for storage and audit partitioning.

### Output Contract:
`AnnotationResult`:
- `artifact_key`: Canonical storage path key (`<project_id>/annotated_image/<uuid>.jpg`).
- `sha256`: Cryptographic SHA-256 digest computed across stored bytes.
- `file_size_bytes`: Stored file size in bytes.
- `mime_type`: Image MIME type (`image/jpeg`).
- `image_width` / `image_height`: Verified pixel dimensions.
- `detection_count`: Integer count of rendered detections.
- `annotated_base64`: Base64-encoded string for zero-leakage API preview transmission.
- `is_zero_detection`: Boolean flag indicating zero-detection state.

---

## 4. Drone Bounding Box Rendering
- Bounding boxes are rendered in pixel space using OpenCV (`cv2.rectangle`).
- Colors are assigned deterministically via `CLASS_PALETTE_BGR` mapping VisDrone and DOTA object classes to distinct high-contrast palettes (e.g. Pedestrian = Neon Cyan, Car = Amber, Truck = Red).
- Label tags include the class name and formatted confidence (e.g., `PEDESTRIAN 0.81`).
- Line thickness and font scale dynamically adapt to image resolution to maintain legibility on both low-res crops and 4K aerial frames.

---

## 5. Satellite OBB Rendering
- Preserves all four vertices of the Oriented Bounding Box (`Point2DCoord[4]`).
- Polygons are drawn using `cv2.polylines` with closed contour loops.
- Labels are positioned relative to the top-most vertex of the polygon to prevent occlusion.
- Pixel coordinates are strictly maintained in image space.

---

## 6. Zero-Detection Behavior
- If `len(analysis_result.detections) == 0`:
  - A clean copy of the original image is preserved.
  - A restrained, high-contrast banner is stamped along the bottom edge:
    `AERION TELEMETRY — VERIFIED SCENE ANALYSIS: NO DETECTIONS (COUNT = 0)`
  - No synthetic bounding boxes or phantom classes are generated.
  - `is_zero_detection` is set to `True`.

---

## 7. Artifact Storage & Path Containment
- Artifacts are stored via `LocalArtifactStorage`.
- Storage directory layout:
  `storage/<project_id>/annotated_image/<uuid>.jpg`
- Path traversal defenses ensure destination files are strictly contained within `settings.STORAGE_LOCAL_ROOT`.
- Filenames use cryptographically secure UUIDv4 identifiers; user-supplied paths or filenames are never used as destination file names.

---

## 8. SHA-256 Integrity & Provenance
- Before returning the `AnnotationResult`, a full SHA-256 hash is computed from the written disk artifact chunk-by-chunk.
- The resulting digest is stored in `AnnotationResult.sha256` and recorded in the database `EvidenceRecord.sensor_metadata`.

---

## 9. Evidence Lineage & Database Model Linkage
- Integrated into `AnalysisPersistenceService.persist_analysis(...)`:
  - Modality is set to `DERIVED` (the original image is `OBSERVED`).
  - `parent_evidence_ids` links the annotated artifact directly to the parent detection evidence records.
  - `source_type` is tagged as `ANNOTATED_VISUAL_EVIDENCE_<SOURCE>`.
  - `raw_payload_uri` stores the canonical `artifact_key`.
  - Verified that database schema migrations are **not** needed: uses existing `EvidenceRecord` table columns seamlessly.

---

## 10. Security Controls
1. **Path Traversal Defense**: All input paths are validated with `sanitize_local_path`.
2. **Null Byte Prohibitions**: Prohibits `\0` in file path parameters.
3. **MIME & Extension Enforcement**: Allowed extensions restricted to `{.jpg, .jpeg, .png, .tif, .tiff}`.
4. **Information Disclosure Prevention**: Absolute server filesystem paths are never returned to clients; only tenant-relative `artifact_key` and base64 previews are exposed.

---

## 11. Resource Controls
1. **Dimension Ceiling**: Images exceeding 8192x8192 are rejected before OpenCV decoding.
2. **File Size Limit**: Hard ceiling of 100 MB for annotation targets.
3. **Deterministic Cleanup**: All intermediate buffers and temporary scratch directories are created with `tempfile.mkdtemp(prefix="aerion_annot_")` and cleaned in `finally` blocks.

---

## 12. API Integration
- `POST /api/v1/analysis/image`:
  - Runs frozen perception detector.
  - Calls `AnnotationService.annotate_and_store(...)`.
  - Attaches `annotated_artifact` metadata and `annotated_image_base64` preview to `ResponseEnvelope.data`.
  - Safely persists analysis and links derived evidence artifact key.
  - Gracefully falls back if annotation fails, ensuring analysis responses never crash.

---

## 13. Frontend Integration
- **Border Dashboard (`frontend/src/pages/BorderPage.tsx`)**:
  - Added visual evidence toggle: `[ANNOTATED EVIDENCE] | [RAW INGEST]`.
  - Defaults to displaying the backend-generated authoritative annotated JPEG artifact (`data:image/jpeg;base64,...`).
  - Displays `"BACKEND DERIVED ARTIFACT (SHA-256 VERIFIED)"` indicator badge.
  - Falls back to raw ingest with interactive SVG bounding boxes/polygons when toggled.
  - Displays honest zero-detection banner when `detections.length === 0`.
- **TypeScript Contracts (`frontend/src/types/index.ts`)**:
  - Added `annotated_image_base64?: string | null` to `AERIONAnalysisResultData`.

---

## 14. Testing & Verification
- Unit & Integration tests in `tests/backend/test_annotation_service.py`:
  - Drone bounding box annotation & color palette validation.
  - Satellite 4-corner OBB rendering.
  - Honest zero-detection banner validation.
  - Original source image byte immutability.
  - Path traversal and null-byte rejection.
  - Evidence lineage and `DERIVED` modality persistence.
- Verified test suite: `151 passed` in backend and runtime test suites.
- Verified frontend build: `npm run build` completed with zero TypeScript errors.

---

## 15. Known Limitations
- Current implementation renders annotations as high-quality JPEG artifacts. Future iterations can add optional lossless PNG rendering for ultra-fine satellite rasters.
- Bi-temporal damage pairs currently render color-coded change masks via their respective Siamese inference endpoints; unified bi-temporal side-by-side composite annotation can be added in a future enhancement.

---

## 16. Future S3 / Object Storage Compatibility
`LocalArtifactStorage` and `AnnotationResult.artifact_key` use relative path keys (`<project_id>/<asset_type>/<uuid>.<ext>`), allowing direct one-to-one mapping with AWS S3 / Google Cloud Storage bucket keys without refactoring business logic or database schemas.
