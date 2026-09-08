"""
AERION v1 — Real Runtime Integration Tests

Tests end-to-end execution of frozen ML models through AERIONOrchestrator
using the real validated datasets and assets:
    1. Real Drone Validation Image (VisDrone)
    2. Real Satellite Validation Tile (DOTA-v1.5)
    3. Real xBD Disaster Change Pair (Guatemala Volcano)
    4. Real Border Surveillance Video (Urban border test video)

Ensures:
    - Real models load and execute without weight modifications.
    - Detections, tracks, and metrics normalize accurately.
    - JSON serialization succeeds with zero numpy / torch leaks.
"""

import json
import sys
import unittest
from pathlib import Path
import cv2

# Ensure workspace root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from aerion_orchestrator import AERIONOrchestrator


DRONE_IMAGE = Path(
    r"C:\Users\avira\yolo_project\datasets\VisDrone\images\val\0000001_02999_d_0000005.jpg"
)

SATELLITE_IMAGE = Path(
    r"C:\Users\avira\yolo_project\datasets\DOTAv1.5-split\images\val\P0003__1024__0___0.jpg"
)

DAMAGE_BEFORE = Path(
    r"D:\mp-1\xBD_damage_processed_v2\val\before\guatemala-volcano_00000000_0000.png"
)

DAMAGE_AFTER = Path(
    r"D:\mp-1\xBD_damage_processed_v2\val\after\guatemala-volcano_00000000_0000.png"
)

BORDER_VIDEO = Path(
    r"D:\mp-1\border_test_videos\border_test_urban.mp4.mp4"
)


class TestAERIONRealIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Use GPU (device 0) as validated in Phase 0
        cls.orchestrator = AERIONOrchestrator(
            mode="disaster",
            device=0,
            drone_model="visdrone_only",
            confidence=0.25,
            iou=0.50,
            terrain_type="arid",
        )

    def test_real_drone_perception(self):
        self.assertTrue(DRONE_IMAGE.exists(), f"Missing drone asset: {DRONE_IMAGE}")

        result = self.orchestrator.process_image(
            DRONE_IMAGE,
            source_type="drone",
            run_intelligence=True,
        )

        self.assertEqual(result.project, "AERION")
        self.assertEqual(result.version, "v1")
        self.assertEqual(result.source_type, "drone")
        self.assertGreater(result.image_width, 0)
        self.assertGreater(result.image_height, 0)
        self.assertGreater(len(result.detections), 0)

        # Inspect first detection contract
        det = result.detections[0]
        self.assertEqual(det.source, "drone")
        self.assertGreaterEqual(det.confidence, 0.25)
        self.assertIsNotNone(det.bbox)
        self.assertIsNone(det.obb_points)

        # Strict JSON serialization check
        json_output = result.to_json()
        parsed = json.loads(json_output)
        self.assertEqual(len(parsed["detections"]), len(result.detections))
        print(f"\n[OK] Real Drone Test Passed: {len(result.detections)} detections found.")

    def test_real_satellite_obb_perception(self):
        self.assertTrue(SATELLITE_IMAGE.exists(), f"Missing satellite asset: {SATELLITE_IMAGE}")

        result = self.orchestrator.process_image(
            SATELLITE_IMAGE,
            source_type="satellite",
            run_intelligence=True,
        )

        self.assertEqual(result.source_type, "satellite")
        self.assertGreater(result.image_width, 0)
        self.assertGreater(result.image_height, 0)

        if len(result.detections) > 0:
            det = result.detections[0]
            self.assertEqual(det.source, "satellite")
            self.assertIsNotNone(det.obb_points)
            self.assertEqual(len(det.obb_points), 4)
            self.assertIsNotNone(det.bbox)

        # Strict JSON serialization check
        json_output = result.to_json()
        parsed = json.loads(json_output)
        self.assertIn("detections", parsed)
        print(f"\n[OK] Real Satellite OBB Test Passed: {len(result.detections)} OBB detections found.")

    def test_real_damage_assessment(self):
        self.assertTrue(DAMAGE_BEFORE.exists(), f"Missing before asset: {DAMAGE_BEFORE}")
        self.assertTrue(DAMAGE_AFTER.exists(), f"Missing after asset: {DAMAGE_AFTER}")

        result = self.orchestrator.process_change_pair(
            DAMAGE_BEFORE,
            DAMAGE_AFTER,
            threshold=0.50,
            run_intelligence=True,
        )

        self.assertEqual(result.mode, "disaster")
        self.assertEqual(result.source_type, "change_detection")
        self.assertIsNotNone(result.damage_analysis)

        dmg = result.damage_analysis
        self.assertEqual(dmg.threshold, 0.50)
        self.assertGreater(dmg.total_pixels, 0)
        self.assertGreaterEqual(dmg.damage_ratio, 0.0)
        self.assertLessEqual(dmg.damage_ratio, 1.0)
        self.assertGreaterEqual(dmg.damage_percentage, 0.0)
        self.assertLessEqual(dmg.damage_percentage, 100.0)

        # Strict JSON serialization check
        json_output = result.to_json()
        parsed = json.loads(json_output)
        self.assertIsNotNone(parsed["damage_analysis"])
        self.assertEqual(parsed["damage_analysis"]["threshold"], 0.50)
        print(
            f"\n[OK] Real Damage Test Passed: {dmg.damage_pixels}/{dmg.total_pixels} pixels damaged ({dmg.damage_percentage:.2f}%)."
        )

    def test_real_border_tracking_frame(self):
        self.assertTrue(BORDER_VIDEO.exists(), f"Missing border video: {BORDER_VIDEO}")

        cap = cv2.VideoCapture(str(BORDER_VIDEO))
        self.assertTrue(cap.isOpened(), "Failed to open border test video")

        # Read 15 frames to allow tracker to initialize trajectory
        orch_border = AERIONOrchestrator(
            mode="border",
            device=0,
            drone_model="visdrone_only",
            confidence=0.35,
        )

        last_result = None
        for frame_idx in range(1, 16):
            ret, frame = cap.read()
            if not ret:
                break
            last_result = orch_border.process_border_frame(frame, frame_number=frame_idx)

        cap.release()

        self.assertIsNotNone(last_result)
        self.assertEqual(last_result.mode, "border")
        self.assertEqual(last_result.source_type, "video")
        self.assertEqual(last_result.frame_number, 15)

        # Strict JSON serialization check
        json_output = last_result.to_json()
        parsed = json.loads(json_output)
        self.assertEqual(parsed["frame_number"], 15)
        print(
            f"\n[OK] Real Border Video Test Passed: Frame 15 processed, {len(last_result.tracks)} tracks active, status='{last_result.overall_status}'."
        )


if __name__ == "__main__":
    unittest.main()
