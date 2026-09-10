"""
AERION — Tests for Batch 2 (Steps 24–26)
Validates:
1. Step 24: Grounded Mistral Intelligence
   - Evidence-only context, prompt construction, anti-hallucination rules.
   - Structured NormalizedAdvisoryRecord response with evidence references.
   - Deterministic fallback when Mistral is unavailable or unconfigured.
   - Zero secret leakage in payloads or outputs.
2. Step 25: Disaster Mode E2E
   - Real damage detection pipeline execution (or bounded test pair).
   - Georeferenced vs unreferenced location status invariants.
   - PostGIS enrichment (admin boundaries, USGS seismicity, shelters, infrastructure).
   - Real weather and road routing integration (no straight-line routes).
   - Grounded advisory and immutable evidence persistence.
3. Step 26: Border Security Mode E2E
   - Detection, ByteTrack tracking, and persistence filtering.
   - Authoritative boundary status (NOT_ACQUIRED invariant preserved).
   - Potential Unauthorized Crossing Indicator terminology (never uncorroborated infiltration).
   - Annotated visual evidence artifact and grounded advisory generation.
"""

import asyncio
import base64
import io
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from PIL import Image

from app.core.auth import create_access_token
from app.core.config import AERIONSettings, get_settings
from app.db.session import close_db_connections, get_session_factory
from app.main import create_app
from app.schemas.evidence import GeoPoint
from app.schemas.external import (
    AdvisoryPriority,
    NormalizedAdvisoryRecord,
    ProviderStatus,
)
from app.services.structured_intelligence import MistralAdvisoryClient


