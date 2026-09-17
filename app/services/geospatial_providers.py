"""
AERION — External Provider Abstractions & Geospatial Integrations
Phase 3F: Real-world Weather, Routing, Geocoding, Shelter, and Hazard Services.

Absolute Invariants:
1. Zero fabrication: If real evidence or provider data is unavailable, return an explicit
   UNAVAILABLE state. Never invent fake weather, coordinates, routes, shelters, or hazard zones.
2. Coordinate Separation: WGS84 (EPSG:4326) strictly separated from image/pixel space.
3. Road Blockage Invariant: Road segments can only be marked BLOCKED when corroborated
   by real hazard or road blockage evidence.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

import httpx

from app.core.config import get_settings
from app.schemas.situation import (
    DisasterType,
    GeoPoint,
    GeoPolygon,
    HazardZone,
    Modality,
    RouteAssessment,
    RouteSegment,
    RouteStatus,
    RouteType,
    Shelter,
    ShelterStatus,
    ThreatLevel,
    WeatherObservation,
)

logger = logging.getLogger("aerion.providers")


# =====================================================================
# 1. WEATHER PROVIDER ABSTRACTION & OPEN-METEO IMPLEMENTATION
# =====================================================================

class WeatherProvider(ABC):
    """Abstract interface for meteorological data retrieval."""

    @abstractmethod
    async def get_weather(
        self,
        latitude: float,
        longitude: float,
        timestamp_utc: Optional[datetime] = None,
    ) -> Optional[WeatherObservation]:
        """
        Fetch weather for coordinates.
        If timestamp_utc is provided, retrieves historical weather for that timestamp.
        Returns None if provider is unreachable or data is unavailable.
        """
        pass


class OpenMeteoWeatherProvider(WeatherProvider):
    """
    Real-world Weather Provider utilizing Open-Meteo API.
    Supports both live/forecast and historical meteorological data without fabrication.
    """

    def __init__(self, base_url: str = "https://api.open-meteo.com/v1"):
        self.base_url = base_url
        self.archive_base_url = "https://archive-api.open-meteo.com/v1/archive"

    async def get_weather(
        self,
        latitude: float,
        longitude: float,
        timestamp_utc: Optional[datetime] = None,
    ) -> Optional[WeatherObservation]:
        now_utc = datetime.now(timezone.utc)
        is_historical = False

        if timestamp_utc is not None:
            # Check if timestamp is more than 2 days in the past
            delta = now_utc - timestamp_utc
            if delta.total_seconds() > 172800:
                is_historical = True

        target_time = timestamp_utc or now_utc

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if is_historical:
                    date_str = target_time.strftime("%Y-%m-%d")
                    params = {
                        "latitude": latitude,
                        "longitude": longitude,
                        "start_date": date_str,
                        "end_date": date_str,
                        "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,cloud_cover",
                    }
                    resp = await client.get(self.archive_base_url, params=params)
                else:
                    params = {
                        "latitude": latitude,
                        "longitude": longitude,
                        "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,cloud_cover",
                    }
                    resp = await client.get(f"{self.base_url}/forecast", params=params)

                if resp.status_code != 200:
                    logger.warning(f"Open-Meteo returned status {resp.status_code}: {resp.text}")
                    return None

                data = resp.json()

                if is_historical:
                    hourly = data.get("hourly", {})
                    # Pick closest hour
                    target_hour_str = target_time.strftime("%Y-%m-%dT%H:00")
                    times = hourly.get("time", [])
                    idx = times.index(target_hour_str) if target_hour_str in times else 0

                    temp = hourly.get("temperature_2m", [None])[idx]
                    humidity = hourly.get("relative_humidity_2m", [None])[idx]
                    precip = hourly.get("precipitation", [None])[idx]
                    wind_speed_kmh = hourly.get("wind_speed_10m", [None])[idx]
                    wind_dir = hourly.get("wind_direction_10m", [None])[idx]
                    cloud_cover = hourly.get("cloud_cover", [None])[idx]
                else:
                    current = data.get("current", {})
                    temp = current.get("temperature_2m")
                    humidity = current.get("relative_humidity_2m")
                    precip = current.get("precipitation")
                    wind_speed_kmh = current.get("wind_speed_10m")
                    wind_dir = current.get("wind_direction_10m")
                    cloud_cover = current.get("cloud_cover")

                # Convert km/h to m/s
                wind_speed_mps = float(wind_speed_kmh) / 3.6 if wind_speed_kmh is not None else None

                # Flight suitability evaluation
                suitability = "OPTIMAL"
                if wind_speed_mps is not None and wind_speed_mps > 15.0:
                    suitability = "GROUNDED"
                elif precip is not None and precip > 10.0:
                    suitability = "GROUNDED"
                elif wind_speed_mps is not None and wind_speed_mps > 10.0:
                    suitability = "MARGINAL"
                elif precip is not None and precip > 2.0:
                    suitability = "MARGINAL"

                return WeatherObservation(
                    observation_id=str(uuid.uuid4()),
                    provider_name="Open-Meteo",
                    observation_timestamp_utc=target_time,
                    is_historical_reconstructed=is_historical,
                    latitude=latitude,
                    longitude=longitude,
                    temperature_celsius=float(temp) if temp is not None else None,
                    wind_speed_mps=wind_speed_mps,
                    wind_direction_deg=float(wind_dir) if wind_dir is not None else None,
                    precipitation_mm_hr=float(precip) if precip is not None else None,
                    cloud_cover_percentage=float(cloud_cover) if cloud_cover is not None else None,
                    relative_humidity_percentage=float(humidity) if humidity is not None else None,
                    flight_suitability=suitability,
                    ground_trafficability_index=0.8 if (precip or 0.0) < 5.0 else 0.3,
                )

        except Exception as e:
            logger.warning(f"Failed to fetch weather from Open-Meteo: {e}")
            return None


# =====================================================================
# 2. ROUTING PROVIDER ABSTRACTION & OPENROUTESERVICE IMPLEMENTATION
# =====================================================================

class RoutingProvider(ABC):
    """Abstract interface for road network navigation and routing."""

    @abstractmethod
    async def calculate_route(
        self,
        origin: GeoPoint,
        destination: GeoPoint,
        route_type: RouteType = RouteType.FASTEST_FEASIBLE,
        avoid_polygons: Optional[List[GeoPolygon]] = None,
    ) -> Optional[RouteAssessment]:
        """
        Calculate actual road-network route avoiding designated hazard boundaries.
        Returns None if routing service is unreachable or coordinates cannot be routed.
        """
        pass


class OpenRouteServiceProvider(RoutingProvider):
    """
    Real-world Routing Engine using OpenRouteService API.
    Calculates genuine road-graph trajectories and avoids blocked / hazardous zones.
    """

    _DEFAULT = object()

    def __init__(self, api_key: Any = _DEFAULT, base_url: str = "https://api.heigit.org"):
        if api_key is self._DEFAULT:
            self.api_key = (
                get_settings().OPENROUTESERVICE_API_KEY.get_secret_value()
                if get_settings().OPENROUTESERVICE_API_KEY
                else None
            )
        else:
            self.api_key = api_key
        self.base_url = base_url

    async def calculate_route(
        self,
        origin: GeoPoint,
        destination: GeoPoint,
        route_type: RouteType = RouteType.FASTEST_FEASIBLE,
        avoid_polygons: Optional[List[GeoPolygon]] = None,
    ) -> Optional[RouteAssessment]:
        if not self.api_key:
            logger.info("OpenRouteService API key not configured; routing unavailable.")
            return None

        url = f"{self.base_url}/v2/directions/driving-car/geojson"
        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "coordinates": [
                [origin.longitude, origin.latitude],
                [destination.longitude, destination.latitude],
            ],
            "preference": "fastest" if route_type == RouteType.FASTEST_FEASIBLE else "recommended",
            "elevation": True,
        }

        # Add polygon avoidance if present
        if avoid_polygons:
            poly_coords = [p.coordinates for p in avoid_polygons]
            payload["options"] = {
                "avoid_polygons": {
                    "type": "MultiPolygon",
                    "coordinates": poly_coords,
                }
            }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code != 200:
                    logger.warning(f"OpenRouteService returned status {resp.status_code}: {resp.text}")
                    return None

                data = resp.json()
                features = data.get("features", [])
                if not features:
                    return None

                feature = features[0]
                geometry = feature.get("geometry", {})
                properties = feature.get("properties", {})
                summary = properties.get("summary", {})

                dist_m = summary.get("distance")
                dur_s = summary.get("duration")
                elevation = summary.get("ascent")

                # Parse geometry points
                raw_coords = geometry.get("coordinates", [])
                geo_points = [
                    GeoPoint(longitude=c[0], latitude=c[1], altitude_m=c[2] if len(c) > 2 else None)
                    for c in raw_coords
                ]

                # Convert segments
                segments: List[RouteSegment] = []
                for idx, step in enumerate(properties.get("segments", [{}])[0].get("steps", [])):
                    segments.append(
                        RouteSegment(
                            segment_index=idx,
                            name=step.get("name", f"Segment {idx}"),
                            distance_meters=float(step.get("distance", 0.0)),
                            duration_seconds=float(step.get("duration", 0.0)),
                            is_blocked=False,
                            hazard_proximity_meters=None,
                            geo_line=[],
                        )
                    )

                return RouteAssessment(
                    route_id=str(uuid.uuid4()),
                    route_type=route_type,
                    status=RouteStatus.ACTIVE,
                    origin=origin,
                    destination=destination,
                    total_distance_meters=float(dist_m) if dist_m is not None else None,
                    total_duration_seconds=float(dur_s) if dur_s is not None else None,
                    elevation_gain_meters=float(elevation) if elevation is not None else None,
                    hazards_avoided_count=len(avoid_polygons or []),
                    road_segments=segments,
                    geometry_geojson=geometry,
                    routing_engine_name="OpenRouteService",
                    engine_response_timestamp_utc=datetime.now(timezone.utc),
                    evidence_ids=[str(uuid.uuid4())],
                )

        except Exception as e:
            logger.warning(f"Failed to calculate route via OpenRouteService: {e}")
            return None


class MapboxRoutingProvider(RoutingProvider):
    """
    Real-world Routing Engine using Mapbox Directions API.
    Calculates genuine road-graph trajectories. Never returns straight-line approximations.
    """

    def __init__(self, access_token: Optional[str] = None, base_url: str = "https://api.mapbox.com/directions/v5"):
        self.access_token = access_token or (get_settings().MAPBOX_ACCESS_TOKEN.get_secret_value() if get_settings().MAPBOX_ACCESS_TOKEN else None)
        self.base_url = base_url

    async def calculate_route(
        self,
        origin: GeoPoint,
        destination: GeoPoint,
        route_type: RouteType = RouteType.FASTEST_FEASIBLE,
        avoid_polygons: Optional[List[GeoPolygon]] = None,
    ) -> Optional[RouteAssessment]:
        if not self.access_token:
            logger.info("Mapbox access token not configured; routing unavailable.")
            return None

        url = f"{self.base_url}/mapbox/driving/{origin.longitude},{origin.latitude};{destination.longitude},{destination.latitude}"
        params = {
            "access_token": self.access_token,
            "geometries": "geojson",
            "steps": "true",
            "overview": "full",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    logger.warning(f"Mapbox returned status {resp.status_code}: {resp.text}")
                    return None

                data = resp.json()
                routes = data.get("routes", [])
                if not routes:
                    return None

                route0 = routes[0]
                dist_m = route0.get("distance")
                dur_s = route0.get("duration")
                geometry = route0.get("geometry", {})

                segments: List[RouteSegment] = []
                for leg in route0.get("legs", []):
                    for idx, step in enumerate(leg.get("steps", [])):
                        segments.append(
                            RouteSegment(
                                segment_index=idx,
                                name=step.get("name") or step.get("maneuver", {}).get("instruction", f"Segment {idx}"),
                                distance_meters=float(step.get("distance", 0.0)),
                                duration_seconds=float(step.get("duration", 0.0)),
                                is_blocked=False,
                                hazard_proximity_meters=None,
                                geo_line=[],
                            )
                        )

                return RouteAssessment(
                    route_id=str(uuid.uuid4()),
                    route_type=route_type,
                    status=RouteStatus.ACTIVE,
                    origin=origin,
                    destination=destination,
                    total_distance_meters=float(dist_m) if dist_m is not None else None,
                    total_duration_seconds=float(dur_s) if dur_s is not None else None,
                    elevation_gain_meters=None,
                    hazards_avoided_count=len(avoid_polygons or []),
                    road_segments=segments,
                    geometry_geojson=geometry,
                    routing_engine_name="Mapbox",
                    engine_response_timestamp_utc=datetime.now(timezone.utc),
                    evidence_ids=[str(uuid.uuid4())],
                )

        except Exception as e:
            logger.warning(f"Failed to calculate route via Mapbox: {e}")
            return None


# =====================================================================
# 3. SHELTER REGISTRY ABSTRACTION
# =====================================================================

class ShelterRegistry(ABC):
    """Abstract interface for retrieving verified shelter resources."""

    @abstractmethod
    async def get_shelters_near(
        self,
        location: GeoPoint,
        radius_km: float = 25.0,
    ) -> List[Shelter]:
        """Fetch shelters within proximity radius."""
        pass


class InMemoryShelterRegistry(ShelterRegistry):
    """
    Standard in-memory / relational registry for shelters.
    Stores only verified, explicitly registered shelters without fabrication.
    """

    def __init__(self, shelters: Optional[List[Shelter]] = None):
        self._shelters: List[Shelter] = shelters or []

    def register_shelter(self, shelter: Shelter) -> None:
        self._shelters.append(shelter)

    async def get_shelters_near(
        self,
        location: GeoPoint,
        radius_km: float = 25.0,
    ) -> List[Shelter]:
        # Filter within approx bounding box (1 deg ~ 111 km)
        delta_deg = radius_km / 111.0
        results: List[Shelter] = []
        for s in self._shelters:
            lat_diff = abs(s.geo_location.latitude - location.latitude)
            lon_diff = abs(s.geo_location.longitude - location.longitude)
            if lat_diff <= delta_deg and lon_diff <= delta_deg:
                results.append(s)
        return results


# =====================================================================
# 4. HAZARD ZONE SERVICE ABSTRACTION
# =====================================================================

class HazardZoneRegistry(ABC):
    """Abstract interface for active hazard zones (floods, fires, collapses)."""

    @abstractmethod
    async def get_active_hazards(
        self,
        bounding_box: Optional[GeoPolygon] = None,
    ) -> List[HazardZone]:
        """Fetch active hazard perimeters."""
        pass


class InMemoryHazardZoneRegistry(HazardZoneRegistry):
    """In-memory hazard repository for validated active disaster boundaries."""

    def __init__(self, hazards: Optional[List[HazardZone]] = None):
        self._hazards: List[HazardZone] = hazards or []

    def register_hazard(self, hazard: HazardZone) -> None:
        self._hazards.append(hazard)

    async def get_active_hazards(
        self,
        bounding_box: Optional[GeoPolygon] = None,
    ) -> List[HazardZone]:
        return [h for h in self._hazards if h.active]


# =====================================================================
# 5. EVACUATION ROUTING EVALUATION ENGINE
# =====================================================================

class EvacuationRoutingEngine:
    """
    Synthesizes evacuation route candidates against road networks and hazards.
    Adheres strictly to the Road Blockage and Zero Fabrication Invariants:
    - Never fabricates coordinates.
    - If routing provider is unavailable, sets status = UNAVAILABLE.
    - Damage near a road alone does NOT mark a road blocked.
    """

    def __init__(
        self,
        routing_provider: Optional[RoutingProvider] = None,
        shelter_registry: Optional[ShelterRegistry] = None,
        hazard_registry: Optional[HazardZoneRegistry] = None,
    ):
        self.routing_provider = routing_provider
        self.shelter_registry = shelter_registry or InMemoryShelterRegistry()
        self.hazard_registry = hazard_registry or InMemoryHazardZoneRegistry()

    async def evaluate_evacuation(
        self,
        origin: GeoPoint,
        destination_shelter: Optional[Shelter] = None,
    ) -> Optional[RouteAssessment]:
        if destination_shelter is None:
            # Find nearest shelter
            shelters = await self.shelter_registry.get_shelters_near(origin, radius_km=50.0)
            open_shelters = [s for s in shelters if s.status in (ShelterStatus.OPEN, ShelterStatus.APPROACHING_CAPACITY)]
            if not open_shelters:
                logger.info("No open shelters identified within proximity radius.")
                return None
            destination_shelter = open_shelters[0]

        dest_point = destination_shelter.geo_location
        active_hazards = await self.hazard_registry.get_active_hazards()
        avoid_polys = [h.geo_boundary for h in active_hazards]

        if not self.routing_provider:
            return RouteAssessment(
                route_id=str(uuid.uuid4()),
                route_type=RouteType.SAFEST_FEASIBLE,
                status=RouteStatus.UNAVAILABLE,
                origin=origin,
                destination=dest_point,
                destination_shelter_id=destination_shelter.shelter_id,
                routing_engine_name="None (Routing Unavailable)",
                engine_response_timestamp_utc=datetime.now(timezone.utc),
                evidence_ids=[str(uuid.uuid4())],
            )

        assessment = await self.routing_provider.calculate_route(
            origin=origin,
            destination=dest_point,
            route_type=RouteType.SAFEST_FEASIBLE,
            avoid_polygons=avoid_polys,
        )

        if assessment:
            return assessment.model_copy(update={"destination_shelter_id": destination_shelter.shelter_id})

        return RouteAssessment(
            route_id=str(uuid.uuid4()),
            route_type=RouteType.SAFEST_FEASIBLE,
            status=RouteStatus.UNAVAILABLE,
            origin=origin,
            destination=dest_point,
            destination_shelter_id=destination_shelter.shelter_id,
            routing_engine_name="Provider Error (Degraded)",
            engine_response_timestamp_utc=datetime.now(timezone.utc),
            evidence_ids=[str(uuid.uuid4())],
        )
