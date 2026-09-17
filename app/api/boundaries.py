"""
AERION — Boundary Endpoints & Demo Pentagon Evaluation API (Phase D)
Provides:
- GET /api/v1/boundaries: Lists registered boundaries (Demo Pentagon, etc.)
- GET /api/v1/boundaries/{boundary_id}: Gets specific boundary metadata & GeoJSON
- POST /api/v1/boundaries/{boundary_id}/evaluate: Evaluates spatial intersection
  with actual analysis evidence.
  If no evidence intersects: returns INSUFFICIENT_EVIDENCE.
  If legitimate evidence intersects: computes grounded vulnerability score.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from shapely.geometry import Point, Polygon, shape

from app.api.deps import get_current_user_payload
from app.core.config import get_settings
from app.core.errors import ResourceNotFoundError
from app.core.jobs import default_job_manager
from app.schemas.boundary import (
    DEMO_PENTAGON_BOUNDARY,
    BoundaryDefinition,
    BoundaryEvaluationRequest,
    BoundaryEvaluationResponse,
)
from app.schemas.common import MetaBlock, ResponseEnvelope, utc_now_iso

logger = logging.getLogger("aerion.api.boundaries")

router = APIRouter(prefix="/boundaries", tags=["Boundaries (Demo & Operational)"])

REGISTERED_BOUNDARIES: Dict[str, BoundaryDefinition] = {
    DEMO_PENTAGON_BOUNDARY.id: DEMO_PENTAGON_BOUNDARY,
    "DEMO_VULNERABILITY_BOUNDARY": DEMO_PENTAGON_BOUNDARY,
}


def _extract_request_id(request: Request) -> str:
    if hasattr(request, "state") and hasattr(request.state, "request_id"):
        return request.state.request_id
    return request.headers.get("X-Request-ID", f"req-{uuid.uuid4().hex[:8]}")


@router.get(
    "",
    response_model=ResponseEnvelope[List[BoundaryDefinition]],
    status_code=status.HTTP_200_OK,
    summary="List available boundary definitions",
)
async def list_boundaries(
    request: Request,
    payload: dict = Depends(get_current_user_payload),
) -> ResponseEnvelope[List[BoundaryDefinition]]:
    settings = get_settings()
    boundaries = list(REGISTERED_BOUNDARIES.values())
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=boundaries, meta=meta)


@router.get(
    "/{boundary_id}",
    response_model=ResponseEnvelope[BoundaryDefinition],
    status_code=status.HTTP_200_OK,
    summary="Get details of a specific boundary definition",
)
async def get_boundary(
    boundary_id: str,
    request: Request,
    payload: dict = Depends(get_current_user_payload),
) -> ResponseEnvelope[BoundaryDefinition]:
    settings = get_settings()
    b = REGISTERED_BOUNDARIES.get(boundary_id)
    if not b:
        raise ResourceNotFoundError(f"Boundary not found: {boundary_id}")
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=b, meta=meta)


@router.post(
    "/{boundary_id}/evaluate",
    response_model=ResponseEnvelope[BoundaryEvaluationResponse],
    status_code=status.HTTP_200_OK,
    summary="Evaluate actual analysis evidence against boundary for spatial intersection & vulnerability",
)
async def evaluate_boundary(
    boundary_id: str,
    req: BoundaryEvaluationRequest,
    request: Request,
    payload: dict = Depends(get_current_user_payload),
) -> ResponseEnvelope[BoundaryEvaluationResponse]:
    settings = get_settings()
    b = REGISTERED_BOUNDARIES.get(boundary_id)
    if not b:
        raise ResourceNotFoundError(f"Boundary not found: {boundary_id}")

    # Build Shapely polygon
    poly = shape(b.geometry)

    # Collect candidate points from request or persisted analysis
    points_to_test: List[Dict[str, float]] = []

    if req.evidence_points:
        points_to_test.extend(req.evidence_points)

    if req.analysis_id:
        # Check job manager or analysis result
        job = await default_job_manager.get_job(req.analysis_id)
        if job and job.result:
            res_dict = job.result if isinstance(job.result, dict) else (job.result.to_dict() if hasattr(job.result, "to_dict") else {})
            # Look for location_context or georeferenced detections
            loc = res_dict.get("location_context") or res_dict.get("sensor_coordinates")
            if loc and "latitude" in loc and "longitude" in loc:
                points_to_test.append({
                    "latitude": float(loc["latitude"]),
                    "longitude": float(loc["longitude"]),
                    "weight": 1.0,
                })

    # Count spatial intersections
    intersecting_count = 0
    for pt in points_to_test:
        lat = pt.get("latitude")
        lon = pt.get("longitude")
        if lat is not None and lon is not None:
            # Shapely takes (x, y) = (lon, lat)
            p = Point(lon, lat)
            if poly.contains(p) or poly.touches(p):
                intersecting_count += 1

    # Evidence gating invariant:
    # If no evidence intersects, vulnerability is INSUFFICIENT_EVIDENCE (None)
    if intersecting_count == 0:
        score = None
        vuln_status = "INSUFFICIENT_EVIDENCE"
        reason = "No valid sensor observations or target detections intersect the boundary polygon."
    else:
        # Legitimate evidence intersects: compute grounded threat based on evidence density
        score = round(min(100.0, 35.0 + intersecting_count * 20.0), 2)
        vuln_status = "CALCULATED"
        reason = f"{intersecting_count} verified observation point(s) spatially intersect the boundary geometry."

    resp_data = BoundaryEvaluationResponse(
        boundary_id=b.id,
        boundary_name=b.name,
        boundary_type=b.boundary_type.value,
        authority=b.authority.value,
        provenance=b.provenance.value,
        status=b.status.value,
        intersecting_evidence_count=intersecting_count,
        vulnerability_score=score,
        vulnerability_status=vuln_status,
        reason=reason,
        disclaimer=b.disclaimer,
    )

    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=resp_data, meta=meta)
