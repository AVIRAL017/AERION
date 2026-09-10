"""
AERION — Building Footprint API Endpoints (Step 20)
Exposes REST endpoints for querying building footprints in Disaster Mode.

Endpoints:
- GET /api/v1/geospatial/buildings
- GET /api/v1/geospatial/buildings/{building_id}
- POST /api/v1/geospatial/buildings/intersect
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_payload
from app.db.session import get_async_session
from app.schemas.building import BuildingQueryResponse, BuildingRecord
from app.services.building_service import BuildingService

router = APIRouter(prefix="/buildings", tags=["Building Footprints"])


def get_building_service(session: AsyncSession = Depends(get_async_session)) -> BuildingService:
    return BuildingService(session)


@router.get(
    "",
    response_model=BuildingQueryResponse,
    summary="Query building footprints within proximity radius of coordinates",
)
async def query_buildings_proximity(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="WGS-84 latitude in decimal degrees"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="WGS-84 longitude in decimal degrees"),
    radius_km: float = Query(0.5, ge=0.05, le=10.0, description="Search radius in kilometers (max 10.0)"),
    limit: int = Query(100, ge=1, le=500, description="Maximum building records to return"),
    service: BuildingService = Depends(get_building_service),
    _user: dict = Depends(get_current_user_payload),
) -> BuildingQueryResponse:
    """
    Finds building footprints within radius_km of coordinates using PostGIS geography ST_DWithin.
    Strict invariant: building footprints represent externally sourced geometry and do not establish
    occupancy, structural safety, or damage.
    """
    return await service.query_buildings_proximity(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        limit=limit,
    )


@router.get(
    "/{building_id}",
    response_model=BuildingRecord,
    summary="Retrieve an individual building footprint record by ID",
)
async def get_building_by_id(
    building_id: str,
    service: BuildingService = Depends(get_building_service),
    _user: dict = Depends(get_current_user_payload),
) -> BuildingRecord:
    """
    Retrieves building footprint details, dimensions, and GeoJSON geometry.
    """
    building = await service.get_building_by_id(building_id)
    if not building:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Building record '{building_id}' not found in registry.",
        )
    return building


@router.post(
    "/intersect",
    response_model=BuildingQueryResponse,
    summary="Find building footprints intersecting an incident or hazard polygon",
)
async def query_buildings_intersection(
    polygon_geojson: Dict[str, Any],
    limit: int = Query(100, ge=1, le=500, description="Maximum building records to return"),
    service: BuildingService = Depends(get_building_service),
    _user: dict = Depends(get_current_user_payload),
) -> BuildingQueryResponse:
    """
    Computes spatial intersection between a supplied incident polygon (GeoJSON)
    and building footprints in PostGIS (ST_Intersects).
    """
    return await service.query_buildings_polygon_intersection(
        polygon_geojson=polygon_geojson,
        limit=limit,
    )
