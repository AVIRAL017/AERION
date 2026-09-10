"""
AERION — Shelter API Endpoints (Step 18)
Exposes REST endpoints for querying shelter and evacuation points in Disaster Mode.

Endpoints:
- GET /api/v1/geospatial/shelters
- GET /api/v1/geospatial/shelters/nearby
- GET /api/v1/geospatial/shelters/{shelter_id}
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_payload
from app.db.session import get_async_session
from app.schemas.shelter import ShelterQueryResponse, ShelterRecord
from app.services.shelter_service import ShelterService

router = APIRouter(prefix="/shelters", tags=["Shelters & Evacuation Points"])


def get_shelter_service(session: AsyncSession = Depends(get_async_session)) -> ShelterService:
    return ShelterService(session)


@router.get(
    "",
    response_model=ShelterQueryResponse,
    summary="Query shelters with optional spatial proximity and classification filters",
)
async def list_shelters(
    latitude: Optional[float] = Query(None, ge=-90.0, le=90.0, description="WGS-84 latitude"),
    longitude: Optional[float] = Query(None, ge=-180.0, le=180.0, description="WGS-84 longitude"),
    radius_km: Optional[float] = Query(None, ge=0.1, le=500.0, description="Proximity radius in kilometers"),
    shelter_type: Optional[str] = Query(None, description="Filter by shelter classification"),
    operational_status: Optional[str] = Query(None, description="Filter by operational status"),
    state_code: Optional[str] = Query(None, description="Filter by ADM1 state code"),
    district_code: Optional[str] = Query(None, description="Filter by ADM2 district code"),
    limit: int = Query(50, ge=1, le=200, description="Maximum records to return"),
    service: ShelterService = Depends(get_shelter_service),
    _user: dict = Depends(get_current_user_payload),
) -> ShelterQueryResponse:
    """
    Queries shelter facilities from PostGIS. If coordinates are provided, computes
    true geodesic distance using PostGIS geography functions and orders by nearest facility.
    """
    return await service.query_shelters(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        shelter_type=shelter_type,
        operational_status=operational_status,
        state_code=state_code,
        district_code=district_code,
        limit=limit,
    )


@router.get(
    "/nearby",
    response_model=ShelterQueryResponse,
    summary="Find shelters near a geographic coordinate anchor",
)
async def find_nearby_shelters(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="WGS-84 latitude"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="WGS-84 longitude"),
    radius_km: float = Query(25.0, ge=0.1, le=200.0, description="Search radius in kilometers"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    service: ShelterService = Depends(get_shelter_service),
    _user: dict = Depends(get_current_user_payload),
) -> ShelterQueryResponse:
    """
    Convenience endpoint for locating shelters in proximity to an operational incident coordinate.
    """
    return await service.query_shelters(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        limit=limit,
    )


@router.get(
    "/{shelter_id}",
    response_model=ShelterRecord,
    summary="Get detailed record and provenance for a specific shelter",
)
async def get_shelter_detail(
    shelter_id: str,
    service: ShelterService = Depends(get_shelter_service),
    _user: dict = Depends(get_current_user_payload),
) -> ShelterRecord:
    """
    Retrieves full verified details for a single shelter facility.
    """
    record = await service.get_shelter_by_id(shelter_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shelter with ID '{shelter_id}' not found in registry.",
        )
    return record
