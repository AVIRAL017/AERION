"""
AERION — External Routing Service (Steps 22–23)
Integrates OpenRouteService (ORS) as primary road network provider and Mapbox Directions API as secondary fallback.
CRITICAL INVARIANTS:
1. Zero Straight-Line Routing: Routes must come strictly from real road-network graphs.
   Straight-line interpolation is strictly prohibited.
2. Missing Key Handling: If no valid provider key exists, returns AUTH_REQUIRED with route=None.
3. Explicit Failure States: If route calculation fails or endpoints are unreachable,
   returns explicit status (UNAVAILABLE, TIMEOUT, etc.) without guessing.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.core.cache import routing_cache
from app.core.config import get_settings
from app.schemas.evidence import (
    EvidenceRecord,
    EvidenceSourceType,
    GeoPoint,
    GeoPolygon,
    Modality,
    TemporalMode,
    VerificationState,
    utcnow,
)
from app.schemas.external import (
    NormalizedRouteRecord,
    NormalizedRouteStep,
    ProviderStatus,
    RouteProfile,
)

logger = logging.getLogger("aerion.external.routing")


class ExternalRoutingService:
    """
    Normalized road routing service connecting to OpenRouteService with Mapbox fallback.
    Adheres strictly to the road graph invariant: no straight lines allowed.
    """

    def __init__(
        self,
        ors_base_url: str = "https://api.heigit.org",
        mapbox_base_url: str = "https://api.mapbox.com/directions/v5",
        timeout_seconds: float = 12.0,
    ):
        self.ors_base_url = ors_base_url
        self.mapbox_base_url = mapbox_base_url
        self.timeout = timeout_seconds

    async def calculate_route(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        profile: RouteProfile = RouteProfile.DRIVING_CAR,
        avoid_polygons: Optional[List[GeoPolygon]] = None,
        use_cache: bool = True,
    ) -> NormalizedRouteRecord:
        """
        Calculates road network route between coordinates.
        Never fabricates straight-line trajectories.
        """
        origin = GeoPoint(latitude=origin_lat, longitude=origin_lon)
        destination = GeoPoint(latitude=dest_lat, longitude=dest_lon)

        # Coordinate bounds validation
        if not (-90.0 <= origin_lat <= 90.0 and -180.0 <= origin_lon <= 180.0 and
                -90.0 <= dest_lat <= 90.0 and -180.0 <= dest_lon <= 180.0):
            return NormalizedRouteRecord(
                route_id=str(uuid.uuid4()),
                provider_name="None",
                status=ProviderStatus.INVALID_REQUEST,
                origin=origin,
                destination=destination,
                profile=profile,
                fetched_at_utc=utcnow(),
                warnings=["Origin or destination coordinates violate WGS84 bounding range."],
            )

        settings = get_settings()
        ors_key = settings.OPENROUTESERVICE_API_KEY.get_secret_value() if settings.OPENROUTESERVICE_API_KEY else None
        mapbox_token = settings.MAPBOX_ACCESS_TOKEN.get_secret_value() if settings.MAPBOX_ACCESS_TOKEN else None

        # Check if any credentials exist
        if not ors_key and not mapbox_token:
            logger.info("Neither OpenRouteService API key nor Mapbox token configured.")
            return NormalizedRouteRecord(
                route_id=str(uuid.uuid4()),
                provider_name="None",
                status=ProviderStatus.AUTH_REQUIRED,
                origin=origin,
                destination=destination,
                profile=profile,
                fetched_at_utc=utcnow(),
                warnings=[
                    "Routing credentials (OPENROUTESERVICE_API_KEY or MAPBOX_ACCESS_TOKEN) are not configured.",
                    "AERION strictly prohibits straight-line pseudo-routing. Route assessment is unavailable without real network credentials."
                ],
            )

        # Cache check
        cache_key = f"route:{round(origin_lat, 4)}:{round(origin_lon, 4)}->{round(dest_lat, 4)}:{round(dest_lon, 4)}:{profile.value}:{len(avoid_polygons or [])}"
        if use_cache:
            cached_route = await routing_cache.get(cache_key)
            if cached_route:
                return cached_route.model_copy(update={"cached": True})

        # Try OpenRouteService primary
        if ors_key:
            res = await self._calculate_ors_route(origin, destination, profile, ors_key, avoid_polygons)
            if res.status == ProviderStatus.AVAILABLE:
                await routing_cache.set(cache_key, res)
                return res
            logger.warning(f"OpenRouteService failed with status {res.status}. Checking Mapbox fallback...")

        # Fallback to Mapbox if available
        if mapbox_token:
            res_mb = await self._calculate_mapbox_route(origin, destination, profile, mapbox_token)
            if res_mb.status == ProviderStatus.AVAILABLE:
                await routing_cache.set(cache_key, res_mb)
                return res_mb

        return NormalizedRouteRecord(
            route_id=str(uuid.uuid4()),
            provider_name="OpenRouteService/Mapbox",
            status=ProviderStatus.PROVIDER_ERROR,
            origin=origin,
            destination=destination,
            profile=profile,
            fetched_at_utc=utcnow(),
            warnings=[
                "External road routing providers failed or returned unroutable network trajectories.",
                "Zero straight-line fallback applied."
            ],
        )

    async def _calculate_ors_route(
        self,
        origin: GeoPoint,
        destination: GeoPoint,
        profile: RouteProfile,
        api_key: str,
        avoid_polygons: Optional[List[GeoPolygon]] = None,
    ) -> NormalizedRouteRecord:
        url = f"{self.ors_base_url}/v2/directions/driving-car/geojson"
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "coordinates": [
                [origin.longitude, origin.latitude],
                [destination.longitude, destination.latitude],
            ],
            "preference": "fastest",
            "elevation": True,
        }

        if avoid_polygons:
            poly_coords = [p.coordinates for p in avoid_polygons]
            payload["options"] = {
                "avoid_polygons": {
                    "type": "MultiPolygon",
                    "coordinates": poly_coords,
                }
            }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 401 or resp.status_code == 403:
                    return NormalizedRouteRecord(
                        route_id=str(uuid.uuid4()),
                        provider_name="OpenRouteService",
                        status=ProviderStatus.AUTH_REQUIRED,
                        origin=origin,
                        destination=destination,
                        profile=profile,
                        fetched_at_utc=utcnow(),
                        warnings=["OpenRouteService rejected the configured API key."],
                    )
                if resp.status_code == 429:
                    return NormalizedRouteRecord(
                        route_id=str(uuid.uuid4()),
                        provider_name="OpenRouteService",
                        status=ProviderStatus.RATE_LIMITED,
                        origin=origin,
                        destination=destination,
                        profile=profile,
                        fetched_at_utc=utcnow(),
                        warnings=["OpenRouteService rate limit exceeded."],
                    )
                if resp.status_code != 200:
                    return NormalizedRouteRecord(
                        route_id=str(uuid.uuid4()),
                        provider_name="OpenRouteService",
                        status=ProviderStatus.PROVIDER_ERROR,
                        origin=origin,
                        destination=destination,
                        profile=profile,
                        fetched_at_utc=utcnow(),
                        warnings=[f"OpenRouteService returned status {resp.status_code}: {resp.text}"],
                    )

                data = resp.json()
                features = data.get("features", [])
                if not features:
                    return NormalizedRouteRecord(
                        route_id=str(uuid.uuid4()),
                        provider_name="OpenRouteService",
                        status=ProviderStatus.UNAVAILABLE,
                        origin=origin,
                        destination=destination,
                        profile=profile,
                        fetched_at_utc=utcnow(),
                        warnings=["No navigable road network found between coordinates."],
                    )

                feature = features[0]
                geometry = feature.get("geometry", {})
                properties = feature.get("properties", {})
                summary = properties.get("summary", {})

                dist_m = summary.get("distance")
                dur_s = summary.get("duration")
                elevation = summary.get("ascent")

                # Parse route steps
                steps: List[NormalizedRouteStep] = []
                segments = properties.get("segments", [{}])
                if segments:
                    for idx, st in enumerate(segments[0].get("steps", [])):
                        steps.append(
                            NormalizedRouteStep(
                                step_index=idx,
                                instruction=st.get("instruction", ""),
                                name=st.get("name", f"Step {idx}"),
                                distance_meters=float(st.get("distance", 0.0)),
                                duration_seconds=float(st.get("duration", 0.0)),
                            )
                        )

                evidence_rec = EvidenceRecord(
                    evidence_id=str(uuid.uuid4()),
                    parent_evidence_ids=[],
                    source_type=EvidenceSourceType.GEOSPATIAL_REGISTRY,
                    created_at_utc=utcnow(),
                    temporal_mode=TemporalMode.STATIC_IMAGE,
                    crs="EPSG:4326",
                    geo_location=origin,
                    modality=Modality.EXTERNALLY_PROVIDED,
                    confidence=1.0,
                    verification_state=VerificationState.CALCULATED,
                    sensor_metadata={
                        "provider": "OpenRouteService",
                        "distance_meters": dist_m,
                        "duration_seconds": dur_s,
                        "elevation_gain_meters": elevation,
                    },
                )

                return NormalizedRouteRecord(
                    route_id=str(uuid.uuid4()),
                    provider_name="OpenRouteService",
                    status=ProviderStatus.AVAILABLE,
                    origin=origin,
                    destination=destination,
                    profile=profile,
                    total_distance_meters=float(dist_m) if dist_m is not None else None,
                    total_duration_seconds=float(dur_s) if dur_s is not None else None,
                    elevation_ascent_meters=float(elevation) if elevation is not None else None,
                    geometry_geojson=geometry,
                    steps=steps,
                    hazards_avoided_count=len(avoid_polygons or []),
                    fetched_at_utc=utcnow(),
                    warnings=[],
                    is_evacuation_evaluated=bool(avoid_polygons),
                    cached=False,
                    evidence=evidence_rec,
                )

        except httpx.TimeoutException:
            return NormalizedRouteRecord(
                route_id=str(uuid.uuid4()),
                provider_name="OpenRouteService",
                status=ProviderStatus.TIMEOUT,
                origin=origin,
                destination=destination,
                profile=profile,
                fetched_at_utc=utcnow(),
                warnings=[f"OpenRouteService timed out after {self.timeout}s."],
            )
        except Exception as e:
            return NormalizedRouteRecord(
                route_id=str(uuid.uuid4()),
                provider_name="OpenRouteService",
                status=ProviderStatus.PROVIDER_ERROR,
                origin=origin,
                destination=destination,
                profile=profile,
                fetched_at_utc=utcnow(),
                warnings=[f"OpenRouteService query error: {e}"],
            )

    async def _calculate_mapbox_route(
        self,
        origin: GeoPoint,
        destination: GeoPoint,
        profile: RouteProfile,
        access_token: str,
    ) -> NormalizedRouteRecord:
        url = f"{self.mapbox_base_url}/mapbox/driving/{origin.longitude},{origin.latitude};{destination.longitude},{destination.latitude}"
        params = {
            "access_token": access_token,
            "geometries": "geojson",
            "steps": "true",
            "overview": "full",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 401 or resp.status_code == 403:
                    return NormalizedRouteRecord(
                        route_id=str(uuid.uuid4()),
                        provider_name="Mapbox",
                        status=ProviderStatus.AUTH_REQUIRED,
                        origin=origin,
                        destination=destination,
                        profile=profile,
                        fetched_at_utc=utcnow(),
                        warnings=["Mapbox rejected the configured access token."],
                    )
                if resp.status_code != 200:
                    return NormalizedRouteRecord(
                        route_id=str(uuid.uuid4()),
                        provider_name="Mapbox",
                        status=ProviderStatus.PROVIDER_ERROR,
                        origin=origin,
                        destination=destination,
                        profile=profile,
                        fetched_at_utc=utcnow(),
                        warnings=[f"Mapbox returned HTTP {resp.status_code}: {resp.text}"],
                    )

                data = resp.json()
                routes = data.get("routes", [])
                if not routes:
                    return NormalizedRouteRecord(
                        route_id=str(uuid.uuid4()),
                        provider_name="Mapbox",
                        status=ProviderStatus.UNAVAILABLE,
                        origin=origin,
                        destination=destination,
                        profile=profile,
                        fetched_at_utc=utcnow(),
                        warnings=["No navigable route returned by Mapbox."],
                    )

                route0 = routes[0]
                dist_m = route0.get("distance")
                dur_s = route0.get("duration")
                geometry = route0.get("geometry", {})

                steps: List[NormalizedRouteStep] = []
                for idx, leg in enumerate(route0.get("legs", [])):
                    for s_idx, st in enumerate(leg.get("steps", [])):
                        steps.append(
                            NormalizedRouteStep(
                                step_index=s_idx,
                                instruction=st.get("maneuver", {}).get("instruction", ""),
                                name=st.get("name", f"Step {s_idx}"),
                                distance_meters=float(st.get("distance", 0.0)),
                                duration_seconds=float(st.get("duration", 0.0)),
                            )
                        )

                evidence_rec = EvidenceRecord(
                    evidence_id=str(uuid.uuid4()),
                    parent_evidence_ids=[],
                    source_type=EvidenceSourceType.GEOSPATIAL_REGISTRY,
                    created_at_utc=utcnow(),
                    temporal_mode=TemporalMode.STATIC_IMAGE,
                    crs="EPSG:4326",
                    geo_location=origin,
                    modality=Modality.EXTERNALLY_PROVIDED,
                    confidence=1.0,
                    verification_state=VerificationState.CALCULATED,
                    sensor_metadata={
                        "provider": "Mapbox",
                        "distance_meters": dist_m,
                        "duration_seconds": dur_s,
                    },
                )

                return NormalizedRouteRecord(
                    route_id=str(uuid.uuid4()),
                    provider_name="Mapbox",
                    status=ProviderStatus.AVAILABLE,
                    origin=origin,
                    destination=destination,
                    profile=profile,
                    total_distance_meters=float(dist_m) if dist_m is not None else None,
                    total_duration_seconds=float(dur_s) if dur_s is not None else None,
                    geometry_geojson=geometry,
                    steps=steps,
                    fetched_at_utc=utcnow(),
                    warnings=[],
                    cached=False,
                    evidence=evidence_rec,
                )

        except Exception as e:
            return NormalizedRouteRecord(
                route_id=str(uuid.uuid4()),
                provider_name="Mapbox",
                status=ProviderStatus.PROVIDER_ERROR,
                origin=origin,
                destination=destination,
                profile=profile,
                fetched_at_utc=utcnow(),
                warnings=[f"Mapbox query failed: {e}"],
            )
