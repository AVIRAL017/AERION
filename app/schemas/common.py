"""
AERION — Common Schemas
Defines global envelope schemas adhering to AERION_API_CONTRACT.md Section 1.2.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format with millisecond precision."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class MetaBlock(BaseModel):
    """
    Standard metadata block included in all AERION API response envelopes.
    """
    timestamp: str = Field(
        default_factory=utc_now_iso,
        description="ISO 8601 UTC timestamp of response generation",
    )
    request_id: str = Field(
        ...,
        description="Unique request correlation ID for tracing and logging",
    )
    version: str = Field(
        default="v1",
        description="API major version identifier",
    )


class ResponseEnvelope(BaseModel, Generic[T]):
    """
    Standard success envelope wrapping all JSON API responses.
    AERION_API_CONTRACT.md Section 1.2
    """
    success: bool = Field(
        default=True,
        description="Always true for successful requests",
    )
    data: T = Field(
        ...,
        description="Domain payload corresponding to the specific endpoint",
    )
    meta: MetaBlock = Field(
        ...,
        description="Standardized execution and tracing metadata",
    )
