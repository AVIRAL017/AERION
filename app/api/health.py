"""
AERION — Health & Readiness Endpoints
Provides non-blocking liveness and readiness inspection for orchestration monitoring.
Conforms strictly to AERION_API_CONTRACT.md Section 1.2 response envelopes.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.core.inference_lock import default_inference_lock
from app.schemas.common import MetaBlock, ResponseEnvelope, utc_now_iso
from app.schemas.health import ComponentStatus, HealthResponse, ReadinessResponse

router = APIRouter(tags=["Health & Readiness"])


def _extract_request_id(request: Request) -> str:
    """Retrieve request correlation ID attached by RequestIDMiddleware."""
    return getattr(request.state, "request_id", "req-unknown")


@router.get("/health", response_model=ResponseEnvelope[HealthResponse])
async def health_check(request: Request) -> ResponseEnvelope[HealthResponse]:
    """
    Liveness probe: verifies that the FastAPI application process is alive.
    Does NOT load heavy ML models, connect to databases, or make external network calls.
    """
    settings = get_settings()
    req_id = _extract_request_id(request)

    data = HealthResponse(
        status="healthy",
        timestamp=utc_now_iso(),
        version=settings.API_VERSION,
    )
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=req_id,
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=data, meta=meta)


@router.get("/ready", response_model=ResponseEnvelope[ReadinessResponse])
async def readiness_check(request: Request) -> ResponseEnvelope[ReadinessResponse]:
    """
    Readiness probe: reports operational readiness of Phase 3A backend foundation.
    Accurately and honestly reflects status of subsystems without fabricating fake connections.
    """
    settings = get_settings()
    req_id = _extract_request_id(request)

    components = {
        "process": ComponentStatus(
            status="ready",
            details=f"FastAPI application active in {settings.ENVIRONMENT} mode.",
        ),
        "config": ComponentStatus(
            status="ready",
            details="Pydantic settings loaded and environment validated.",
        ),
        "inference_lock": ComponentStatus(
            status="ready",
            details=f"GPU mutex active (locked={default_inference_lock.is_locked}, waiters={default_inference_lock.waiters_count}).",
        ),
        "models": ComponentStatus(
            status="lazy_unloaded",
            details="Perception and damage models deferred to on-demand execution to protect 6 GB VRAM.",
        ),
        "database": ComponentStatus(
            status="not_implemented",
            details="PostgreSQL + PostGIS persistence planned for Phase 3B.",
        ),
        "providers": ComponentStatus(
            status="not_implemented",
            details="External providers (Open-Meteo, OpenRouteService, Mapbox) planned for Phase 3F.",
        ),
        "mistral": ComponentStatus(
            status="not_implemented",
            details="Mistral AI executive advisory planned for Phase 3G.",
        ),
    }

    data = ReadinessResponse(
        ready=True,
        timestamp=utc_now_iso(),
        version=settings.API_VERSION,
        components=components,
    )
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=req_id,
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=data, meta=meta)