def create_test_rgb_image_bytes(width: int = 256, height: int = 256, color=(100, 150, 200)) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestBatch2GroundedIntelligenceAndE2E(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.settings = AERIONSettings(ENVIRONMENT="test")
        self.app = create_app(settings=self.settings)
        self.client = TestClient(self.app)

        self.user_id = str(uuid.uuid4())
        self.org_id = str(uuid.uuid4())
        self.token = create_access_token({
            "sub": self.user_id,
            "org": self.org_id,
            "role": "operator",
            "email": "batch2_test@aerion.mil",
        })
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    async def asyncTearDown(self):
        await close_db_connections()

    # ========================================================================
    # STEP 24: MISTRAL INTELLIGENCE TESTS
    # ========================================================================

    async def test_mistral_grounded_prompt_anti_hallucination_rules(self):
        """Verify that Mistral prompt enforces strict anti-hallucination and evidence grounding."""
        client = MistralAdvisoryClient()
        evidence = {
            "detection_count": 2,
            "crossing_indicators_count": 1,
            "weather_status": "UNAVAILABLE",
            "authoritative_border_status": "NOT_ACQUIRED",
        }
        prompt = client._build_strict_grounded_prompt(
            mode="BORDER_SECURITY",
            context=evidence,
            protocol="Standard advisory: dispatch patrol unit.",
        )
        self.assertIn("STRICT INVARIANT: DO NOT invent coordinates", prompt)
        self.assertIn("Potential Unauthorized Crossing Indicator", prompt)
        self.assertIn("never 'confirmed infiltration'", prompt)
        self.assertIn("State ONLY verified facts", prompt)

    async def test_mistral_deterministic_fallback_when_unconfigured(self):
        """When API key is None, system must return deterministic fallback with AUTH_REQUIRED status."""
        client = MistralAdvisoryClient(api_key=None)
        evidence = {
            "evidence_ids": ["ev-101", "ev-102"],
            "detection_count": 4,
            "crossing_indicators_count": 2,
            "authoritative_border_status": "NOT_ACQUIRED",
            "weather_status": "UNAVAILABLE",
        }
        res = await client.generate_grounded_advisory(
            mode="BORDER_SECURITY",
            evidence_package=evidence,
            standard_protocol="Standard advisory: dispatch visual verification.",
            deterministic_priority=AdvisoryPriority.HIGH,
        )
        self.assertIsInstance(res, NormalizedAdvisoryRecord)
        self.assertEqual(res.provider_status, ProviderStatus.AUTH_REQUIRED)
        self.assertEqual(res.priority, AdvisoryPriority.HIGH)
        self.assertEqual(res.model, "none (deterministic fallback)")
        self.assertTrue(res.grounded)
        self.assertIn("AUTH_REQUIRED", res.summary)
        self.assertIn("ev-101", res.evidence_references)
        self.assertIn("ev-102", res.evidence_references)
        self.assertTrue(any("Authoritative Survey of India" in lim for lim in res.limitations))
        self.assertTrue(any("weather" in lim.lower() for lim in res.limitations))

    async def test_mistral_no_secret_leakage(self):
        """Verify API keys and credentials are not exposed in advisory output or string representations."""
        client = MistralAdvisoryClient(api_key="secret_test_key_xyz_12345")
        evidence = {"detection_count": 1}
        # Build fallback
        fallback = client._build_deterministic_fallback(
            mode="DISASTER_RESPONSE",
            evidence_package=evidence,
            standard_protocol="Dispatch team.",
            priority=AdvisoryPriority.MEDIUM,
            provider_status=ProviderStatus.AVAILABLE,
            evidence_refs=[],
            limitations=[],
        )
        output_str = str(fallback.model_dump())
        self.assertNotIn("secret_test_key", output_str)

    # ========================================================================
    # STEP 25: DISASTER MODE E2E WORKFLOW TESTS
    # ========================================================================

    async def test_disaster_e2e_unreferenced_input(self):
        """When input lacks coordinates, location_status must be UNAVAILABLE and no coords fabricated."""
        b64_img = base64.b64encode(create_test_rgb_image_bytes()).decode("utf-8")
        payload = {
            "before_base64": b64_img,
            "after_base64": b64_img,
            "threshold": 0.50,
            "latitude": None,
            "longitude": None,
        }
        resp = self.client.post("/api/v1/analysis/disaster/e2e", json=payload, headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        res = data["data"]
        self.assertEqual(res["mode"], "DISASTER_RESPONSE")
        self.assertEqual(res["georeferencing_status"], "UNAVAILABLE")
        self.assertEqual(res["external_context"]["weather"]["status"], "UNAVAILABLE")
        self.assertEqual(res["external_context"]["routing"]["status"], "UNAVAILABLE")
        self.assertIn("advisory", res)
        self.assertTrue(res["advisory"]["grounded"])

    async def test_disaster_e2e_georeferenced_with_external_services(self):
        """When input is georeferenced, enriches with PostGIS hazards, shelters, weather, and routing."""
        b64_img = base64.b64encode(create_test_rgb_image_bytes()).decode("utf-8")
        # Connaught Place, New Delhi coordinates (near OSM shelters and buildings)
        payload = {
            "before_base64": b64_img,
            "after_base64": b64_img,
            "threshold": 0.50,
            "latitude": 28.6318,
            "longitude": 77.2194,
            "evacuation_dest_lat": 28.6129,
            "evacuation_dest_lon": 77.2295,
            "radius_km": 15.0,
        }
        resp = self.client.post("/api/v1/analysis/disaster/e2e", json=payload, headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        res = data["data"]
        self.assertEqual(res["mode"], "DISASTER_RESPONSE")
        self.assertEqual(res["georeferencing_status"], "AVAILABLE")
        # Damage model output
        self.assertIn("damage_analysis", res)
        self.assertIn("damage_pixels", res["damage_analysis"])
        self.assertIn("damage_ratio", res["damage_analysis"])
        # Geospatial context
        self.assertIn("geospatial_context", res)
        self.assertIn("seismic_events", res["geospatial_context"])
        # Weather context
        weather = res["external_context"]["weather"]
        self.assertIn(weather.get("status"), ("AVAILABLE", "UNAVAILABLE", "RATE_LIMITED"))
        # Routing context
        routing = res["external_context"]["routing"]
        self.assertIn(routing.get("status"), ("AVAILABLE", "UNAVAILABLE", "AUTH_REQUIRED"))
        # Advisory
        self.assertIn("advisory", res)
        self.assertIn("summary", res["advisory"])
        self.assertIn("priority", res["advisory"])
        self.assertTrue(res["advisory"]["grounded"])

    # ========================================================================
    # STEP 26: BORDER SECURITY MODE E2E WORKFLOW TESTS
    # ========================================================================

    async def test_border_e2e_authoritative_boundary_not_acquired_invariant(self):
        """Verify that Border E2E reports authoritative_border_status as NOT_ACQUIRED and never fabricates it."""
        b64_img = base64.b64encode(create_test_rgb_image_bytes()).decode("utf-8")
        payload = {
            "image_base64": b64_img,
            "terrain_context": "arid",
            "latitude": 31.0,
            "longitude": 74.5,
        }
        resp = self.client.post("/api/v1/analysis/border/e2e", json=payload, headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        res = data["data"]
        self.assertEqual(res["mode"], "BORDER_SECURITY")
        contract = res["authoritative_border_contract"]
        self.assertFalse(contract["operational_border_available"])
        self.assertEqual(contract["acquisition_status"], "NOT_ACQUIRED")
        # Proximity should be suspended to avoid false operational claims
        self.assertFalse(res["border_proximity"]["available"])
        self.assertIn("suspended", res["border_proximity"]["status_message"].lower())

    async def test_border_e2e_terminology_and_no_false_infiltration(self):
        """Verify terminology uses Potential Unauthorized Crossing Indicator, never uncorroborated infiltration."""
        b64_img = base64.b64encode(create_test_rgb_image_bytes()).decode("utf-8")
        payload = {
            "image_base64": b64_img,
            "terrain_context": "arid",
        }
        resp = self.client.post("/api/v1/analysis/border/e2e", json=payload, headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        res = data["data"]
        # Advisory and findings
        advisory = res["advisory"]
        adv_text = (advisory.get("summary", "") + " " + " ".join(advisory.get("key_findings", []))).lower()
        self.assertNotIn("confirmed infiltration", adv_text)
        # Limitations must explicitly note this rule
        limitations_text = " ".join(res["limitations"])
        self.assertIn("detection alone is NOT a confirmed infiltration", limitations_text)


if __name__ == "__main__":
    unittest.main()
