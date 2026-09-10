"""
AERION — Critical Infrastructure API Endpoints (Step 20)
Exposes REST endpoints for querying critical infrastructure facilities in Disaster Mode.

Endpoints:
- GET /api/v1/geospatial/infrastructure
- GET /api/v1/geospatial/infrastructure/{infrastructure_id}
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_payload
from app.db.session import get_async_session
from app.schemas.infrastructure import (
    CriticalInfrastructureRecord,
    InfrastructureQueryResponse,
)
from app.services.infrastructure_service import InfrastructureService

router = APIRouter(prefix="/infrastructure", tags=["Critical Infrastructure"])


def get_infra_service(session: AsyncSession = Depends(get_async_session)) -> InfrastructureService:
    return InfrastructureService(session)


@router.get(
    "",
    response_model=InfrastructureQueryResponse,
    summary="Query critical infrastructure facilities near coordinates with optional classification filters",
)
async def query_infrastructure_proximity(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="WGS-84 latitude in decimal degrees"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="WGS-84 longitude in decimal degrees"),
    radius_km: float = Query(5.0, ge=0.1, le=50.0, description="Search radius in kilometers (max 50.0)"),
    infrastructure_type: Optional[str] = Query(None, description="Filter by facility type (e.g. HOSPITAL, FIRE_STATION, POLICE_STATION, SCHOOL)"),
    state_code: Optional[str] = Query(None, description="Filter by ADM1 state code"),
    district_code: Optional[str] = Query(None, description="Filter by ADM2 district code"),
    limit: int = Query(50, ge=1, le=200, description="Maximum facilities to return"),
    service: InfrastructureService = Depends(get_infra_service),
    _user: dict = Depends(get_current_user_payload),
) -> InfrastructureQueryResponse:
    """
    Finds critical infrastructure facilities within radius_km of coordinates.
    Computes true geodesic distance via PostGIS geography functions.
    Strict invariant: operational_status is strictly UNKNOWN unless source provides explicit status.
    """
    return await service.query_infrastructure_proximity(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        infrastructure_type=infrastructure_type,
        state_code=state_code,
        district_code=district_code,
        limit=limit,
    )


@router.get(
    "/{infrastructure_id}",
    response_model=CriticalInfrastructureRecord,
    summary="Retrieve an individual critical infrastructure facility record by ID",
)
async def get_infrastructure_by_id(
    infrastructure_id: str,
    service: InfrastructureService = Depends(get_infra_service),
    _user: dict = Depends(get_current_user_payload),
) -> CriticalInfrastructureRecord:
    """
    Retrieves critical infrastructure facility details, enriched administrative attributes, and GeoJSON.
    """
    facility = await service.get_infrastructure_by_id(infrastructure_id)
    if not facility:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Infrastructure record '{infrastructure_id}' not found in registry.",
        )
    return facility
