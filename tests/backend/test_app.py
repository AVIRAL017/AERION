"""
AERION — Application Integration Tests
Tests application factory, Request ID lifecycle, Security Headers, and CORS enforcement.
"""

import unittest
from fastapi.testclient import TestClient

from app.core.config import AERIONSettings
from app.main import create_app


class TestApplicationSecurityAndMiddleware(unittest.TestCase):

    def setUp(self):
        self.settings = AERIONSettings(
            ENVIRONMENT="test",
            ALLOWED_ORIGINS=["https://dashboard.aerion.org", "http://localhost:3000"],
            MAX_REQUEST_ID_LENGTH=32,
        )
        self.app = create_app(settings=self.settings)
        self.client = TestClient(self.app)

    def test_request_id_generated_when_absent(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        req_id = response.headers.get("X-Request-ID")
        self.assertIsNotNone(req_id)
        # Should match UUID4 string representation
        self.assertEqual(len(req_id), 36)
        # Envelope meta must match
        payload = response.json()
        self.assertEqual(payload["meta"]["request_id"], req_id)

    def test_request_id_propagated_when_valid(self):
        client_id = "test-req-12345"
        response = self.client.get("/health", headers={"X-Request-ID": client_id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Request-ID"), client_id)
        payload = response.json()
        self.assertEqual(payload["meta"]["request_id"], client_id)

    def test_request_id_regenerated_when_oversized(self):
        oversized_id = "a" * 100  # Exceeds MAX_REQUEST_ID_LENGTH=32
        response = self.client.get("/health", headers={"X-Request-ID": oversized_id})
        self.assertEqual(response.status_code, 200)
        req_id = response.headers.get("X-Request-ID")
        self.assertNotEqual(req_id, oversized_id)
        self.assertEqual(len(req_id), 36)

    def test_request_id_regenerated_when_malformed(self):
        malformed_id = "invalid id with spaces & symbols <script>"
        response = self.client.get("/health", headers={"X-Request-ID": malformed_id})
        self.assertEqual(response.status_code, 200)
        req_id = response.headers.get("X-Request-ID")
        self.assertNotEqual(req_id, malformed_id)
        self.assertEqual(len(req_id), 36)

    def test_security_headers_present_on_response(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        headers = response.headers

        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertEqual(headers.get("Content-Security-Policy"), "default-src 'none'; frame-ancestors 'none'")
        self.assertIn("accelerometer=()", headers.get("Permissions-Policy", ""))

    def test_cors_allowed_origin(self):
        # OPTIONS preflight request
        response = self.client.options(
            "/health",
            headers={
                "Origin": "https://dashboard.aerion.org",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "https://dashboard.aerion.org")
        self.assertEqual(response.headers.get("Access-Control-Allow-Credentials"), "true")

    def test_cors_disallowed_origin(self):
        response = self.client.options(
            "/health",
            headers={
                "Origin": "https://unauthorized-attacker.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Unauthorized origin should not receive Access-Control-Allow-Origin
        self.assertNotEqual(response.headers.get("Access-Control-Allow-Origin"), "https://unauthorized-attacker.com")


if __name__ == "__main__":
    unittest.main()
