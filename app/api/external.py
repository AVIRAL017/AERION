"""
AERION — External Provider REST Endpoints (Steps 22–23)
Exposes normalized endpoints for Weather, Routing, Forward Geocoding, and Reverse Geocoding.
Conforms strictly to AERION zero-fabrication and coordinate safety rules.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import get_current_user_payload
from app.core.config import get_settings
from app.schemas.common import MetaBlock, ResponseEnvelope, utc_now_iso
from app.schemas.external import (
    NormalizedGeocodeResult,
    NormalizedRouteRecord,
    NormalizedWeatherRecord,
    RouteProfile,
)
from app.services.external_geocoding_service import ExternalGeocodingService
from app.services.external_routing_service import ExternalRoutingService
from app.services.external_weather_service import ExternalWeatherService

router = APIRouter(prefix="/external", tags=["External APIs (Weather, Routing, Geocoding)"])


def get_weather_service() -> ExternalWeatherService:
    return ExternalWeatherService()


def get_routing_service() -> ExternalRoutingService:
    return ExternalRoutingService()


def get_geocoding_service() -> ExternalGeocodingService:
    return ExternalGeocodingService()


def _extract_request_id(request: Request) -> str:
    if hasattr(request, "state") and hasattr(request.state, "request_id"):
        return request.state.request_id
    settings = get_settings()
    return request.headers.get(settings.REQUEST_ID_HEADER, "req-external-default")


@router.get(
    "/weather",
    response_model=ResponseEnvelope[NormalizedWeatherRecord],
    status_code=status.HTTP_200_OK,
    summary="Get normalized weather conditions and flight suitability for coordinates",
)
async def get_weather(
    request: Request,
    latitude: float = Query(..., ge=-90.0, le=90.0, description="WGS84 latitude"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="WGS84 longitude"),
    timestamp_utc: Optional[datetime] = Query(default=None, description="Optional UTC timestamp for historical meteorological reconstruction"),
    service: ExternalWeatherService = Depends(get_weather_service),
    _user: dict = Depends(get_current_user_payload),
) -> ResponseEnvelope[NormalizedWeatherRecord]:
    """
    Returns normalized weather data from Open-Meteo.
    Zero-fabrication: unavailable metrics remain None.
    """
    record = await service.get_weather(
        latitude=latitude,
        longitude=longitude,
        timestamp_utc=timestamp_utc,
    )
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=get_settings().API_VERSION,
    )
    return ResponseEnvelope(success=True, data=record, meta=meta)


@router.get(
    "/route",
    response_model=ResponseEnvelope[NormalizedRouteRecord],
    status_code=status.HTTP_200_OK,
    summary="Calculate road network trajectory between two geographic points",
)
async def calculate_route(
    request: Request,
    origin_lat: float = Query(..., ge=-90.0, le=90.0, description="Origin WGS84 latitude"),
    origin_lon: float = Query(..., ge=-180.0, le=180.0, description="Origin WGS84 longitude"),
    dest_lat: float = Query(..., ge=-90.0, le=90.0, description="Destination WGS84 latitude"),
    dest_lon: float = Query(..., ge=-180.0, le=180.0, description="Destination WGS84 longitude"),
    profile: RouteProfile = Query(default=RouteProfile.DRIVING_CAR, description="Routing mode profile"),
    service: ExternalRoutingService = Depends(get_routing_service),
    _user: dict = Depends(get_current_user_payload),
) -> ResponseEnvelope[NormalizedRouteRecord]:
    """
    Calculates actual road-graph route via OpenRouteService / Mapbox.
    STRICT INVARIANT: Zero straight-line routing.
    """
    route_record = await service.calculate_route(
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        profile=profile,
    )
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=get_settings().API_VERSION,
    )
    return ResponseEnvelope(success=True, data=route_record, meta=meta)


@router.get(
    "/geocode",
    response_model=ResponseEnvelope[List[NormalizedGeocodeResult]],
    status_code=status.HTTP_200_OK,
    summary="Forward geocode a text query to geographic coordinates",
)
async def forward_geocode(
    request: Request,
    query: str = Query(..., min_length=1, max_length=200, description="Location name or address query"),
    limit: int = Query(default=1, ge=1, le=5, description="Maximum number of candidates"),
    service: ExternalGeocodingService = Depends(get_geocoding_service),
    _user: dict = Depends(get_current_user_payload),
) -> ResponseEnvelope[List[NormalizedGeocodeResult]]:
    """
    Forward geocode place query into WGS84 coordinates and administrative context.
    """
    results = await service.forward_geocode(query=query, limit=limit)
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=get_settings().API_VERSION,
    )
    return ResponseEnvelope(success=True, data=results, meta=meta)


@router.get(
    "/reverse-geocode",
    response_model=ResponseEnvelope[Optional[NormalizedGeocodeResult]],
    status_code=status.HTTP_200_OK,
    summary="Reverse geocode geographic coordinates to place metadata",
)
async def reverse_geocode(
    request: Request,
    latitude: float = Query(..., ge=-90.0, le=90.0, description="WGS84 latitude"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="WGS84 longitude"),
    service: ExternalGeocodingService = Depends(get_geocoding_service),
    _user: dict = Depends(get_current_user_payload),
) -> ResponseEnvelope[Optional[NormalizedGeocodeResult]]:
    """
    Reverse geocode coordinates into human-readable place description and administrative hierarchy.
    """
    result = await service.reverse_geocode(latitude=latitude, longitude=longitude)
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=get_settings().API_VERSION,
    )
    return ResponseEnvelope(success=True, data=result, meta=meta)
