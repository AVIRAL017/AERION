"""
Unit tests for BUG-005: Confidence Threshold Propagation & Filtering
Verifies:
1. Orchestrator respects explicit confidence parameter and filters detections
2. Metadata records applied_confidence_threshold and requested_confidence_threshold
3. Low confidence retains more detections; high confidence filters them out
4. Zero detections result in overall_status = 'no_detections'
5. ImageProcessingService and API request schemas pass confidence_threshold
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np

from aerion_orchestrator import AERIONOrchestrator
from aerion_runtime_contracts import Detection, BoundingBox
from app.services.application_services import ImageProcessingService
from app.services.runtime_manager import RuntimeManager


class TestConfidenceThresholdPropagation(unittest.TestCase):

    def setUp(self):
        self.orch = AERIONOrchestrator(mode="disaster")

    def test_orchestrator_filters_detections_by_confidence(self):
        # Create mock raw detections with varying confidences
        mock_raw = MagicMock()
        mock_raw.image_width = 1000
        mock_raw.image_height = 800

        d1 = MagicMock()
        d1.class_id = 1
        d1.class_name = "person"
        d1.confidence = 0.30
        d1.bbox = [10.0, 10.0, 50.0, 50.0]

        d2 = MagicMock()
        d2.class_id = 2
        d2.class_name = "car"
        d2.confidence = 0.65
        d2.bbox = [100.0, 100.0, 200.0, 200.0]

        d3 = MagicMock()
        d3.class_id = 3
        d3.class_name = "truck"
        d3.confidence = 0.85
        d3.bbox = [300.0, 300.0, 500.0, 500.0]

        mock_raw.detections = [d1, d2, d3]
        mock_raw.detection_count = 3

        with patch.object(self.orch, "detect_drone", return_value=mock_raw):
            dummy_img = np.zeros((800, 1000, 3), dtype=np.uint8)

            # Test 1: Confidence = 0.25 (all 3 survive)
            res_low = self.orch.process_image(image=dummy_img, confidence=0.25)
            self.assertEqual(len(res_low.detections), 3)
            self.assertEqual(res_low.overall_status, "detections_available")
            self.assertEqual(res_low.metadata["applied_confidence_threshold"], 0.25)
            self.assertEqual(res_low.metadata["requested_confidence_threshold"], 0.25)

            # Test 2: Confidence = 0.50 (only d2 and d3 survive)
            res_med = self.orch.process_image(image=dummy_img, confidence=0.50)
            self.assertEqual(len(res_med.detections), 2)
            classes_med = [d.class_name for d in res_med.detections]
            self.assertIn("car", classes_med)
            self.assertIn("truck", classes_med)
            self.assertNotIn("person", classes_med)
            self.assertEqual(res_med.metadata["applied_confidence_threshold"], 0.50)

            # Test 3: Confidence = 0.80 (only d3 survives)
            res_high = self.orch.process_image(image=dummy_img, confidence=0.80)
            self.assertEqual(len(res_high.detections), 1)
            self.assertEqual(res_high.detections[0].class_name, "truck")
            self.assertEqual(res_high.metadata["applied_confidence_threshold"], 0.80)

            # Test 4: Confidence = 0.95 (none survive)
            res_none = self.orch.process_image(image=dummy_img, confidence=0.95)
            self.assertEqual(len(res_none.detections), 0)
            self.assertEqual(res_none.overall_status, "no_detections")
            self.assertEqual(res_none.metadata["applied_confidence_threshold"], 0.95)

    def test_invalid_confidence_threshold_raises_value_error(self):
        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
        with self.assertRaises(ValueError):
            self.orch.process_image(image=dummy_img, confidence=-0.1)

        with self.assertRaises(ValueError):
            self.orch.process_image(image=dummy_img, confidence=1.5)


class TestApplicationServiceConfidencePropagation(unittest.IsolatedAsyncioTestCase):

    async def test_image_processing_service_passes_confidence(self):
        mock_rm = MagicMock(spec=RuntimeManager)
        mock_rm.run_image_inference = AsyncMock(return_value=MagicMock())

        service = ImageProcessingService(runtime_manager=mock_rm)
        await service.analyze_image(
            image_path="dummy.jpg",
            mode="border",
            drone_model="visdrone_only",
            confidence_threshold=0.75,
            iou_threshold=0.45,
        )

        mock_rm.run_image_inference.assert_awaited_once_with(
            image_path_or_array="dummy.jpg",
            source_type="drone",
            mode="border",
            drone_model="visdrone_only",
            terrain_context="arid",
            run_intelligence=True,
            confidence=0.75,
            iou=0.45,
        )


if __name__ == "__main__":
    unittest.main()
