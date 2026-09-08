"""
AERION — Error Handling Integration Tests
Tests error envelopes, custom exceptions, validation failures, and unhandled exception shielding.
"""

import unittest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.config import AERIONSettings
from app.core.errors import (
    AERIONException,
    InferenceTimeoutError,
    ModelUnavailableError,
    RateLimitExceededError,
    ResourceNotFoundError,
    ValidationError,
)
from app.main import create_app


class SampleRequest(BaseModel):
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_type: str = Field(..., min_length=2)


class TestErrorHandling(unittest.TestCase):

    def setUp(self):
        self.settings = AERIONSettings(ENVIRONMENT="test")
        self.app = create_app(settings=self.settings)

        # Add mock endpoints to trigger specific error conditions
        mock_router = APIRouter(prefix="/test-errors")

        @mock_router.post("/validate")
        async def mock_validation(body: SampleRequest):
            return {"status": "ok"}

        @mock_router.get("/custom-not-found")
        async def mock_not_found():
            raise ResourceNotFoundError("Asset 'ast-999' not found.")

        @mock_router.get("/custom-timeout")
        async def mock_timeout():
            raise InferenceTimeoutError()

        @mock_router.get("/custom-model-unavailable")
        async def mock_model_unavail():
            raise ModelUnavailableError()

        @mock_router.get("/custom-rate-limit")
        async def mock_rate_limit():
            raise RateLimitExceededError()

        @mock_router.get("/unhandled-crash")
        async def mock_unhandled():
            raise RuntimeError("Database connection password=supersecret leaked!")

        self.app.include_router(mock_router)
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_pydantic_validation_error_envelope(self):
        response = self.client.post("/test-errors/validate", json={"confidence": 2.5, "source_type": "x"})
        self.assertEqual(response.status_code, 422)
        payload = response.json()

        self.assertFalse(payload["success"])
        err = payload["error"]
        self.assertEqual(err["code"], "VALIDATION_ERROR")
        self.assertEqual(err["error_type"], "ClientError")
        self.assertTrue(len(err["details"]) >= 2)
        self.assertTrue(len(err["request_id"]) > 0)
        self.assertIn("timestamp", err)

    def test_resource_not_found_envelope(self):
        response = self.client.get("/test-errors/custom-not-found")
        self.assertEqual(response.status_code, 404)
        payload = response.json()

        self.assertFalse(payload["success"])
        err = payload["error"]
        self.assertEqual(err["code"], "RESOURCE_NOT_FOUND")
        self.assertEqual(err["message"], "Asset 'ast-999' not found.")
        self.assertEqual(err["error_type"], "ClientError")

    def test_inference_timeout_envelope(self):
        response = self.client.get("/test-errors/custom-timeout")
        self.assertEqual(response.status_code, 503)
        payload = response.json()

        self.assertFalse(payload["success"])
        err = payload["error"]
        self.assertEqual(err["code"], "INFERENCE_TIMEOUT")
        self.assertEqual(err["error_type"], "ResourceExhaustionError")

    def test_model_unavailable_envelope(self):
        response = self.client.get("/test-errors/custom-model-unavailable")
        self.assertEqual(response.status_code, 503)
        payload = response.json()

        self.assertFalse(payload["success"])
        err = payload["error"]
        self.assertEqual(err["code"], "MODEL_UNAVAILABLE")

    def test_rate_limit_exceeded_envelope(self):
        response = self.client.get("/test-errors/custom-rate-limit")
        self.assertEqual(response.status_code, 429)
        payload = response.json()

        self.assertFalse(payload["success"])
        err = payload["error"]
        self.assertEqual(err["code"], "RATE_LIMIT_EXCEEDED")

    def test_404_unregistered_route(self):
        response = self.client.get("/non-existent-path-xyz")
        self.assertEqual(response.status_code, 404)
        payload = response.json()

        self.assertFalse(payload["success"])
        err = payload["error"]
        self.assertEqual(err["code"], "RESOURCE_NOT_FOUND")

    def test_unhandled_exception_does_not_leak_internals(self):
        response = self.client.get("/test-errors/unhandled-crash")
        self.assertEqual(response.status_code, 500)
        payload = response.json()

        self.assertFalse(payload["success"])
        err = payload["error"]
        self.assertEqual(err["code"], "PROCESSING_FAILURE")
        # Internal secret in RuntimeError message must NOT appear in client payload
        self.assertNotIn("supersecret", response.text)
        self.assertNotIn("RuntimeError", response.text)
        self.assertIn("unexpected server error occurred", err["message"])


if __name__ == "__main__":
    unittest.main()
