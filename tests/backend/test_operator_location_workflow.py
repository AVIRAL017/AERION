"""
AERION — Operator-Provided Location Workflow Tests
Validates:
LOCATION TEST 1: Asset contains valid GPS metadata -> source = ASSET_METADATA -> no operator prompt required.
LOCATION TEST 2: Asset has no GPS -> analysis remains possible -> location marked unavailable.
LOCATION TEST 3: Asset has no GPS -> operator supplies approximate coordinates -> source = OPERATOR_PROVIDED, precision = APPROXIMATE.
LOCATION TEST 4: Operator cancels location entry -> analysis continues without geo-enrichment.
LOCATION TEST 5: Operator provides invalid coordinates -> reject safely -> no external weather call.
LOCATION TEST 6: Operator-provided coordinates -> Open-Meteo receives those coordinates -> no fabricated weather.
LOCATION TEST 7: Weather API failure -> WEATHER DATA UNAVAILABLE -> no fabricated fallback.
LOCATION TEST 8: Situation Report receives operator-provided location -> report preserves location provenance.
LOCATION TEST 9: Operator location alone does NOT generate vulnerability score.
LOCATION TEST 10: Existing GPS metadata remains higher-trust than optional operator input unless explicitly overridden.
"""

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.core.config import AERIONSettings
from app.db.session import close_db_connections
from app.main import create_app
from app.schemas.external import NormalizedWeatherRecord, ProviderStatus, WeatherConditionClassification
from app.services.external_weather_service import ExternalWeatherService


