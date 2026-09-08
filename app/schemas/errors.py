"""
AERION — Error Schemas
Defines standardized error envelopes adhering to AERION_API_CONTRACT.md Section 1.3.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.common import utc_now_iso


class StandardErrorCode(str, Enum):
    """Authoritative error codes defined in AERION_API_CONTRACT.md Section 1.3."""
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    SUBSCRIPTION_RESTRICTION = "SUBSCRIPTION_RESTRICTION"
    USAGE_LIMIT_EXCEEDED = "USAGE_LIMIT_EXCEEDED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PROCESSING_FAILURE = "PROCESSING_FAILURE"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    INFERENCE_TIMEOUT = "INFERENCE_TIMEOUT"


class ErrorDetail(BaseModel):
    """Itemized issue detail within an error response."""
    field: Optional[str] = Field(default=None, description="Request field that triggered the error")
    issue: str = Field(..., description="Machine-readable issue descriptor")
    provided: Optional[Any] = Field(default=None, description="Rejected value if safe to echo")


class ErrorBlock(BaseModel):
    """Inner error payload in AERION standard error envelope."""
    code: str = Field(..., description="Standard machine-readable error code")
    message: str = Field(..., description="Human-readable explanation of the error")
    error_type: str = Field(..., description="Category: ClientError, ServerError, SecurityError, etc.")
    details: List[ErrorDetail] = Field(
        default_factory=list,
        description="Structured list of field-level or specific failure causes",
    )
    timestamp: str = Field(
        default_factory=utc_now_iso,
        description="ISO 8601 UTC timestamp of error occurrence",
    )
    request_id: str = Field(
        ...,
        description="Request correlation ID for log tracing",
    )


class ErrorEnvelope(BaseModel):
    """
    Standard error envelope wrapping all error responses.
    AERION_API_CONTRACT.md Section 1.3
    """
    success: bool = Field(
        default=False,
        description="Always false for error responses",
    )
    error: ErrorBlock = Field(
        ...,
        description="Standardized error details",
    )
