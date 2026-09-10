"""
AERION — Geospatial API Endpoints (Step 17)
Exposes REST endpoints for administrative boundary resolution, historical hazard queries,
dataset provenance exploration, and international border contract status.
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_payload
from app.db.session import get_async_session
from app.schemas.geospatial import (
    AdminBoundaryResolution,
    BorderContractStatus,
    BorderSpatialQueryResponse,
    DatasetProvenanceContract,
    HistoricalHazardQueryResponse,
)
from app.services.geospatial_service import GeospatialService
from app.services.international_boundary_service import InternationalBoundaryService

router = APIRouter(prefix="/geospatial", tags=["Geospatial Data"])


def get_geospatial_service(session: AsyncSession = Depends(get_async_session)) -> GeospatialService:
    return GeospatialService(session)


def get_boundary_service(session: AsyncSession = Depends(get_async_session)) -> InternationalBoundaryService:
    return InternationalBoundaryService(session)


@router.get(
    "/datasets",
    response_model=List[DatasetProvenanceContract],
    summary="List all indexed geospatial datasets and provenance metadata",
)
async def list_geospatial_datasets(
    service: GeospatialService = Depends(get_geospatial_service),
    _user: dict = Depends(get_current_user_payload),
) -> List[DatasetProvenanceContract]:
    """Returns provenance metadata for all indexed datasets in AERION."""
    return await service.get_all_datasets()


@router.get(
    "/admin/resolve",
    response_model=AdminBoundaryResolution,
    summary="Resolve geographic point to administrative containment (Country -> State -> District)",
)
async def resolve_admin_boundary(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="WGS-84 latitude in decimal degrees"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="WGS-84 longitude in decimal degrees"),
    service: GeospatialService = Depends(get_geospatial_service),
    _user: dict = Depends(get_current_user_payload),
) -> AdminBoundaryResolution:
    """
    Performs PostGIS spatial containment query on administrative boundaries.
    Returns explicit available=False if coordinates fall outside indexed coverage.
    """
    return await service.resolve_admin_point(latitude=latitude, longitude=longitude)


@router.get(
    "/hazards/history",
    response_model=HistoricalHazardQueryResponse,
    summary="Query historical hazard inventory records within a spatial proximity radius",
)
async def query_historical_hazards(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="WGS-84 latitude"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="WGS-84 longitude"),
    radius_km: float = Query(25.0, ge=0.1, le=500.0, description="Search radius in kilometers"),
    service: GeospatialService = Depends(get_geospatial_service),
    _user: dict = Depends(get_current_user_payload),
) -> HistoricalHazardQueryResponse:
    """
    Returns historical flood polygons from PostGIS within proximity radius.
    Strict invariant: strictly reference/historical hazard evidence, never live operational status.
    """
    return await service.query_historical_hazards(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
    )


@router.get(
    "/border/status",
    response_model=BorderContractStatus,
    summary="Query operational status of international border vector demarcations",
)
async def get_border_status(
    service: InternationalBoundaryService = Depends(get_boundary_service),
    _user: dict = Depends(get_current_user_payload),
) -> BorderContractStatus:
    """
    Reports whether authoritative international boundary vector geometry is available.
    Zero fabrication: reports unavailable if authoritative boundary is absent.
    """
    return await service.get_border_contract_status()


@router.get(
    "/border/resolve",
    response_model=BorderSpatialQueryResponse,
    summary="Resolve point location relative to the authoritative international border",
)
async def resolve_border_location(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="WGS-84 latitude in decimal degrees"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="WGS-84 longitude in decimal degrees"),
    service: InternationalBoundaryService = Depends(get_boundary_service),
    _user: dict = Depends(get_current_user_payload),
) -> BorderSpatialQueryResponse:
    """
    Resolves coordinate containment and calculates exact geodesic distance in km
    against authoritative international boundary vector geometry.
    Zero fabrication: returns available=False if authoritative boundary is not loaded.
    """
    return await service.resolve_border_proximity(latitude=latitude, longitude=longitude)


# Mount Shelters sub-router under /geospatial/shelters
from app.api.shelters import router as shelters_router
router.include_router(shelters_router)
