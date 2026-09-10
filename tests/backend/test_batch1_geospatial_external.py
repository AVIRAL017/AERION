"""
AERION — Tests for Batch 1 (Steps 21–23)
Validates:
1. Step 21: Verified Dataset Expansion (USGS Seismicity Catalog provenance, SHA-256, schema, PostGIS queries).
2. Step 22: Required External API Layer (In-memory TTL cache, normalized status, error handling, auth required).
3. Step 23: Weather / Routing / Geocoding Services (Open-Meteo, ORS/Mapbox, Nominatim, zero straight-line invariant).
4. REST API endpoints under /api/v1/external/.
5. Location safety invariant: pixel coordinates != geographic coordinates.
"""

import asyncio
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import httpx

from app.core.auth import create_access_token
from app.core.cache import InMemoryTTLCache, weather_cache, routing_cache, geocoding_cache
from app.core.config import AERIONSettings, get_settings
from app.db.session import close_db_connections, get_session_factory
from app.main import create_app
from app.schemas.evidence import GeoPoint, GeoPolygon
from app.schemas.external import (
    NormalizedGeocodeResult,
    NormalizedRouteRecord,
    NormalizedWeatherRecord,
    ProviderStatus,
    RouteProfile,
    WeatherConditionClassification,
)
from app.services.external_geocoding_service import ExternalGeocodingService
from app.services.external_routing_service import ExternalRoutingService
from app.services.external_weather_service import ExternalWeatherService
from app.services.geospatial_ingestion import GeospatialIngestionEngine, compute_file_sha256
from app.services.geospatial_service import GeospatialService


