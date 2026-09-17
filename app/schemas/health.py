"""
AERION — Health & Readiness Schemas
Defines schemas for service liveness and readiness probes.
"""

from __future__ import annotations

from typing import Dict, Optional
from pydantic import BaseModel, Field

from app.schemas.common import utc_now_iso


class ComponentStatus(BaseModel):
    """Status description for an individual subsystem or integration."""
    status: str = Field(..., description="Component state: ready, lazy_unloaded, not_implemented, degraded, etc.")
    details: Optional[str] = Field(default=None, description="Additional operational context or notes")


class HealthResponse(BaseModel):
    """
    Liveness probe response payload.
    Confirms the application process is alive and responsive.
    """
    status: str = Field(default="healthy", description="Application process health status")
    timestamp: str = Field(default_factory=utc_now_iso, description="Current UTC timestamp")
    version: str = Field(default="v1", description="API version")


class ReadinessResponse(BaseModel):
    """
    Readiness probe response payload.
    Reports operational readiness of the Phase 3A backend foundation and explicit status of subsystems.
    """
    ready: bool = Field(..., description="True if backend is ready to accept requests")
    status: Optional[str] = Field(default="HEALTHY", description="Aggregated overall status (HEALTHY, DEGRADED, UNAVAILABLE)")
    timestamp: str = Field(default_factory=utc_now_iso, description="Current UTC timestamp")
    version: str = Field(default="v1", description="API version")
    components: Dict[str, ComponentStatus] = Field(
        ...,
        description="Explicit breakdown of system components and their real operational state",
    )
