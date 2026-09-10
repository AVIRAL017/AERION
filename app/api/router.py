"""
AERION — API Router Central Assembly
Mounts all versioned /api/v1 endpoint routers conforming to AERION_API_CONTRACT.md.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.situations import router as situations_router
from app.api.analysis import router as analysis_router
from app.api.usage import router as usage_router
from app.api.geospatial import router as geospatial_router

api_router = APIRouter(prefix="/api/v1")

# Mount versioned endpoints
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(situations_router)
api_router.include_router(analysis_router)
api_router.include_router(usage_router)
api_router.include_router(geospatial_router)
