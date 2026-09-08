"""
AERION v1 — Orchestrator Unit Tests

Tests the AERIONOrchestrator coordinator class for:
    - Mode validation ("disaster", "border", invalid rejection)
    - Lazy loading and lifecycle management
    - Terrain context metadata injection
    - Intelligence engine coordination
    - Advisory protocol querying
    - Output contract formatting and serialization
"""

import sys
import unittest
from pathlib import Path
import numpy as np

# Ensure workspace root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from aerion_orchestrator import AERIONOrchestrator


class TestAERIONOrchestrator(unittest.TestCase):

    def test_init_modes(self):
        # Valid disaster mode
        orch_disaster = AERIONOrchestrator(mode="disaster")
        self.assertEqual(orch_disaster.mode, "disaster")

        # Valid border mode
        orch_border = AERIONOrchestrator(mode="border")
        self.assertEqual(orch_border.mode, "border")

        # Invalid mode rejected explicitly
        with self.assertRaises(ValueError):
            AERIONOrchestrator(mode="urban_surveillance")

    def test_terrain_context_configured_metadata(self):
        orch = AERIONOrchestrator(terrain_type="coastal")
        self.assertEqual(orch.terrain_type, "coastal")
        self.assertIn("environment", orch._terrain_metadata)
        self.assertEqual(orch._terrain_metadata["environment"], "coastal/maritime")

    def test_lazy_loading_detectors_not_instantiated_at_init(self):
        orch = AERIONOrchestrator(mode="border")
        # Ensure heavy models are NOT loaded into VRAM on simple construction
        self.assertIsNone(orch._drone_detector)
        self.assertIsNone(orch._satellite_detector)
        self.assertIsNone(orch._border_pipeline)

    def test_analyze_detections_deterministic(self):
        orch = AERIONOrchestrator(mode="disaster")
        detections = [
            {
                "class": "building_damage",
                "confidence": 0.85,
                "background_ssim": 0.4210,
                "local_ssim": 0.2705,
            },
            {
                "class": "person",
                "confidence": 0.90,
                "background_ssim": 0.4210,
                "local_ssim": 0.3800,
            }
        ]

        items, summary = orch.analyze_detections(detections, mode="disaster")
        self.assertEqual(len(items), 2)
        # building_damage should have highest priority
        self.assertEqual(items[0].object_class, "building_damage")
        self.assertGreaterEqual(items[0].priority_score, items[1].priority_score)
        self.assertIn(items[0].priority, {"Critical", "High"})

    def test_advisory_protocol_query(self):
        orch = AERIONOrchestrator(mode="disaster")
        query = {
            "mode": "disaster",
            "object_class": "person",
            "confidence": 0.95,
        }
        advisory = orch.generate_advisory_report(query)
        self.assertIn("protocol", advisory)
        self.assertIn("search-and-rescue", advisory["protocol"])


if __name__ == "__main__":
    unittest.main()
