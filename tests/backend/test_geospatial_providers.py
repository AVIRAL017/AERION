"""
AERION — Tests for Phase 3F External Providers & Geospatial Integrations
"""

import unittest
from datetime import datetime, timezone
import uuid

from app.schemas.situation import (
    GeoPoint,
    GeoPolygon,
    HazardZone,
    Modality,
    RouteAssessment,
    RouteStatus,
    RouteType,
    Shelter,
    ShelterStatus,
    ThreatLevel,
    WeatherObservation,
)
from app.services.geospatial_providers import (
    EvacuationRoutingEngine,
    InMemoryHazardZoneRegistry,
    InMemoryShelterRegistry,
    OpenMeteoWeatherProvider,
    OpenRouteServiceProvider,
    RoutingProvider,
    WeatherProvider,
)


class MockWeatherProvider(WeatherProvider):
    async def get_weather(self, latitude, longitude, timestamp_utc=None):
        return WeatherObservation(
            observation_id=str(uuid.uuid4()),
            provider_name="MockWeather",
            observation_timestamp_utc=timestamp_utc or datetime.now(timezone.utc),
            is_historical_reconstructed=False,
            latitude=latitude,
            longitude=longitude,
            temperature_celsius=24.5,
            wind_speed_mps=4.2,
            wind_direction_deg=180.0,
            precipitation_mm_hr=0.0,
            cloud_cover_percentage=20.0,
            relative_humidity_percentage=55.0,
            flight_suitability="OPTIMAL",
            ground_trafficability_index=0.9,
        )


class MockRoutingProvider(RoutingProvider):
    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed

    async def calculate_route(self, origin, destination, route_type=RouteType.FASTEST_FEASIBLE, avoid_polygons=None):
        if not self.should_succeed:
            return None
        return RouteAssessment(
            route_id=str(uuid.uuid4()),
            route_type=route_type,
            status=RouteStatus.ACTIVE,
            origin=origin,
            destination=destination,
            total_distance_meters=5200.0,
            total_duration_seconds=480.0,
            elevation_gain_meters=15.0,
            hazards_avoided_count=len(avoid_polygons or []),
            road_segments=[],
            geometry_geojson={"type": "LineString", "coordinates": [[origin.longitude, origin.latitude], [destination.longitude, destination.latitude]]},
            routing_engine_name="MockEngine",
            engine_response_timestamp_utc=datetime.now(timezone.utc),
            evidence_ids=[str(uuid.uuid4())],
        )


class TestGeospatialProviders(unittest.IsolatedAsyncioTestCase):

    async def test_weather_provider_interface(self):
        provider = MockWeatherProvider()
        obs = await provider.get_weather(12.9716, 77.5946)
        self.assertIsNotNone(obs)
        self.assertEqual(obs.provider_name, "MockWeather")
        self.assertEqual(obs.flight_suitability, "OPTIMAL")

    async def test_shelter_registry(self):
        registry = InMemoryShelterRegistry()
        shelter = Shelter(
            shelter_id="SHELTER-001",
            name="Civic Center Safe Haven",
            geo_location=GeoPoint(latitude=12.9716, longitude=77.5946),
            status=ShelterStatus.OPEN,
            capacity_total=500,
            capacity_occupied=120,
            is_generator_powered=True,
            medical_support_available=True,
            last_reported_utc=datetime.now(timezone.utc),
            modality=Modality.OBSERVED,
            source_registry="District Disaster Authority",
        )
        registry.register_shelter(shelter)

        # Query near
        results = await registry.get_shelters_near(GeoPoint(latitude=12.9700, longitude=77.5900), radius_km=10.0)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].shelter_id, "SHELTER-001")

        # Query far away
        far_results = await registry.get_shelters_near(GeoPoint(latitude=15.0, longitude=75.0), radius_km=10.0)
        self.assertEqual(len(far_results), 0)

    async def test_evacuation_routing_success(self):
        registry = InMemoryShelterRegistry()
        shelter = Shelter(
            shelter_id="SHELTER-002",
            name="North Evacuation Point",
            geo_location=GeoPoint(latitude=13.0, longitude=77.6),
            status=ShelterStatus.OPEN,
            capacity_total=1000,
            capacity_occupied=200,
            is_generator_powered=True,
            medical_support_available=True,
            last_reported_utc=datetime.now(timezone.utc),
            modality=Modality.OBSERVED,
            source_registry="State Agency",
        )
        registry.register_shelter(shelter)

        engine = EvacuationRoutingEngine(
            routing_provider=MockRoutingProvider(should_succeed=True),
            shelter_registry=registry,
        )

        origin = GeoPoint(latitude=12.95, longitude=77.58)
        route = await engine.evaluate_evacuation(origin)
        self.assertIsNotNone(route)
        self.assertEqual(route.status, RouteStatus.ACTIVE)
        self.assertEqual(route.destination_shelter_id, "SHELTER-002")
        self.assertEqual(route.total_distance_meters, 5200.0)

    async def test_evacuation_routing_degraded_when_provider_unavailable(self):
        registry = InMemoryShelterRegistry()
        shelter = Shelter(
            shelter_id="SHELTER-003",
            name="East Relief Post",
            geo_location=GeoPoint(latitude=13.0, longitude=77.6),
            status=ShelterStatus.OPEN,
            capacity_total=300,
            capacity_occupied=50,
            is_generator_powered=False,
            medical_support_available=False,
            last_reported_utc=datetime.now(timezone.utc),
            modality=Modality.OBSERVED,
            source_registry="Red Cross",
        )
        registry.register_shelter(shelter)

        # Engine with no provider configured -> must return UNAVAILABLE status without fabricating routes
        engine = EvacuationRoutingEngine(
            routing_provider=None,
            shelter_registry=registry,
        )

        origin = GeoPoint(latitude=12.95, longitude=77.58)
        route = await engine.evaluate_evacuation(origin)
        self.assertIsNotNone(route)
        self.assertEqual(route.status, RouteStatus.UNAVAILABLE)
        self.assertIsNone(route.total_distance_meters)
        self.assertEqual(route.routing_engine_name, "None (Routing Unavailable)")

    async def test_openmeteo_and_openrouteservice_instantiation(self):
        # Verify providers can be instantiated cleanly without throwing
        weather = OpenMeteoWeatherProvider()
        self.assertEqual(weather.base_url, "https://api.open-meteo.com/v1")

        routing = OpenRouteServiceProvider(api_key=None)
        self.assertIsNone(routing.api_key)
        # Calling calculate_route without key returns None cleanly
        res = await routing.calculate_route(GeoPoint(latitude=10, longitude=10), GeoPoint(latitude=11, longitude=11))
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
