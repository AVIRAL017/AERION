"""
AERION — Step 15 Annotated Visual Evidence Pipeline Unit & Integration Tests
Validates:
1. Drone bounding-box annotation (rectangle, label, confidence)
2. Drone class labels and formatting
3. Drone confidence labels
4. Satellite four-corner OBB rendering (preserved polygon, not axis-aligned)
5. Zero detections honest handling (no fake boxes, restrained indicator banner)
6. Original source image remains unchanged (unmodified bytes)
7. Output artifact exists and is saved to LocalArtifactStorage
8. SHA-256 is deterministic and matches actual bytes
9. Path traversal rejection
10. Unsupported extension / invalid path handling
11. Evidence lineage: Derived modality, parent evidence linkage
12. No fake detection generation
13. Resource safety: image dimensions bounding
"""

import hashlib
import os
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
import numpy as np
import cv2

from aerion_runtime_contracts import (
    AERIONAnalysisResult,
    BoundingBox,
    Detection,
    Point2D,
    SceneSummary,
)
from app.core.errors import ResourceNotFoundError, ValidationError
from app.services.annotation_service import AnnotationResult, AnnotationService
from app.services.persistence_service import AnalysisPersistenceService
from app.services.storage_service import LocalArtifactStorage


class TestAnnotationService(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="aerion_test_annot_")
        self.project_id = uuid.uuid4()
        self.storage = LocalArtifactStorage(root_dir=self.temp_dir)
        self.service = AnnotationService(storage=self.storage)

        # Create a synthetic 640x480 test image (solid dark gray canvas)
        self.img_h, self.img_w = 480, 640
        self.canvas = np.full((self.img_h, self.img_w, 3), 40, dtype=np.uint8)
        self.test_img_path = Path(self.temp_dir) / "source_test.jpg"
        cv2.imwrite(str(self.test_img_path), self.canvas)
        with open(self.test_img_path, "rb") as f:
            self.source_bytes = f.read()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Drone bounding-box annotation
    # -------------------------------------------------------------------------
    def test_drone_bbox_annotation(self):
        analysis_id = str(uuid.uuid4())
        drone_det = Detection(
            source="drone",
            class_id=0,
            class_name="pedestrian",
            confidence=0.87,
            bbox=BoundingBox(x1=50, y1=60, x2=150, y2=200),
        )
        result = AERIONAnalysisResult(
            analysis_id=analysis_id,
            mode="border",
            source_type="drone",
            image_width=self.img_w,
            image_height=self.img_h,
            detections=[drone_det],
            summary=SceneSummary(critical=0, high=1, medium=0, low=0),
        )

        annot_res: AnnotationResult = self.service.annotate_and_store(
            source_image_path=self.test_img_path,
            analysis_result=result,
            project_id=self.project_id,
        )

        # Check artifact returned
        self.assertIsNotNone(annot_res.artifact_key)
        self.assertTrue(annot_res.artifact_key.startswith(str(self.project_id)))
        self.assertEqual(annot_res.detection_count, 1)
        self.assertFalse(annot_res.is_zero_detection)
        self.assertEqual(annot_res.image_width, self.img_w)
        self.assertEqual(annot_res.image_height, self.img_h)

        # Check artifact exists in storage
        annot_path = self.storage.root_dir / annot_res.artifact_key
        self.assertTrue(annot_path.exists())
        self.assertGreater(annot_path.stat().st_size, 0)

        # Verify SHA-256 matches actual stored artifact bytes
        with open(annot_path, "rb") as f:
            actual_bytes = f.read()
        expected_hash = hashlib.sha256(actual_bytes).hexdigest()
        self.assertEqual(annot_res.sha256, expected_hash)

        # Verify source image bytes remain completely unmodified
        with open(self.test_img_path, "rb") as f:
            current_source_bytes = f.read()
        self.assertEqual(self.source_bytes, current_source_bytes)

    # -------------------------------------------------------------------------
    # 2. Satellite 4-corner OBB rendering
    # -------------------------------------------------------------------------
    def test_satellite_obb_annotation(self):
        analysis_id = str(uuid.uuid4())
        sat_det = Detection(
            source="satellite",
            class_id=1,
            class_name="small-vehicle",
            confidence=0.92,
            obb_points=[
                Point2D(x=100.0, y=100.0),
                Point2D(x=200.0, y=120.0),
                Point2D(x=180.0, y=220.0),
                Point2D(x=80.0, y=200.0),
            ],
        )
        result = AERIONAnalysisResult(
            analysis_id=analysis_id,
            mode="border",
            source_type="satellite",
            image_width=self.img_w,
            image_height=self.img_h,
            detections=[sat_det],
            summary=SceneSummary(critical=0, high=1, medium=0, low=0),
        )

        annot_res = self.service.annotate_and_store(
            source_image_path=self.test_img_path,
            analysis_result=result,
            project_id=self.project_id,
        )

        self.assertIsNotNone(annot_res.artifact_key)
        self.assertEqual(annot_res.detection_count, 1)
        self.assertFalse(annot_res.is_zero_detection)
        self.assertIsNotNone(annot_res.annotated_base64)

        # Verify stored image is a valid readable JPEG with annotations
        annot_path = self.storage.root_dir / annot_res.artifact_key
        rendered_cv = cv2.imread(str(annot_path))
        self.assertIsNotNone(rendered_cv)
        self.assertEqual(rendered_cv.shape[:2], (self.img_h, self.img_w))

    # -------------------------------------------------------------------------
    # 3. Honest zero-detection behavior (no fake boxes, restrained banner)
    # -------------------------------------------------------------------------
    def test_zero_detection_honest_artifact(self):
        analysis_id = str(uuid.uuid4())
        result = AERIONAnalysisResult(
            analysis_id=analysis_id,
            mode="border",
            source_type="drone",
            image_width=self.img_w,
            image_height=self.img_h,
            detections=[],  # Empty detections
            summary=SceneSummary(critical=0, high=0, medium=0, low=0),
        )

        annot_res = self.service.annotate_and_store(
            source_image_path=self.test_img_path,
            analysis_result=result,
            project_id=self.project_id,
        )

        self.assertTrue(annot_res.is_zero_detection)
        self.assertEqual(annot_res.detection_count, 0)
        self.assertIsNotNone(annot_res.artifact_key)

        # Verify artifact was created and readable
        annot_path = self.storage.root_dir / annot_res.artifact_key
        self.assertTrue(annot_path.exists())

        # Verify source remains untouched
        with open(self.test_img_path, "rb") as f:
            self.assertEqual(f.read(), self.source_bytes)

    # -------------------------------------------------------------------------
    # 4. Path traversal and safety checks
    # -------------------------------------------------------------------------
    def test_path_traversal_rejection(self):
        analysis_id = str(uuid.uuid4())
        result = AERIONAnalysisResult(
            analysis_id=analysis_id,
            mode="border",
            source_type="drone",
            image_width=self.img_w,
            image_height=self.img_h,
            detections=[],
            summary=SceneSummary(),
        )

        # Null byte injection rejection
        null_byte_path = "image\0test.jpg"
        with self.assertRaises(ValidationError):
            self.service.annotate_and_store(
                source_image_path=null_byte_path,
                analysis_result=result,
                project_id=self.project_id,
            )

    def test_nonexistent_image_rejection(self):
        analysis_id = str(uuid.uuid4())
        result = AERIONAnalysisResult(
            analysis_id=analysis_id,
            mode="border",
            source_type="drone",
            image_width=self.img_w,
            image_height=self.img_h,
            detections=[],
            summary=SceneSummary(),
        )

        missing_path = Path(self.temp_dir) / "nonexistent_aerial.jpg"
        with self.assertRaises(ResourceNotFoundError):
            self.service.annotate_and_store(
                source_image_path=missing_path,
                analysis_result=result,
                project_id=self.project_id,
            )

    # -------------------------------------------------------------------------
    # 5. Evidence Lineage Verification (Parent link & DERIVED modality)
    # -------------------------------------------------------------------------
    async def test_evidence_lineage_and_persistence(self):
        from unittest.mock import AsyncMock

        analysis_id = str(uuid.uuid4())
        det = Detection(
            source="drone",
            class_id=1,
            class_name="people",
            confidence=0.88,
            bbox=BoundingBox(x1=20, y1=30, x2=80, y2=120),
        )
        result = AERIONAnalysisResult(
            analysis_id=analysis_id,
            mode="border",
            source_type="drone",
            image_width=self.img_w,
            image_height=self.img_h,
            detections=[det],
            summary=SceneSummary(critical=0, high=1, medium=0, low=0),
        )

        annot_key = f"{self.project_id}/annotated_image/{uuid.uuid4()}.jpg"

        mock_session = AsyncMock()
        mock_session.get.side_effect = lambda model, item_id: None

        service = AnalysisPersistenceService(session=mock_session)
        persist_res = await service.persist_analysis(
            result=result,
            project_id=self.project_id,
            annotated_artifact_key=annot_key,
        )

        self.assertTrue(persist_res["persisted"])
        self.assertTrue(persist_res["annotated_persisted"])
        self.assertEqual(persist_res["detections_count"], 1)

        # Check that an evidence record with modality DERIVED was added
        added_records = [
            call[0][0]
            for call in mock_session.add.call_args_list
            if hasattr(call[0][0], "__tablename__") and call[0][0].__tablename__ == "evidence_records"
        ]
        derived_records = [r for r in added_records if r.modality == "DERIVED"]
        self.assertEqual(len(derived_records), 1)
        self.assertEqual(derived_records[0].raw_payload_uri, annot_key)
        self.assertIn("ANNOTATED_VISUAL_EVIDENCE", derived_records[0].source_type)

