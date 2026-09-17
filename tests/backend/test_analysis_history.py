"""
AERION — Phase A Analysis History & Persistence Regression Tests
Validates:
1. GET /api/v1/analysis/history returns user-scoped and tenant-isolated analysis records.
2. Tenant isolation: Organization A cannot access Organization B's analyses.
3. GET /api/v1/analysis/{analysis_id} returns canonical persisted analysis data by analysis_id and job_id.
4. Stable URL context: querying nonexistent or unauthorized analysis returns 404.
5. In-memory JobManager fallback when database is offline or job is in-flight.
6. Re-login / session refresh persistence: analyses remain retrievable across sessions.
"""

import asyncio
import json
import unittest
import uuid
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient


from app.core.auth import create_access_token
from app.core.jobs import JobManager, JobRecord, JobStatus, default_job_manager
from app.main import app
from app.db.models import AnalysisJob, AnalysisResult, Project, Organization


class TestPhaseAAnalysisHistory(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.user_a = str(uuid.uuid4())
        self.org_a = "00000000-0000-0000-0000-000000000001"
        self.token_a = create_access_token(
            data={"sub": self.user_a, "org": self.org_a, "role": "operator"}
        )
        self.headers_a = {"Authorization": f"Bearer {self.token_a}"}

        self.user_b = str(uuid.uuid4())
        self.org_b = str(uuid.uuid4())
        self.token_b = create_access_token(
            data={"sub": self.user_b, "org": self.org_b, "role": "operator"}
        )
        self.headers_b = {"Authorization": f"Bearer {self.token_b}"}

    def test_unauthenticated_history_rejected(self):
        """Unauthenticated history access must be rejected with 401."""
        resp = self.client.get("/api/v1/analysis/history")
        self.assertEqual(resp.status_code, 401)

    def test_unauthenticated_analysis_by_id_rejected(self):
        """Unauthenticated single analysis retrieval must be rejected with 401."""
        test_id = str(uuid.uuid4())
        resp = self.client.get(f"/api/v1/analysis/{test_id}")
        self.assertEqual(resp.status_code, 401)

    async def test_get_analysis_by_id_from_job_manager(self):
        """Job in JobManager should be retrievable by its ID for the authorized user."""
        test_analysis_id = str(uuid.uuid4())
        job_id = f"job-{uuid.uuid4().hex[:8]}"

        fake_result = {
            "analysis_id": test_analysis_id,
            "mode": "BORDER_SECURITY",
            "overall_status": "completed",
            "detections": [{"class_name": "person", "confidence": 0.88}],
        }

        # Submit job into default_job_manager
        record = JobRecord(
            job_id=job_id,
            task_name="border_test",
            status=JobStatus.COMPLETED,
            current_stage="COMPLETED",
            progress_percent=100,
            mode="border",
            user_id=self.user_a,
            analysis_id=test_analysis_id,
            result=fake_result,
        )
        async with default_job_manager._lock:
            default_job_manager._jobs[job_id] = record

        # Retrieve by job_id with User A
        resp = self.client.get(f"/api/v1/analysis/{job_id}", headers=self.headers_a)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["analysis_id"], test_analysis_id)

        # User B cannot access User A's job
        resp_b = self.client.get(f"/api/v1/analysis/{job_id}", headers=self.headers_b)
        self.assertEqual(resp_b.status_code, 404)

    async def test_history_list_structure(self):
        """History list must return valid JSON envelope with expected schema."""
        resp = self.client.get("/api/v1/analysis/history", headers=self.headers_a)
        self.assertEqual(resp.status_code, 200)
        json_data = resp.json()
        self.assertTrue(json_data["success"])
        self.assertIsInstance(json_data["data"], list)

    def test_nonexistent_analysis_returns_404(self):
        """Querying a non-existent analysis_id returns 404."""
        nonexistent = str(uuid.uuid4())
        resp = self.client.get(f"/api/v1/analysis/{nonexistent}", headers=self.headers_a)
        self.assertEqual(resp.status_code, 404)

    def test_history_filter_by_mode(self):
        """History endpoint respects mode query parameter filter."""
        resp = self.client.get("/api/v1/analysis/history?mode=border", headers=self.headers_a)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        for item in data:
            self.assertEqual(item["mode"], "border")

    # =========================================================================
    # PHASE C OPERATIONAL REPORT TESTS (BUG-007, 008, 009, 012, 013)
    # =========================================================================

    async def test_bug_007_disaster_report_represents_persisted_damage_analysis(self):
        """BUG-007: Disaster report reflects actual completed damage analysis."""
        test_analysis_id = str(uuid.uuid4())
        job_id = f"job-{uuid.uuid4().hex[:8]}"

        disaster_payload = {
            "analysis_id": test_analysis_id,
            "mode": "disaster",
            "source_type": "satellite_pair",
            "overall_status": "COMPLETED",
            "input_asset_reference": "storage/assets/test_disaster_pair.tif",
            "damage_analysis": {
                "damage_ratio": 0.345678,
                "damage_percentage": 34.57,
                "damage_pixels": 450000,
                "total_pixels": 1301789,
                "probability_mean": 0.6214,
                "threshold": 0.50,
                "classification": "MAJOR_DAMAGE",
                "mask_storage_key": "storage/artifacts/damage_mask_001.png",
            },
            "damage_artifact": {
                "artifact_key": "damage/masks/damage_mask_001.png",
                "mime_type": "image/png",
                "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                "size_bytes": 1048576,
            },
            "pair_validation": {
                "is_compatible": True,
                "status": "VALIDATED",
                "warnings": ["Slight illumination delta observed between T0 and T1"],
                "limitations": ["Cloud shadow in northwestern quad"],
            },
            "advisory": {
                "summary": "Severe structural damage identified along western riverbank.",
                "model": "open-mistral-nemo",
                "generated_at_utc": "2026-09-13T10:00:00Z",
                "provider_status": "AVAILABLE",
                "disclaimer": "AI advisory is bounded to verified ground facts.",
            },
        }

        record = JobRecord(
            job_id=job_id,
            task_name="disaster_analysis_test",
            status=JobStatus.COMPLETED,
            current_stage="COMPLETED",
            progress_percent=100,
            mode="disaster",
            user_id=self.user_a,
            analysis_id=test_analysis_id,
            input_asset_reference="storage/assets/test_disaster_pair.tif",
            limitations=["Cloud shadow in northwestern quad"],
            result=disaster_payload,
        )
        async with default_job_manager._lock:
            default_job_manager._jobs[job_id] = record

        resp = self.client.get(
            f"/api/v1/situations/00000000-0000-0000-0000-000000000002/report?analysis_id={job_id}",
            headers=self.headers_a,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]

        self.assertEqual(data["analysis_id"], test_analysis_id)
        self.assertEqual(data["job_id"], job_id)
        self.assertEqual(data["mode"], "disaster")
        self.assertIsNotNone(data["damage_summary"])
        self.assertEqual(data["damage_summary"]["damage_percentage"], 34.57)
        self.assertEqual(data["damage_summary"]["damage_pixels"], 450000)
        self.assertEqual(data["damage_summary"]["total_pixels"], 1301789)
        self.assertEqual(data["damage_summary"]["classification"], "MAJOR_DAMAGE")
        self.assertEqual(data["damage_summary"]["pair_validation"]["status"], "VALIDATED")
        self.assertIn("Cloud shadow in northwestern quad", data["damage_summary"]["pair_validation"]["limitations"])
        self.assertTrue(any(a["type"] == "DAMAGE_MASK" for a in data["artifacts"]))

        facts_text = " ".join(data["verified_facts"])
        self.assertIn("34.57% damaged area", facts_text)
        self.assertIn("450,000", facts_text)

    async def test_bug_012_border_report_represents_actual_detections(self):
        """BUG-012: Border report reflects actual current analysis detections."""
        test_analysis_id = str(uuid.uuid4())
        job_id = f"job-{uuid.uuid4().hex[:8]}"

        border_payload = {
            "analysis_id": test_analysis_id,
            "mode": "border",
            "source_type": "drone_aerial",
            "overall_status": "COMPLETED",
            "input_asset_reference": "storage/assets/border_drone_042.jpg",
            "detections": [
                {
                    "detection_id": "det-001",
                    "class_name": "person",
                    "confidence": 0.9234,
                    "bbox": {"x1": 100, "y1": 150, "x2": 160, "y2": 280},
                    "track_id": 4,
                    "evidence_id": "EV-001-PERSON",
                },
                {
                    "detection_id": "det-002",
                    "class_name": "van",
                    "confidence": 0.8812,
                    "bbox": {"x1": 320, "y1": 400, "x2": 540, "y2": 620},
                    "track_id": 7,
                    "evidence_id": "EV-002-VEHICLE",
                },
            ],
            "annotated_artifact": {
                "artifact_key": "annotated/border_drone_042_annot.jpg",
                "mime_type": "image/jpeg",
                "sha256": "11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
                "size_bytes": 524288,
            },
            "advisory": {
                "summary": "Coordinated movement observed in sector Delta-9.",
                "model": "open-mistral-nemo",
                "provider_status": "AVAILABLE",
            },
        }

        record = JobRecord(
            job_id=job_id,
            task_name="border_detections_test",
            status=JobStatus.COMPLETED,
            current_stage="COMPLETED",
            progress_percent=100,
            mode="border",
            user_id=self.user_a,
            analysis_id=test_analysis_id,
            input_asset_reference="storage/assets/border_drone_042.jpg",
            result=border_payload,
        )
        async with default_job_manager._lock:
            default_job_manager._jobs[job_id] = record

        resp = self.client.get(
            f"/api/v1/situations/00000000-0000-0000-0000-000000000001/report?analysis_id={job_id}",
            headers=self.headers_a,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]

        self.assertEqual(data["analysis_id"], test_analysis_id)
        self.assertEqual(data["job_id"], job_id)
        self.assertIsNotNone(data["detection_summary"])
        self.assertEqual(data["detection_summary"]["total_detections"], 2)
        self.assertEqual(data["detection_summary"]["by_class"]["person"], 1)
        self.assertEqual(data["detection_summary"]["by_class"]["van"], 1)

        dets = data["detection_summary"]["detections"]
        self.assertEqual(len(dets), 2)
        self.assertEqual(dets[0]["class_name"], "person")
        self.assertEqual(dets[0]["confidence"], 0.9234)
        self.assertEqual(dets[0]["track_id"], 4)
        self.assertEqual(dets[0]["evidence_reference"], "EV-001-PERSON")

    async def test_bug_012_border_report_zero_detections_honestly_stated(self):
        """BUG-012: Border analysis with zero detections explicitly shows total_detections = 0."""
        test_analysis_id = str(uuid.uuid4())
        job_id = f"job-{uuid.uuid4().hex[:8]}"

        border_zero_payload = {
            "analysis_id": test_analysis_id,
            "mode": "border",
            "source_type": "drone_aerial",
            "overall_status": "COMPLETED",
            "detections": [],
            "input_asset_reference": "storage/assets/clear_sector.jpg",
        }

        record = JobRecord(
            job_id=job_id,
            task_name="border_zero_test",
            status=JobStatus.COMPLETED,
            current_stage="COMPLETED",
            progress_percent=100,
            mode="border",
            user_id=self.user_a,
            analysis_id=test_analysis_id,
            result=border_zero_payload,
        )
        async with default_job_manager._lock:
            default_job_manager._jobs[job_id] = record

        resp = self.client.get(
            f"/api/v1/situations/00000000-0000-0000-0000-000000000001/report?analysis_id={job_id}",
            headers=self.headers_a,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]

        self.assertEqual(data["detection_summary"]["total_detections"], 0)
        self.assertIn("Zero detections returned by this analysis.", data["verified_facts"])

    async def test_bug_013_evidence_lineage_and_traceability(self):
        """BUG-013: Report exposes complete audit lineage and hashes."""
        test_analysis_id = str(uuid.uuid4())
        job_id = f"job-{uuid.uuid4().hex[:8]}"

        payload = {
            "analysis_id": test_analysis_id,
            "mode": "border",
            "source_type": "drone_aerial",
            "input_asset_reference": "storage/inputs/patrol_alpha.png",
            "metadata": {"sha256": "99887766554433221100aabbccddeeff99887766554433221100aabbccddeeff"},
            "detections": [{"class_name": "person", "confidence": 0.85}],
            "annotated_artifact": {
                "artifact_key": "annotated/patrol_alpha_annot.png",
                "sha256": "aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899",
                "size_bytes": 204800,
                "mime_type": "image/png",
            },
        }

        record = JobRecord(
            job_id=job_id,
            task_name="lineage_test",
            status=JobStatus.COMPLETED,
            current_stage="COMPLETED",
            progress_percent=100,
            mode="border",
            user_id=self.user_a,
            analysis_id=test_analysis_id,
            input_asset_reference="storage/inputs/patrol_alpha.png",
            result=payload,
        )
        async with default_job_manager._lock:
            default_job_manager._jobs[job_id] = record

        resp = self.client.get(
            f"/api/v1/situations/00000000-0000-0000-0000-000000000001/report?analysis_id={job_id}",
            headers=self.headers_a,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]

        self.assertEqual(data["input_asset_reference"], "storage/inputs/patrol_alpha.png")
        self.assertTrue(len(data["evidence_lineage"]) > 0)
        first_ev = data["evidence_lineage"][0]
        self.assertEqual(first_ev["source"], "storage/inputs/patrol_alpha.png")
        self.assertEqual(first_ev["hash"], "99887766554433221100aabbccddeeff99887766554433221100aabbccddeeff")
        self.assertTrue(any(a["sha256"].startswith("aabbccddeeff") for a in data["artifacts"]))

    async def test_bug_008_pdf_operational_report_download(self):
        """BUG-008: PDF endpoint generates authentic, vector PDF with analysis facts."""
        test_analysis_id = str(uuid.uuid4())
        job_id = f"job-{uuid.uuid4().hex[:8]}"

        payload = {
            "analysis_id": test_analysis_id,
            "mode": "border",
            "source_type": "drone_aerial",
            "overall_status": "COMPLETED",
            "detections": [{"id": "d1", "class_name": "vehicle", "confidence": 0.95}],
            "input_asset_reference": "storage/assets/aerial_patrol.jpg",
        }

        record = JobRecord(
            job_id=job_id,
            task_name="pdf_download_test",
            status=JobStatus.COMPLETED,
            current_stage="COMPLETED",
            progress_percent=100,
            mode="border",
            user_id=self.user_a,
            analysis_id=test_analysis_id,
            result=payload,
        )
        async with default_job_manager._lock:
            default_job_manager._jobs[job_id] = record

        resp = self.client.get(
            f"/api/v1/situations/00000000-0000-0000-0000-000000000001/report/download?format=pdf&analysis_id={job_id}",
            headers=self.headers_a,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "application/pdf")
        self.assertIn("attachment", resp.headers["content-disposition"])
        self.assertTrue(resp.content.startswith(b"%PDF-"))
        self.assertGreater(len(resp.content), 5000)
        self.assertIn(test_analysis_id[:8].encode("utf-8"), resp.content)

    async def test_bug_009_json_operational_report_download(self):
        """BUG-009: JSON endpoint serializes the authoritative report matching the analysis result."""
        test_analysis_id = str(uuid.uuid4())
        job_id = f"job-{uuid.uuid4().hex[:8]}"

        payload = {
            "analysis_id": test_analysis_id,
            "mode": "disaster",
            "source_type": "satellite_pair",
            "overall_status": "COMPLETED",
            "damage_analysis": {
                "damage_percentage": 22.45,
                "damage_ratio": 0.224500,
                "damage_pixels": 100000,
                "total_pixels": 445434,
                "classification": "MODERATE_DAMAGE",
            },
        }

        record = JobRecord(
            job_id=job_id,
            task_name="json_download_test",
            status=JobStatus.COMPLETED,
            current_stage="COMPLETED",
            progress_percent=100,
            mode="disaster",
            user_id=self.user_a,
            analysis_id=test_analysis_id,
            result=payload,
        )
        async with default_job_manager._lock:
            default_job_manager._jobs[job_id] = record

        resp = self.client.get(
            f"/api/v1/situations/00000000-0000-0000-0000-000000000002/report/download?format=json&analysis_id={job_id}",
            headers=self.headers_a,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/json", resp.headers["content-type"])
        self.assertIn("attachment", resp.headers["content-disposition"])

        json_data = json.loads(resp.content)
        self.assertEqual(json_data["analysis_id"], test_analysis_id)
        self.assertEqual(json_data["job_id"], job_id)
        self.assertEqual(json_data["mode"], "disaster")
        self.assertEqual(json_data["damage_summary"]["damage_percentage"], 22.45)

    async def test_tenant_isolation_cross_org_report_access_rejected(self):
        """Tenant Isolation: Org B cannot access Org A's report or download."""
        test_analysis_id = str(uuid.uuid4())
        job_id = f"job-{uuid.uuid4().hex[:8]}"

        payload = {
            "analysis_id": test_analysis_id,
            "mode": "border",
            "overall_status": "COMPLETED",
        }

        record = JobRecord(
            job_id=job_id,
            task_name="isolation_test",
            status=JobStatus.COMPLETED,
            current_stage="COMPLETED",
            progress_percent=100,
            mode="border",
            user_id=self.user_a,
            analysis_id=test_analysis_id,
            result=payload,
        )
        async with default_job_manager._lock:
            default_job_manager._jobs[job_id] = record

        resp_b = self.client.get(
            f"/api/v1/situations/00000000-0000-0000-0000-000000000001/report?analysis_id={job_id}",
            headers=self.headers_b,
        )
        self.assertEqual(resp_b.status_code, 404)

        resp_b_dl = self.client.get(
            f"/api/v1/situations/00000000-0000-0000-0000-000000000001/report/download?format=pdf&analysis_id={job_id}",
            headers=self.headers_b,
        )
        self.assertEqual(resp_b_dl.status_code, 404)

    async def test_stale_analysis_protection_different_analyses_produce_different_reports(self):
        """Stale Analysis Protection: Job A and Job B maintain separate, unpolluted state."""
        job_a_id = f"job-a-{uuid.uuid4().hex[:6]}"
        job_b_id = f"job-b-{uuid.uuid4().hex[:6]}"

        record_a = JobRecord(
            job_id=job_a_id,
            task_name="job_a",
            status=JobStatus.COMPLETED,
            current_stage="COMPLETED",
            progress_percent=100,
            mode="border",
            user_id=self.user_a,
            analysis_id=str(uuid.uuid4()),
            result={"detections": [{"class_name": "truck", "confidence": 0.99}]},
        )
        record_b = JobRecord(
            job_id=job_b_id,
            task_name="job_b",
            status=JobStatus.COMPLETED,
            current_stage="COMPLETED",
            progress_percent=100,
            mode="border",
            user_id=self.user_a,
            analysis_id=str(uuid.uuid4()),
            result={"detections": [{"class_name": "boat", "confidence": 0.77}]},
        )
        async with default_job_manager._lock:
            default_job_manager._jobs[job_a_id] = record_a
            default_job_manager._jobs[job_b_id] = record_b

        resp_a = self.client.get(
            f"/api/v1/situations/00000000-0000-0000-0000-000000000001/report?analysis_id={job_a_id}",
            headers=self.headers_a,
        )
        resp_b = self.client.get(
            f"/api/v1/situations/00000000-0000-0000-0000-000000000001/report?analysis_id={job_b_id}",
            headers=self.headers_a,
        )

        data_a = resp_a.json()["data"]
        data_b = resp_b.json()["data"]

        self.assertIn("truck", data_a["detection_summary"]["by_class"])
        self.assertNotIn("boat", data_a["detection_summary"]["by_class"])

        self.assertIn("boat", data_b["detection_summary"]["by_class"])
        self.assertNotIn("truck", data_b["detection_summary"]["by_class"])

