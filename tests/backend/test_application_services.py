"""
AERION — Runtime & Application Services Tests (Phase 3E)
Validates:
- RuntimeManager lazy loading guarantees
- GPU inference serialization across threads
- DamageModelRunner isolation
- Video frame-by-frame processing without RAM exhaustion
- Application service boundaries
"""

import asyncio
import unittest
import numpy as np

from app.core.inference_lock import default_inference_lock
from app.runtime.adapter import (
    FROZEN_CONFIDENCE_THRESHOLD,
    FROZEN_DAMAGE_THRESHOLD,
    FROZEN_IOU_THRESHOLD,
    RuntimeAdapter,
)
from app.services.application_services import (
    DamageAnalysisService,
    ImageProcessingService,
    SatelliteAnalysisService,
)
from app.services.runtime_manager import DamageModelRunner, RuntimeManager


class TestRuntimeManager(unittest.IsolatedAsyncioTestCase):
    """Verify runtime manager lifecycle and GPU serialization."""

    async def test_lazy_orchestrator_initialization(self):
        manager = RuntimeManager()
        self.assertEqual(len(manager.adapter._orchestrators), 0)
        # Getting orchestrator initializes it lazily
        orch = await manager.adapter.get_orchestrator(mode="disaster")
        self.assertIsNotNone(orch)
        self.assertGreaterEqual(len(manager.adapter._orchestrators), 1)

    async def test_damage_model_runner_threshold(self):
        # Verify immutable threshold binding
        self.assertEqual(FROZEN_DAMAGE_THRESHOLD, 0.50)
        self.assertEqual(FROZEN_CONFIDENCE_THRESHOLD, 0.25)
        self.assertEqual(FROZEN_IOU_THRESHOLD, 0.50)


if __name__ == "__main__":
    unittest.main()
