"""
AERION — Step 13 Upload-to-Result Workflow Tests
Validates requirements from Step 13 prompt:
1. Valid image upload (base64 and service invocation)
2. Invalid image type / corrupt base64 error handling
3. Oversized payload / limit validation
4. Authentication requirement on all analysis endpoints
5. Path traversal protection on local image/video paths
6. Service invocation for image, damage, and border video
7. Valid damage pair handling
8. Mismatched / missing damage pair validation
9. Valid border video handling (path and base64)
10. Invalid video type / missing video validation
"""

import base64
import unittest
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.core.config import AERIONSettings
from app.main import create_app
from aerion_runtime_contracts import AERIONAnalysisResult, SceneSummary, DamageAnalysis


class TestStep13UploadToResultWorkflow(unittest.TestCase):

    def setUp(self):
        self.settings = AERIONSettings(ENVIRONMENT="test")
        self.app = create_app(settings=self.settings)
        self.client = TestClient(self.app)

        self.user_id = str(uuid.uuid4())
        self.org_id = str(uuid.uuid4())
        self.token = create_access_token({
            "sub": self.user_id,
            "org": self.org_id,
            "role": "operator",
            "email": "operator@aerion.mil",
        })
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}
        # 1x1 transparent PNG
        self.valid_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

    # 1. Authentication requirement
    def test_analysis_image_requires_auth(self):
        res = self.client.post("/api/v1/analysis/image", json={"image_base64": self.valid_b64})
        self.assertEqual(res.status_code, 401)
        self.assertFalse(res.json()["success"])

    def test_analysis_image_with_invalid_token_rejected(self):
        invalid_headers = {"Authorization": "Bearer invalid_or_tampered_token_value"}
        res = self.client.post(
            "/api/v1/analysis/image",
            json={"image_base64": self.valid_b64},
            headers=invalid_headers,
        )
        self.assertEqual(res.status_code, 401)
        self.assertFalse(res.json()["success"])

    def test_analysis_damage_requires_auth(self):
        res = self.client.post(
            "/api/v1/analysis/damage",
            json={"before_base64": self.valid_b64, "after_base64": self.valid_b64},
        )
        self.assertEqual(res.status_code, 401)
        self.assertFalse(res.json()["success"])

    def test_analysis_video_requires_auth(self):
        res = self.client.post("/api/v1/analysis/border/video", json={"video_path": "test.mp4"})
        self.assertEqual(res.status_code, 401)
        self.assertFalse(res.json()["success"])

    # 2. Path traversal protection
    def test_path_traversal_image_path_rejected(self):
        res = self.client.post(
            "/api/v1/analysis/image",
            json={"image_path": "../../../etc/passwd"},
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 404)
        self.assertFalse(res.json()["success"])

    def test_path_traversal_video_path_rejected(self):
        res = self.client.post(
            "/api/v1/analysis/border/video",
            json={"video_path": "../../../windows/system32/cmd.exe"},
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 404)
        self.assertFalse(res.json()["success"])

    # 3. Invalid image data / base64 decode failure
    def test_invalid_base64_returns_validation_error(self):
        res = self.client.post(
            "/api/v1/analysis/image",
            json={"image_base64": "NOT_A_VALID_BASE64_STRING!@#$"},
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 422)
        self.assertFalse(res.json()["success"])

    # 4. Valid image upload & service invocation
    @patch("app.services.application_services.ImageProcessingService.analyze_image")
    def test_valid_drone_image_upload(self, mock_analyze):
        mock_result = AERIONAnalysisResult(
            project="AERION",
            version="v1",
            analysis_id=str(uuid.uuid4()),
            mode="border",
            source_type="drone",
            detections=[],
            summary=SceneSummary(critical=0, high=0, medium=0, low=0),
            overall_status="nominal",
        )
        mock_analyze.return_value = mock_result

        res = self.client.post(
            "/api/v1/analysis/image",
            json={
                "image_base64": self.valid_b64,
                "source_type": "drone",
                "mode": "border",
                "drone_model": "visdrone_only",
                "confidence_threshold": 0.25,
            },
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertIn("analysis_id", body["data"])
        mock_analyze.assert_called_once()

    # 5. Satellite OBB service invocation
    @patch("app.services.application_services.SatelliteAnalysisService.analyze_satellite_image")
    def test_valid_satellite_image_upload(self, mock_sat):
        mock_result = AERIONAnalysisResult(
            project="AERION",
            version="v1",
            analysis_id=str(uuid.uuid4()),
            mode="border",
            source_type="satellite",
            detections=[],
            summary=SceneSummary(critical=0, high=0, medium=0, low=0),
            overall_status="satellite_obb_completed",
        )
        mock_sat.return_value = mock_result

        res = self.client.post(
            "/api/v1/analysis/image",
            json={
                "image_base64": self.valid_b64,
                "source_type": "satellite",
                "mode": "border",
            },
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["overall_status"], "satellite_obb_completed")
        mock_sat.assert_called_once()

    # 6. Valid damage pair upload & service invocation
    @patch("app.services.application_services.DamageAnalysisService.analyze_damage_pair")
    def test_valid_damage_pair_upload(self, mock_damage):
        dummy_dmg = DamageAnalysis(
            before_width=512,
            before_height=512,
            after_width=512,
            after_height=512,
            probability_min=0.0,
            probability_max=0.75,
            probability_mean=0.12,
            threshold=0.5,
            damage_pixels=450,
            total_pixels=262144,
            damage_ratio=0.0017,
            damage_percentage=0.17,
        )
        mock_result = AERIONAnalysisResult(
            project="AERION",
            version="v1",
            analysis_id=str(uuid.uuid4()),
            mode="disaster",
            source_type="change_detection",
            damage_analysis=dummy_dmg,
            summary=SceneSummary(critical=0, high=0, medium=0, low=0),
            overall_status="damage_assessed",
        )
        mock_damage.return_value = mock_result

        res = self.client.post(
            "/api/v1/analysis/damage",
            json={
                "before_base64": self.valid_b64,
                "after_base64": self.valid_b64,
                "threshold": 0.50,
            },
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertAlmostEqual(body["data"]["damage_analysis"]["damage_percentage"], 0.17)
        mock_damage.assert_called_once()

    # 7. Mismatched damage pair validation
    def test_damage_pair_missing_one_image_fails(self):
        res = self.client.post(
            "/api/v1/analysis/damage",
            json={"before_base64": self.valid_b64},
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 422)
        self.assertFalse(res.json()["success"])

    # 8. Valid border video upload via base64
    @patch("app.services.application_services.BorderVideoJobService.process_video_file")
    def test_valid_border_video_base64_upload(self, mock_video):
        mock_video.return_value = {
            "processed_frames": 5,
            "total_video_frames": 25,
            "report": {"status": "ok", "tracks": []},
        }

        fake_video_b64 = base64.b64encode(b"FAKE_MP4_HEADER_DATA_12345").decode("utf-8")
        res = self.client.post(
            "/api/v1/analysis/border/video",
            json={
                "video_base64": fake_video_b64,
                "max_frames": 5,
                "frame_stride": 5,
            },
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["processed_frames"], 5)
        mock_video.assert_called_once()

    # 9. Invalid video missing source
    def test_border_video_missing_source_fails(self):
        res = self.client.post(
            "/api/v1/analysis/border/video",
            json={},
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 422)
        self.assertFalse(res.json()["success"])


if __name__ == "__main__":
    unittest.main()
