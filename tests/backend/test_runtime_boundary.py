"""
AERION — Runtime Boundary & Adapter Unit Tests
Tests lazy loading, GPU mutex enforcement, non-blocking execution, and application service mediation.
"""

import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import AERIONSettings
from app.core.inference_lock import InferenceLock
from app.core.jobs import JobManager, JobStatus
from app.runtime.adapter import RuntimeAdapter
from app.services.runtime_service import RuntimeService


class TestRuntimeBoundary(unittest.IsolatedAsyncioTestCase):

    def test_adapter_lazy_loading_invariants(self):
        settings = AERIONSettings(ENVIRONMENT="test", LAZY_LOAD_MODELS=True)
        adapter = RuntimeAdapter(settings=settings)
        # Verify no orchestrators or models are loaded at instantiation
        self.assertEqual(len(adapter._orchestrators), 0)

    async def test_get_orchestrator_lazy_caching(self):
        adapter = RuntimeAdapter()
        mock_orch = MagicMock()

        with patch.object(adapter, "_create_orchestrator", return_value=mock_orch) as mock_create:
            # First retrieval calls _create_orchestrator
            orch1 = await adapter.get_orchestrator(mode="disaster", terrain_type="arid")
            self.assertEqual(mock_create.call_count, 1)
            self.assertIs(orch1, mock_orch)

            # Second retrieval with same params returns cached instance without re-creating
            orch2 = await adapter.get_orchestrator(mode="disaster", terrain_type="arid")
            self.assertEqual(mock_create.call_count, 1)
            self.assertIs(orch2, orch1)

    async def test_process_image_acquires_inference_lock(self):
        mock_lock = MagicMock(spec=InferenceLock)
        # Create an async context manager mock
        acquire_ctx = AsyncMock()
        mock_lock.acquire.return_value = acquire_ctx

        adapter = RuntimeAdapter(inference_lock=mock_lock)
        mock_orch = MagicMock()
        mock_result = MagicMock()
        mock_orch.process_image.return_value = mock_result

        with patch.object(adapter, "get_orchestrator", return_value=mock_orch):
            result = await adapter.process_image(
                image_input="mock_image_path.jpg",
                source_type="drone",
                mode="disaster",
            )
            # Must acquire inference lock
            mock_lock.acquire.assert_called_once()
            self.assertIs(result, mock_result)

    async def test_process_damage_acquires_inference_lock(self):
        mock_lock = MagicMock(spec=InferenceLock)
        acquire_ctx = AsyncMock()
        mock_lock.acquire.return_value = acquire_ctx

        adapter = RuntimeAdapter(inference_lock=mock_lock)
        mock_orch = MagicMock()
        mock_result = MagicMock()
        mock_orch.process_damage.return_value = mock_result

        with patch.object(adapter, "get_orchestrator", return_value=mock_orch):
            result = await adapter.process_damage(
                pre_image="pre.jpg",
                post_image="post.jpg",
            )
            mock_lock.acquire.assert_called_once()
            self.assertIs(result, mock_result)

    async def test_runtime_service_delegates_to_adapter(self):
        mock_adapter = MagicMock(spec=RuntimeAdapter)
        mock_adapter.process_image = AsyncMock(return_value={"status": "detected"})
        mock_adapter.process_damage = AsyncMock(return_value={"damage": "moderate"})

        service = RuntimeService(adapter=mock_adapter)

        res_img = await service.analyze_image("test.jpg", mode="disaster")
        self.assertEqual(res_img, {"status": "detected"})
        mock_adapter.process_image.assert_awaited_once()

        res_dmg = await service.analyze_damage("pre.jpg", "post.jpg")
        self.assertEqual(res_dmg, {"damage": "moderate"})
        mock_adapter.process_damage.assert_awaited_once()

    async def test_runtime_service_async_job_submission(self):
        mock_adapter = MagicMock(spec=RuntimeAdapter)
        mock_adapter.process_image = AsyncMock(return_value={"analysis_id": "123"})
        job_manager = JobManager()

        service = RuntimeService(adapter=mock_adapter, job_manager=job_manager)
        job_record = await service.submit_async_image_analysis(
            task_name="async_recon",
            image_input="recon.jpg",
        )
        self.assertIsNotNone(job_record.job_id)

        # Await completion
        await asyncio.sleep(0.05)
        status = await service.get_job_status(job_record.job_id)
        self.assertEqual(status.status, JobStatus.COMPLETED)
        self.assertEqual(status.result, {"analysis_id": "123"})

    def test_frozen_runtime_constants_values(self):
        from app.runtime.adapter import (
            FROZEN_CONFIDENCE_THRESHOLD,
            FROZEN_DAMAGE_THRESHOLD,
            FROZEN_IOU_THRESHOLD,
        )
        self.assertEqual(FROZEN_CONFIDENCE_THRESHOLD, 0.25)
        self.assertEqual(FROZEN_IOU_THRESHOLD, 0.50)
        self.assertEqual(FROZEN_DAMAGE_THRESHOLD, 0.50)
        self.assertEqual(RuntimeAdapter.FROZEN_CONFIDENCE, 0.25)
        self.assertEqual(RuntimeAdapter.FROZEN_IOU, 0.50)
        self.assertEqual(RuntimeAdapter.FROZEN_DAMAGE, 0.50)

    async def test_runtime_adapter_immune_to_environment_threshold_overrides(self):
        # Even if someone sets environment variables, the adapter uses frozen constants
        with patch.dict(os.environ, {
            "CONFIDENCE_THRESHOLD": "0.10",
            "IOU_THRESHOLD": "0.90",
            "DAMAGE_THRESHOLD": "0.20",
        }):
            adapter = RuntimeAdapter()
            mock_orch = MagicMock()
            mock_result = MagicMock()
            mock_orch.process_image.return_value = mock_result
            mock_orch.process_damage.return_value = mock_result

            with patch.object(adapter, "get_orchestrator", return_value=mock_orch):
                # Process image without explicit overrides should strictly use 0.25 and 0.50
                await adapter.process_image("test.jpg")
                mock_orch.process_image.assert_called_once()
                call_kwargs = mock_orch.process_image.call_args[1]
                self.assertEqual(call_kwargs["confidence"], 0.25)
                self.assertEqual(call_kwargs["iou"], 0.50)

                # Process damage without explicit overrides should strictly use 0.50
                await adapter.process_damage("pre.jpg", "post.jpg")
                mock_orch.process_damage.assert_called_once()
                call_damage_kwargs = mock_orch.process_damage.call_args[1]
                self.assertEqual(call_damage_kwargs["threshold"], 0.50)


if __name__ == "__main__":
    unittest.main()