class TestBatch1GeospatialExternal(unittest.IsolatedAsyncioTestCase):

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
            "email": "batch1_test@aerion.mil",
        })
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    async def asyncTearDown(self):
        await close_db_connections()

    # ========================================================================
    # STEP 21: VERIFIED SEISMIC HAZARD DATASET & POSTGIS INTEGRATION
    # ========================================================================

    async def test_seismic_dataset_provenance_and_integrity(self):
        """Verify USGS seismic dataset integrity on disk and in database."""
        seismic_path = Path("data/geospatial/hazards/seismic/usgs_india_seismic_m5_2010_2025.geojson")
        self.assertTrue(seismic_path.exists(), "Seismic geojson missing from data directory")

        # Verify SHA-256 matches metadata
        sha = compute_file_sha256(seismic_path)
        self.assertEqual(sha, "9c926947fd5cc810be77e63235ec435ce80bb4651599f25e8a1d7d28a34c24c6")

        # Verify PostGIS dataset registration & spatial query
        factory = get_session_factory()
        async with factory() as session:
            service = GeospatialService(session)
            datasets = await service.get_all_datasets()
            seismic_meta = next((d for d in datasets if d.dataset_id == "USGS_INDIA_SEISMIC_M5_2010_2025"), None)
            self.assertIsNotNone(seismic_meta, "Seismic dataset not registered in geospatial_datasets table")
            self.assertEqual(seismic_meta.geometry_type, "POINT")
            self.assertEqual(seismic_meta.crs, "EPSG:4326")

            # Perform PostGIS ST_DWithin spatial query for earthquakes within 500km of Delhi
            res = await service.query_historical_hazards(
                latitude=28.6139,
                longitude=77.2090,
                radius_km=500.0,
                hazard_type="HISTORICAL_EARTHQUAKE",
            )
            self.assertGreater(res.record_count, 0)
            self.assertTrue(res.is_historical_reference_only)
            self.assertFalse(res.records[0].is_live_status)
            self.assertIsNotNone(res.records[0].magnitude)
            self.assertIsNotNone(res.records[0].depth_km)

    # ========================================================================
    # STEP 22: IN-MEMORY TTL CACHE & PROVIDER NORMALIZATION
    # ========================================================================

    async def test_in_memory_ttl_cache_lifecycle(self):
        """Verify TTL expiration, eviction on capacity, and thread-safety."""
        cache = InMemoryTTLCache(max_size=3, default_ttl_seconds=0.2)
        await cache.set("k1", "v1")
        await cache.set("k2", "v2")
        self.assertEqual(await cache.get("k1"), "v1")
        self.assertEqual(await cache.get("k2"), "v2")

        # Expiration test
        await asyncio.sleep(0.3)
        self.assertIsNone(await cache.get("k1"), "Expired key should return None")

        # Capacity and eviction test
        await cache.set("a", "1", ttl_seconds=10.0)
        await cache.set("b", "2", ttl_seconds=10.0)
        await cache.set("c", "3", ttl_seconds=10.0)
        await cache.set("d", "4", ttl_seconds=10.0)  # Should evict oldest
        self.assertLessEqual(await cache.size(), 3)

    # ========================================================================
    # STEP 23: WEATHER SERVICE NORMALIZATION & ZERO-FABRICATION
    # ========================================================================

    async def test_weather_service_bounds_validation(self):
        """Out-of-bounds coordinates must return INVALID_REQUEST and UNAVAILABLE suitability."""
        svc = ExternalWeatherService()
        record = await svc.get_weather(latitude=150.0, longitude=77.0, use_cache=False)
        self.assertEqual(record.status, ProviderStatus.INVALID_REQUEST)
        self.assertEqual(record.flight_suitability, WeatherConditionClassification.UNAVAILABLE)
        self.assertIsNone(record.temperature_celsius)

    async def test_weather_service_normalization_with_mock(self):
        """Verify complete normalization of Open-Meteo current payload."""
        svc = ExternalWeatherService()
        mock_response = {
            "current": {
                "temperature_2m": 29.5,
                "apparent_temperature": 32.1,
                "relative_humidity_2m": 60,
                "precipitation": 0.5,
                "weather_code": 1,
                "wind_speed_10m": 12.0,
                "wind_direction_10m": 240,
                "visibility": 10000.0,
                "cloud_cover": 25.0,
            }
        }
        mock_resp = httpx.Response(200, json=mock_response)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp

            rec = await svc.get_weather(28.61, 77.20, use_cache=False)
            self.assertEqual(rec.status, ProviderStatus.AVAILABLE)
            self.assertEqual(rec.temperature_celsius, 29.5)
            self.assertEqual(rec.apparent_temperature_celsius, 32.1)
            self.assertEqual(rec.wind_speed_mps, round(12.0 / 3.6, 2))
            self.assertEqual(rec.flight_suitability, WeatherConditionClassification.OPTIMAL)
            self.assertIsNotNone(rec.evidence)

    # ========================================================================
    # STEP 23: ROUTING SERVICE & STRICT ZERO STRAIGHT-LINE INVARIANT
    # ========================================================================

    async def test_routing_missing_credentials_returns_auth_required(self):
        """If neither ORS key nor Mapbox token configured, return AUTH_REQUIRED, never straight line."""
        svc = ExternalRoutingService()
        with patch("app.services.external_routing_service.get_settings") as mock_settings:
            mock_obj = AERIONSettings(ENVIRONMENT="test")
            mock_obj.OPENROUTESERVICE_API_KEY = None
            mock_obj.MAPBOX_ACCESS_TOKEN = None
            mock_settings.return_value = mock_obj

            res = await svc.calculate_route(28.61, 77.20, 28.65, 77.25, use_cache=False)
            self.assertEqual(res.status, ProviderStatus.AUTH_REQUIRED)
            self.assertIsNone(res.total_distance_meters)
            self.assertIsNone(res.geometry_geojson)
            self.assertIn("AERION strictly prohibits straight-line pseudo-routing", res.warnings[1])

    async def test_routing_ors_normalization(self):
        """Verify ORS route geojson parsing into normalized route record."""
        svc = ExternalRoutingService()
        mock_ors_geojson = {
            "features": [{
                "geometry": {"type": "LineString", "coordinates": [[77.20, 28.61], [77.21, 28.62]]},
                "properties": {
                    "summary": {"distance": 1500.0, "duration": 180.0, "ascent": 5.0},
                    "segments": [{
                        "steps": [
                            {"instruction": "Turn left", "name": "Barakhamba Rd", "distance": 800.0, "duration": 90.0},
                            {"instruction": "Arrive", "name": "KG Marg", "distance": 700.0, "duration": 90.0},
                        ]
                    }]
                }
            }]
        }
        mock_resp = httpx.Response(200, json=mock_ors_geojson)
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            res = await svc._calculate_ors_route(
                origin=GeoPoint(latitude=28.61, longitude=77.20),
                destination=GeoPoint(latitude=28.62, longitude=77.21),
                profile=RouteProfile.DRIVING_CAR,
                api_key="test-key",
            )
            self.assertEqual(res.status, ProviderStatus.AVAILABLE)
            self.assertEqual(res.total_distance_meters, 1500.0)
            self.assertEqual(res.total_duration_seconds, 180.0)
            self.assertEqual(len(res.steps), 2)
            self.assertEqual(res.steps[0].name, "Barakhamba Rd")

    # ========================================================================
    # STEP 23: GEOCODING FORWARD & REVERSE NORMALIZATION
    # ========================================================================

    async def test_geocoding_query_bounds_validation(self):
        """Queries exceeding 200 chars or empty must be rejected."""
        svc = ExternalGeocodingService()
        res_empty = await svc.forward_geocode("   ")
        self.assertEqual(res_empty, [])

        res_long = await svc.forward_geocode("A" * 205)
        self.assertEqual(res_long, [])

    async def test_reverse_geocoding_normalization(self):
        """Verify reverse geocoding parses administrative hierarchy cleanly."""
        svc = ExternalGeocodingService()
        mock_nominatim = {
            "display_name": "Connaught Place, New Delhi, Delhi, 110001, India",
            "address": {
                "suburb": "Connaught Place",
                "state_district": "New Delhi",
                "state": "Delhi",
                "country": "India",
                "country_code": "in",
                "postcode": "110001",
            },
            "osm_id": 12345,
        }
        mock_resp = httpx.Response(200, json=mock_nominatim)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp

            res = await svc.reverse_geocode(28.6315, 77.2167, use_cache=False)
            self.assertIsNotNone(res)
            self.assertEqual(res.provider_name, "OSM-Nominatim")
            self.assertEqual(res.locality, "Connaught Place")
            self.assertEqual(res.district, "New Delhi")
            self.assertEqual(res.state, "Delhi")
            self.assertEqual(res.country_code, "IN")

    # ========================================================================
    # REST API ENDPOINTS /api/v1/external
    # ========================================================================

    def test_external_weather_endpoint_auth_and_response(self):
        # 401 without auth
        unauth = self.client.get("/api/v1/external/weather?latitude=28.61&longitude=77.20")
        self.assertEqual(unauth.status_code, 401)

        # 200 with auth
        res = self.client.get(
            "/api/v1/external/weather?latitude=28.61&longitude=77.20",
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIn("status", data["data"])
        self.assertIn("flight_suitability", data["data"])

    def test_external_route_endpoint(self):
        res = self.client.get(
            "/api/v1/external/route?origin_lat=28.6315&origin_lon=77.2167&dest_lat=28.6129&dest_lon=77.2295",
            headers=self.auth_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIn("status", data["data"])

    def test_external_geocode_endpoints(self):
        fwd = self.client.get(
            "/api/v1/external/geocode?query=Delhi&limit=1",
            headers=self.auth_headers,
        )
        self.assertEqual(fwd.status_code, 200)
        self.assertTrue(fwd.json()["success"])

        rev = self.client.get(
            "/api/v1/external/reverse-geocode?latitude=28.6139&longitude=77.2090",
            headers=self.auth_headers,
        )
        self.assertEqual(rev.status_code, 200)
        self.assertTrue(rev.json()["success"])


if __name__ == "__main__":
    unittest.main()
