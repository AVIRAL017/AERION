"""
AERION v1 — Runtime Normalizers Unit Tests

Tests all normalization functions in aerion_runtime_normalizer.py:
    - normalize_drone_result
    - normalize_satellite_result
    - normalize_damage_result
    - normalize_border_result
    - normalize_intelligence_result
"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np

# Ensure workspace root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from aerion_runtime_normalizer import (
    normalize_drone_result,
    normalize_satellite_result,
    normalize_damage_result,
    normalize_border_result,
    normalize_intelligence_result,
)


class TestAERIONRuntimeNormalizers(unittest.TestCase):

    def test_normalize_drone_result(self):
        dummy_det = SimpleNamespace(
            class_id=0,
            class_name="person",
            confidence=0.885,
            bbox=[100.0, 150.0, 200.0, 300.0],
        )
        dummy_result = SimpleNamespace(
            model="visdrone_only",
            image_width=1280,
            image_height=720,
            detections=[dummy_det],
            detection_count=1,
        )

        detections = normalize_drone_result(dummy_result, frame_number=5)
        self.assertEqual(len(detections), 1)
        det = detections[0]
        self.assertEqual(det.source, "drone")
        self.assertEqual(det.class_id, 0)
        self.assertEqual(det.class_name, "person")
        self.assertEqual(det.confidence, 0.885)
        self.assertEqual(det.frame_number, 5)
        self.assertEqual(det.bbox.x1, 100.0)
        self.assertEqual(det.bbox.y2, 300.0)
        self.assertIsNone(det.obb_points)

    def test_normalize_satellite_result(self):
        obb = [
            [10.0, 10.0],
            [50.0, 20.0],
            [40.0, 60.0],
            [0.0, 50.0],
        ]
        dummy_det = SimpleNamespace(
            class_id=1,
            class_name="ship",
            confidence=0.942,
            obb_points=obb,
        )
        dummy_result = SimpleNamespace(
            model="dota_obb",
            image_width=1024,
            image_height=1024,
            detections=[dummy_det],
            detection_count=1,
        )

        detections = normalize_satellite_result(dummy_result)
        self.assertEqual(len(detections), 1)
        det = detections[0]
        self.assertEqual(det.source, "satellite")
        self.assertEqual(det.class_id, 1)
        self.assertEqual(det.class_name, "ship")
        self.assertEqual(len(det.obb_points), 4)

        # Verify derived axis-aligned bbox: min/max of the 4 points
        # xs: 10, 50, 40, 0 -> min=0, max=50
        # ys: 10, 20, 60, 50 -> min=10, max=60
        self.assertEqual(det.bbox.x1, 0.0)
        self.assertEqual(det.bbox.y1, 10.0)
        self.assertEqual(det.bbox.x2, 50.0)
        self.assertEqual(det.bbox.y2, 60.0)

    def test_normalize_damage_result(self):
        before = np.zeros((100, 100, 3), dtype=np.uint8)
        after = np.zeros((100, 100, 3), dtype=np.uint8)

        # 50x50 patch of 0.8 probability, rest 0.1
        prob_map = np.full((100, 100), 0.1, dtype=np.float32)
        prob_map[25:75, 25:75] = 0.8

        # 50x50 mask (2500 pixels damaged)
        mask = (prob_map >= 0.50).astype(np.uint8)

        raw_output = (before, after, prob_map, mask)
        analysis = normalize_damage_result(raw_output, threshold=0.50)

        self.assertEqual(analysis.before_width, 100)
        self.assertEqual(analysis.before_height, 100)
        self.assertEqual(analysis.after_width, 100)
        self.assertEqual(analysis.after_height, 100)
        self.assertEqual(analysis.damage_pixels, 2500)
        self.assertEqual(analysis.total_pixels, 10000)
        self.assertAlmostEqual(analysis.damage_ratio, 0.25)
        self.assertAlmostEqual(analysis.damage_percentage, 25.0)
        self.assertAlmostEqual(analysis.threshold, 0.50)
        self.assertAlmostEqual(analysis.probability_min, 0.1, places=3)
        self.assertAlmostEqual(analysis.probability_max, 0.8, places=3)

    def test_normalize_border_result(self):
        raw_items = [
            {
                "track_id": 1,
                "class_id": 0,
                "class_name": "person",
                "confidence": 0.89,
                "bbox": [100.0, 100.0, 150.0, 200.0],
                "center": (125.0, 150.0),
                "previous_center": [120.0, 145.0],
                "frames_seen": 15,
                "movement_distance": 7.07,
                "displacement": 35.0,
                "direction": "south-east",
                "persistence": 1.0,
                "inside_restricted_zone": True,
                "distance_to_zone": 0.0,
                "zone_entry": True,
                "zone_status": "INSIDE",
                "zone_dwell_frames": 1,
                "zone_dwell_score": 0.2,
                "border_activity_score": 0.85,
                "border_priority": "CRITICAL",
                "border_candidate": True,
                "border_alert": True,
                "alert_level": "CRITICAL",
            }
        ]

        detections, tracks, analyses = normalize_border_result(raw_items, frame_number=42)

        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0].track_id, 1)
        self.assertEqual(detections[0].frame_number, 42)
        self.assertEqual(detections[0].class_name, "person")

        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0].track_id, 1)
        self.assertEqual(tracks[0].direction, "south-east")
        self.assertEqual(tracks[0].previous_center.x, 120.0)

        self.assertEqual(len(analyses), 1)
        self.assertTrue(analyses[0].inside_restricted_zone)
        self.assertTrue(analyses[0].border_alert)
        self.assertEqual(analyses[0].alert_level, "CRITICAL")

    def test_normalize_intelligence_result(self):
        raw_engine_output = {
            "mode": "disaster",
            "total_detections": 2,
            "summary": {
                "critical": 1,
                "high": 1,
                "medium": 0,
                "low": 0,
            },
            "detections": [
                {
                    "object_class": "building_damage",
                    "confidence": 0.95,
                    "class_weight": 1.0,
                    "change_score": 0.8,
                    "priority_score": 0.875,
                    "priority": "Critical",
                    "mode": "disaster",
                    "detection": {"class": "building_damage"},
                },
                {
                    "object_class": "person",
                    "confidence": 0.90,
                    "class_weight": 0.8,
                    "change_score": 0.2,
                    "priority_score": 0.55,
                    "priority": "High",
                    "mode": "disaster",
                    "detection": {"class": "person"},
                },
            ],
        }

        items, summary = normalize_intelligence_result(raw_engine_output)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].object_class, "building_damage")
        self.assertEqual(items[0].priority, "Critical")
        self.assertEqual(summary.critical, 1)
        self.assertEqual(summary.high, 1)
        self.assertEqual(summary.medium, 0)


if __name__ == "__main__":
    unittest.main()
