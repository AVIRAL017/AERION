"""
AERION v1 — Runtime Contracts Unit Tests

Tests all dataclasses in aerion_runtime_contracts.py for:
    - Proper initialization and type conversions
    - Boundary and invariant validation
    - Serialization to pure native Python dictionaries
    - Strict JSON serialization without numpy / torch leaks
"""

import json
import sys
import unittest
from pathlib import Path
import numpy as np

# Ensure workspace root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from aerion_runtime_contracts import (
    Point2D,
    BoundingBox,
    Detection,
    DamageAnalysis,
    TrackState,
    BorderAnalysis,
    IntelligenceItem,
    SceneSummary,
    AERIONAnalysisResult,
)


class TestAERIONRuntimeContracts(unittest.TestCase):

    def test_point2d_valid(self):
        p = Point2D(x=np.float32(10.5), y=np.int32(20))
        self.assertIsInstance(p.x, float)
        self.assertIsInstance(p.y, float)
        self.assertEqual(p.x, 10.5)
        self.assertEqual(p.y, 20.0)
        d = p.to_dict()
        self.assertDictEqual(d, {"x": 10.5, "y": 20.0})

    def test_bounding_box_valid(self):
        bbox = BoundingBox(x1=10, y1=20, x2=100, y2=200)
        self.assertEqual(bbox.x1, 10.0)
        self.assertEqual(bbox.y2, 200.0)
        d = bbox.to_dict()
        self.assertEqual(d["x1"], 10.0)
        self.assertEqual(d["x2"], 100.0)

    def test_bounding_box_invalid(self):
        with self.assertRaises(ValueError):
            BoundingBox(x1=100, y1=20, x2=10, y2=200)  # x1 > x2
        with self.assertRaises(ValueError):
            BoundingBox(x1=10, y1=200, x2=100, y2=20)  # y1 > y2

    def test_detection_bbox_only(self):
        bbox = BoundingBox(x1=0, y1=0, x2=50, y2=50)
        det = Detection(
            source="drone",
            class_id=0,
            class_name="person",
            confidence=0.895,
            bbox=bbox,
        )
        self.assertEqual(det.source, "drone")
        self.assertEqual(det.class_name, "person")
        self.assertAlmostEqual(det.confidence, 0.895)
        self.assertIsNone(det.obb_points)

        d = det.to_dict()
        self.assertEqual(d["source"], "drone")
        self.assertEqual(d["confidence"], 0.895)
        self.assertIsNotNone(d["bbox"])
        self.assertIsNone(d["obb_points"])

    def test_detection_obb_only(self):
        points = [
            Point2D(0, 0),
            Point2D(10, 0),
            Point2D(10, 20),
            Point2D(0, 20),
        ]
        det = Detection(
            source="satellite",
            class_id=1,
            class_name="ship",
            confidence=0.95,
            obb_points=points,
        )
        self.assertIsNone(det.bbox)
        self.assertEqual(len(det.obb_points), 4)
        d = det.to_dict()
        self.assertEqual(len(d["obb_points"]), 4)
        self.assertIsNone(d["bbox"])

    def test_detection_validation_errors(self):
        bbox = BoundingBox(x1=0, y1=0, x2=10, y2=10)
        # Invalid confidence > 1.0
        with self.assertRaises(ValueError):
            Detection("drone", 0, "person", 1.5, bbox=bbox)
        # Invalid confidence < 0.0
        with self.assertRaises(ValueError):
            Detection("drone", 0, "person", -0.1, bbox=bbox)
        # Invalid class_id < 0
        with self.assertRaises(ValueError):
            Detection("drone", -1, "person", 0.5, bbox=bbox)
        # Missing both bbox and obb
        with self.assertRaises(ValueError):
            Detection("drone", 0, "person", 0.5, bbox=None, obb_points=None)

    def test_damage_analysis_valid(self):
        damage = DamageAnalysis(
            before_width=1024,
            before_height=1024,
            after_width=1024,
            after_height=1024,
            probability_min=0.01,
            probability_max=0.98,
            probability_mean=0.35,
            threshold=0.50,
            damage_pixels=1500,
            total_pixels=1024 * 1024,
            damage_ratio=1500 / (1024 * 1024),
            damage_percentage=(1500 / (1024 * 1024)) * 100,
        )
        d = damage.to_dict()
        self.assertEqual(d["damage_pixels"], 1500)
        self.assertEqual(d["threshold"], 0.50)
        self.assertTrue(d["probability_map_available"])
        self.assertTrue(d["damage_mask_available"])

    def test_damage_analysis_validation_errors(self):
        with self.assertRaises(ValueError):
            DamageAnalysis(
                before_width=512, before_height=512, after_width=512, after_height=512,
                probability_min=0, probability_max=1, probability_mean=0.5,
                threshold=0.5, damage_pixels=10, total_pixels=100,
                damage_ratio=1.5, damage_percentage=150.0  # Invalid ratio
            )

    def test_track_state_valid(self):
        bbox = BoundingBox(x1=10, y1=10, x2=30, y2=40)
        track = TrackState(
            track_id=1,
            confidence=0.88,
            bbox=bbox,
            center=Point2D(20, 25),
            previous_center=Point2D(18, 22),
            frames_seen=12,
            movement_distance=3.61,
            displacement=15.2,
            direction="north-east",
            persistence=0.85,
            class_id=0,
            class_name="person",
        )
        d = track.to_dict()
        self.assertEqual(d["track_id"], 1)
        self.assertEqual(d["direction"], "north-east")
        self.assertAlmostEqual(d["persistence"], 0.85)

    def test_border_analysis_valid(self):
        analysis = BorderAnalysis(
            track_id=1,
            inside_restricted_zone=True,
            distance_to_zone=0.0,
            zone_entry=True,
            zone_status="INSIDE",
            border_activity_score=0.85,
            border_priority="CRITICAL",
            border_alert=True,
            alert_level="CRITICAL",
        )
        d = analysis.to_dict()
        self.assertTrue(d["inside_restricted_zone"])
        self.assertTrue(d["zone_entry"])
        self.assertEqual(d["border_priority"], "CRITICAL")
        self.assertIsNone(d["approach_score"])  # Optional field preserved

    def test_intelligence_item_valid(self):
        item = IntelligenceItem(
            object_class="building_damage",
            confidence=0.92,
            class_weight=1.0,
            change_score=0.45,
            priority_score=0.725,
            priority="High",
            mode="disaster",
            protocol="Standard advisory: dispatch structural assessment team",
        )
        d = item.to_dict()
        self.assertEqual(d["object_class"], "building_damage")
        self.assertEqual(d["priority"], "High")

    def test_aerion_analysis_result_complete_serialization(self):
        bbox = BoundingBox(x1=10, y1=10, x2=50, y2=50)
        det = Detection("drone", 0, "person", 0.90, bbox=bbox)
        track = TrackState(
            track_id=1, confidence=0.90, bbox=bbox,
            center=Point2D(30, 30), previous_center=None,
            frames_seen=5, movement_distance=0, displacement=0,
            direction="stationary", persistence=0.5
        )
        border = BorderAnalysis(
            track_id=1, inside_restricted_zone=False, border_priority="LOW"
        )
        summary = SceneSummary(critical=0, high=1, medium=0, low=0)

        result = AERIONAnalysisResult(
            project="AERION",
            version="v1",
            mode="border",
            source_type="video",
            image_width=1280,
            image_height=720,
            frame_number=10,
            detections=[det],
            tracks=[track],
            border_analysis=[border],
            damage_analysis=None,
            intelligence=[],
            summary=summary,
            overall_status="detections_available",
            metadata={"source_fps": 30.0, "numpy_val": np.int64(42)},
        )

        d = result.to_dict()
        self.assertEqual(d["project"], "AERION")
        self.assertEqual(d["version"], "v1")
        self.assertEqual(d["mode"], "border")
        self.assertEqual(len(d["detections"]), 1)
        self.assertEqual(len(d["tracks"]), 1)
        self.assertEqual(d["metadata"]["numpy_val"], 42)
        self.assertIsInstance(d["metadata"]["numpy_val"], int)

        # Strict JSON string serialization test
        json_str = result.to_json()
        parsed = json.loads(json_str)
        self.assertEqual(parsed["analysis_id"], result.analysis_id)
        self.assertEqual(parsed["summary"]["high"], 1)


if __name__ == "__main__":
    unittest.main()
