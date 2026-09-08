"""
AERION — API Router Central Assembly
Mounts all versioned /api/v1 endpoint routers conforming to AERION_API_CONTRACT.md.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.health import router as health_router

api_router = APIRouter(prefix="/api/v1")

# Mount health & readiness endpoints under /api/v1/health and /api/v1/ready
api_router.include_router(health_router)

# Future phase routers will be mounted here:
# Phase 3B: api_router.include_router(projects_router)
# Phase 3B: api_router.include_router(assets_router)
# Phase 3C: api_router.include_router(situations_router)
# Phase 3D: api_router.include_router(auth_router)
# Phase 3E: api_router.include_router(analysis_router)
# Phase 3H: api_router.include_router(usage_router)