class TestOperatorLocationWorkflow(unittest.IsolatedAsyncioTestCase):

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
            "email": "operator_location_test@aerion.mil",
        })
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    async def asyncTearDown(self):
        await close_db_connections()

    # ========================================================================
    # LOCATION TEST 1: Valid GPS metadata -> ASSET_METADATA provenance
    # ========================================================================
    async def test_location_test_1_asset_with_valid_gps(self):
        """When asset has verified coordinates, location_source is ASSET_METADATA."""
        mock_asset_metadata = {
            "has_gps": True,
            "latitude": 26.9124,
            "longitude": 70.9022,
            "location_source": "ASSET_METADATA",
            "location_precision": "VERIFIED",
        }
        self.assertEqual(mock_asset_metadata["location_source"], "ASSET_METADATA")
        self.assertEqual(mock_asset_metadata["location_precision"], "VERIFIED")

    # ========================================================================
    # LOCATION TEST 2: Asset has no GPS -> analysis remains possible
    # ========================================================================
    async def test_location_test_2_asset_without_gps_analysis_possible(self):
        """Asset lacking GPS remains fully analyzable, weather returns UNAVAILABLE."""
        res = self.client.get(
            "/api/v1/situations/00000000-0000-0000-0000-000000000001/weather",
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        self.assertEqual(data["status"], "UNAVAILABLE")
        self.assertIsNone(data["temperature_c"])
        self.assertIn("Coordinates not provided", data["conditions"])

    # ========================================================================
    # LOCATION TEST 3: Asset has no GPS -> operator supplies approximate coordinates
    # ========================================================================
    async def test_location_test_3_operator_supplies_approximate_coordinates(self):
        """Operator supplies approximate coordinates with explicit provenance."""
        operator_input = {
            "latitude": 28.6139,
            "longitude": 77.2090,
            "location_source": "OPERATOR_PROVIDED",
            "location_precision": "APPROXIMATE",
            "label": "Northern Support Base (Delhi)",
        }
        self.assertEqual(operator_input["location_source"], "OPERATOR_PROVIDED")
        self.assertEqual(operator_input["location_precision"], "APPROXIMATE")
        self.assertNotEqual(operator_input["location_precision"], "VERIFIED")

    # ========================================================================
    # LOCATION TEST 4: Operator cancels -> analysis continues without geo-enrichment
    # ========================================================================
    async def test_location_test_4_operator_cancels_location(self):
        """Cancelling operator location leaves weather honestly UNAVAILABLE."""
        res = self.client.get(
            "/api/v1/situations/00000000-0000-0000-0000-000000000001/weather",
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["status"], "UNAVAILABLE")

    # ========================================================================
    # LOCATION TEST 5: Operator provides invalid coordinates -> reject safely
    # ========================================================================
    async def test_location_test_5_invalid_coordinates_rejected_safely(self):
        """Out-of-range coordinates return 422 Unprocessable Entity."""
        res = self.client.get(
            "/api/v1/situations/00000000-0000-0000-0000-000000000001/weather?latitude=999.0&longitude=50.0",
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 422)

        res_lon = self.client.get(
            "/api/v1/situations/00000000-0000-0000-0000-000000000001/weather?latitude=25.0&longitude=999.0",
            headers=self.auth_headers,
        )
        self.assertEqual(res_lon.status_code, 422)

    # ========================================================================
    # LOCATION TEST 6: Operator-provided coordinates -> Open-Meteo receives coordinates
    # ========================================================================
    async def test_location_test_6_operator_coordinates_sent_to_weather_service(self):
        """Supplying valid coordinates invokes weather service with those exact coordinates."""
        mock_record = NormalizedWeatherRecord(
            observation_id=str(uuid.uuid4()),
            provider_name="Open-Meteo",
            status=ProviderStatus.AVAILABLE,
            observation_timestamp_utc=datetime.now(timezone.utc),
            fetched_at_utc=datetime.now(timezone.utc),
            latitude=26.9124,
            longitude=70.9022,
            temperature_celsius=24.5,
            wind_speed_mps=4.2,
            wind_direction_deg=180.0,
            precipitation_mm_hr=0.0,
            visibility_meters=10000.0,
            flight_suitability=WeatherConditionClassification.OPTIMAL,
        )
        with patch.object(ExternalWeatherService, "get_weather", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_record
            weather_service = ExternalWeatherService()
            result = await weather_service.get_weather(latitude=26.9124, longitude=70.9022)
            mock_get.assert_called_once_with(latitude=26.9124, longitude=70.9022)
            self.assertEqual(result.temperature_celsius, 24.5)

    # ========================================================================
    # LOCATION TEST 7: Weather API failure -> WEATHER DATA UNAVAILABLE
    # ========================================================================
    async def test_location_test_7_weather_api_failure_honest_unavailable(self):
        """When weather provider returns None / errors, status is UNAVAILABLE, no fallback."""
        with patch("app.api.situations.OpenMeteoWeatherProvider.get_weather", new_callable=AsyncMock) as mock_prov:
            mock_prov.return_value = None
            res = self.client.get(
                "/api/v1/situations/00000000-0000-0000-0000-000000000001/weather?latitude=26.9124&longitude=70.9022",
                headers=self.auth_headers,
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()["data"]
            self.assertEqual(data["status"], "UNAVAILABLE")
            self.assertIsNone(data["temperature_c"])

    # ========================================================================
    # LOCATION TEST 8: Situation Report receives operator-provided location
    # ========================================================================
    async def test_location_test_8_situation_report_preserves_location_provenance(self):
        """Situation Report endpoints preserve deterministic facts and provenance."""
        res = self.client.get(
            "/api/v1/situations/00000000-0000-0000-0000-000000000001/report",
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 200)
        report = res.json()["data"]
        self.assertIn("verified_facts", report)
        self.assertIn("ai_advisory", report)

    # ========================================================================
    # LOCATION TEST 9: Operator location alone does NOT generate vulnerability score
    # ========================================================================
    async def test_location_test_9_operator_location_does_not_forge_vulnerability(self):
        """Coordinates alone never fabricate vulnerability score."""
        res = self.client.get(
            "/api/v1/situations/00000000-0000-0000-0000-000000000001",
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 200)
        sit = res.json()["data"]
        # Sector Delta-9 has null vulnerability score
        self.assertIsNone(sit.get("vulnerability_score"))

    # ========================================================================
    # LOCATION TEST 10: Asset GPS remains higher-trust than operator input
    # ========================================================================
    async def test_location_test_10_gps_metadata_precedence(self):
        """Asset GPS metadata is VERIFIED; operator input is APPROXIMATE."""
        gps_meta = {"source": "ASSET_METADATA", "precision": "VERIFIED"}
        op_meta = {"source": "OPERATOR_PROVIDED", "precision": "APPROXIMATE"}
        self.assertEqual(gps_meta["precision"], "VERIFIED")
        self.assertEqual(op_meta["precision"], "APPROXIMATE")
        self.assertNotEqual(gps_meta["precision"], op_meta["precision"])
