"""
AERION — Health & Readiness Endpoint Integration Tests
Tests liveness and readiness probes conforming to AERION_API_CONTRACT.md Section 1.2.
"""

import unittest
from fastapi.testclient import TestClient

from app.core.config import AERIONSettings
from app.main import create_app


class TestHealthEndpoints(unittest.TestCase):

    def setUp(self):
        self.settings = AERIONSettings(ENVIRONMENT="test")
        self.app = create_app(settings=self.settings)
        self.client = TestClient(self.app)

    def test_root_health_liveness(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        # Verify envelope structure
        self.assertTrue(payload["success"])
        self.assertIn("data", payload)
        self.assertIn("meta", payload)

        # Verify data payload
        self.assertEqual(payload["data"]["status"], "healthy")
        self.assertEqual(payload["data"]["version"], "v1")
        self.assertIn("timestamp", payload["data"])

        # Verify meta block
        self.assertEqual(payload["meta"]["version"], "v1")
        self.assertTrue(len(payload["meta"]["request_id"]) > 0)

    def test_api_v1_health_liveness(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["status"], "healthy")

    def test_root_readiness_probe(self):
        response = self.client.get("/ready")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertTrue(payload["success"])
        self.assertTrue(payload["data"]["ready"])

        components = payload["data"]["components"]
        # Process and config are ready
        self.assertEqual(components["process"]["status"], "ready")
        self.assertEqual(components["config"]["status"], "ready")
        self.assertEqual(components["inference_lock"]["status"], "ready")

        # Active dynamic state representation
        self.assertIn(components["models"]["status"], ["ready", "lazy_unloaded", "degraded", "not_found"])
        self.assertIn(components["database"]["status"], ["ready", "degraded", "unavailable"])
        self.assertIn(components["storage"]["status"], ["ready", "degraded", "unavailable"])
        self.assertIn(components["providers"]["status"], ["ready", "monitored", "configured", "unconfigured"])
        self.assertIn(components["mistral"]["status"], ["configured", "unconfigured"])

    def test_api_v1_readiness_probe(self):
        response = self.client.get("/api/v1/ready")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])


if __name__ == "__main__":
    unittest.main()
