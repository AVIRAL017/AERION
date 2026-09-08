"""
AERION — Schemas Package
Unified request and response schemas conforming to AERION_API_CONTRACT.md.
"""

from app.schemas.common import MetaBlock, ResponseEnvelope
from app.schemas.errors import ErrorBlock, ErrorDetail, ErrorEnvelope, StandardErrorCode
from app.schemas.health import ComponentStatus, HealthResponse, ReadinessResponse

__all__ = [
    "MetaBlock",
    "ResponseEnvelope",
    "ErrorDetail",
    "ErrorBlock",
    "ErrorEnvelope",
    "StandardErrorCode",
    "ComponentStatus",
    "HealthResponse",
    "ReadinessResponse",
]
