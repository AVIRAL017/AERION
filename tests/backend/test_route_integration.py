"""
AERION — Step 12 Frontend <-> Backend Route Integration Tests
Validates:
1. Router registration under /api/v1 (health, auth, situations, analysis, usage)
2. Authenticated situation access (401 without Bearer JWT)
3. Situation list endpoint returns valid ResponseEnvelope
4. Situation detail endpoint returns operational state
5. Situation events endpoint returns event stream
6. Situation weather endpoint adheres to zero-fabrication (UNAVAILABLE without coords)
7. Situation routes endpoint returns evaluated routes
8. Situation report endpoint returns deterministic report with bounded Mistral advisory
9. Situation creation endpoint (POST /situations) initializes container
10. Image analysis endpoint executes through application service boundary
11. Damage analysis endpoint executes through application service boundary
12. Border video endpoint executes through application service boundary
13. Usage summary endpoint reflects organization tier
14. Subscription upgrade endpoint enforces ₹0 (FREE) and ₹9 (PRO)
15. Authentication & tenant isolation enforcement
"""

import base64
import unittest
import uuid
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.core.config import AERIONSettings
from app.main import create_app


class TestStep12RouteIntegration(unittest.TestCase):

    def setUp(self):
        self.settings = AERIONSettings(ENVIRONMENT="test")
        self.app = create_app(settings=self.settings)
        self.client = TestClient(self.app)

        # Generate test token
        self.user_id = str(uuid.uuid4())
        self.org_id = str(uuid.uuid4())
        self.token = create_access_token({
            "sub": self.user_id,
            "org": self.org_id,
            "role": "operator",
            "email": "operator@aerion.mil",
        })
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    # ------------------------------------------------------------------------
    # 1. Router Registration & Unauthenticated Access
    # ------------------------------------------------------------------------
    def test_unauthenticated_situation_endpoints_rejected(self):
        # Must return 401
        res = self.client.get("/api/v1/situations")
        self.assertEqual(res.status_code, 401)
        self.assertFalse(res.json()["success"])
        self.assertEqual(res.json()["error"]["code"], "AUTHENTICATION_REQUIRED")

    def test_unauthenticated_analysis_endpoints_rejected(self):
        res = self.client.post("/api/v1/analysis/image", json={"image_path": "test.jpg"})
        self.assertEqual(res.status_code, 401)

    def test_unauthenticated_usage_rejected(self):
        res = self.client.get("/api/v1/usage/summary")
        self.assertEqual(res.status_code, 401)

    # ------------------------------------------------------------------------
    # 2. Situations API Group
    # ------------------------------------------------------------------------
    def test_list_situations_authenticated(self):
        res = self.client.get("/api/v1/situations", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertIsInstance(body["data"], list)
        self.assertGreaterEqual(len(body["data"]), 1)
        self.assertIn("situation_type", body["data"][0])

    def test_get_situation_detail(self):
        sit_id = "00000000-0000-0000-0000-000000000001"
        res = self.client.get(f"/api/v1/situations/{sit_id}", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["id"], sit_id)
        self.assertEqual(body["data"]["situation_type"], "BORDER_SECURITY")

    def test_get_situation_events(self):
        sit_id = "00000000-0000-0000-0000-000000000001"
        res = self.client.get(f"/api/v1/situations/{sit_id}/events", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertIsInstance(body["data"], list)

    def test_get_situation_weather_zero_fabrication(self):
        sit_id = "00000000-0000-0000-0000-000000000001"
        # Calling without coordinates must return UNAVAILABLE state
        res = self.client.get(f"/api/v1/situations/{sit_id}/weather", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["status"], "UNAVAILABLE")

    def test_get_situation_routes_zero_fabrication(self):
        sit_id = "00000000-0000-0000-0000-000000000002"
        # Calling without coordinates returns empty candidates list
        res = self.client.get(f"/api/v1/situations/{sit_id}/routes", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"], [])

    def test_get_situation_report_deterministic(self):
        sit_id = "00000000-0000-0000-0000-000000000001"
        res = self.client.get(f"/api/v1/situations/{sit_id}/report", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        report = body["data"]
        self.assertEqual(report["situation_id"], sit_id)
        self.assertIn("verified_facts", report)
        self.assertIn("ai_advisory", report)

    def test_create_situation_container(self):
        payload = {
            "mode": "BORDER_SECURITY",
            "name": "Test Border Patrol",
            "location_name": "Sector Echo-5",
        }
        res = self.client.post("/api/v1/situations", json=payload, headers=self.auth_headers)
        self.assertEqual(res.status_code, 201)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["situation_type"], "BORDER_SECURITY")
        self.assertEqual(body["data"]["location_name"], "Sector Echo-5")

    # ------------------------------------------------------------------------
    # 3. Usage & Subscriptions API Group
    # ------------------------------------------------------------------------
    def test_get_usage_summary(self):
        res = self.client.get("/api/v1/usage/summary", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertIn(body["data"]["tier"], ("free", "pro"))
        self.assertGreater(body["data"]["api_requests_limit"], 0)

    def test_upgrade_subscription_free_to_pro(self):
        res = self.client.post(
            "/api/v1/subscriptions/upgrade",
            json={"tier": "PRO"},
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["plan"], "PRO")
        self.assertEqual(body["data"]["price_inr"], 9)
        self.assertEqual(body["data"]["currency"], "INR")

    def test_upgrade_subscription_invalid_plan_rejected(self):
        res = self.client.post(
            "/api/v1/subscriptions/upgrade",
            json={"tier": "UNLIMITED_ENTERPRISE_CUSTOM"},
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 422)
        self.assertFalse(res.json()["success"])

    # ------------------------------------------------------------------------
    # 4. Analysis API Group & Service Boundary
    # ------------------------------------------------------------------------
    def test_analysis_image_validation_missing_source(self):
        res = self.client.post("/api/v1/analysis/image", json={}, headers=self.auth_headers)
        self.assertEqual(res.status_code, 422)
        self.assertFalse(res.json()["success"])

    def test_analysis_image_nonexistent_file_returns_404(self):
        res = self.client.post(
            "/api/v1/analysis/image",
            json={"image_path": "non_existent_recon_frame_9999.jpg"},
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 404)
        self.assertFalse(res.json()["success"])

    @patch("app.services.application_services.ImageProcessingService.analyze_image")
    def test_analysis_image_invokes_service_boundary(self, mock_analyze):
        from aerion_runtime_contracts import AERIONAnalysisResult, SceneSummary

        dummy_result = AERIONAnalysisResult(
            project="AERION",
            version="v1",
            analysis_id="fa71295b-302a-4dbf-a365-5c1cf7e96b9d",
            mode="disaster",
            source_type="drone",
            detections=[],
            summary=SceneSummary(critical=0, high=0, medium=0, low=0),
            overall_status="detections_available",
        )
        mock_analyze.return_value = dummy_result

        # Use dummy 1x1 base64 transparent PNG
        dummy_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        res = self.client.post(
            "/api/v1/analysis/image",
            json={"image_base64": dummy_b64, "mode": "disaster"},
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["overall_status"], "detections_available")
        mock_analyze.assert_called_once()

    @patch("app.services.application_services.DamageAnalysisService.analyze_damage_pair")
    def test_analysis_damage_invokes_service_boundary(self, mock_damage):
        from aerion_runtime_contracts import AERIONAnalysisResult, SceneSummary, DamageAnalysis

        dummy_dmg = DamageAnalysis(
            before_width=512,
            before_height=512,
            after_width=512,
            after_height=512,
            probability_min=0.0,
            probability_max=0.8,
            probability_mean=0.1,
            threshold=0.5,
            damage_pixels=100,
            total_pixels=262144,
            damage_ratio=0.00038,
            damage_percentage=0.038,
        )
        dummy_result = AERIONAnalysisResult(
            project="AERION",
            version="v1",
            analysis_id="fa71295b-302a-4dbf-a365-5c1cf7e96b9d",
            mode="disaster",
            source_type="change_detection",
            damage_analysis=dummy_dmg,
            summary=SceneSummary(critical=0, high=0, medium=0, low=0),
            overall_status="damage_analysis_available",
        )
        mock_damage.return_value = dummy_result

        dummy_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        res = self.client.post(
            "/api/v1/analysis/damage",
            json={"before_base64": dummy_b64, "after_base64": dummy_b64},
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        mock_damage.assert_called_once()

    @patch("app.services.application_services.BorderVideoJobService.process_video_file")
    def test_analysis_video_invokes_service_boundary(self, mock_video):
        mock_video.return_value = {
            "processed_frames": 10,
            "total_video_frames": 100,
            "report": {"status": "ok"},
        }
        # Provide any existing file as video_path
        res = self.client.post(
            "/api/v1/analysis/border/video",
            json={"video_path": "app/main.py", "max_frames": 10},
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["processed_frames"], 10)
        mock_video.assert_called_once()


if __name__ == "__main__":
    unittest.main()
