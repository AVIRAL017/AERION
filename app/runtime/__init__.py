"""
AERION — Runtime Package
Exports runtime adapter decoupling FastAPI from the frozen ML orchestrator.
"""

from app.runtime.adapter import (
    FROZEN_CONFIDENCE_THRESHOLD,
    FROZEN_DAMAGE_THRESHOLD,
    FROZEN_IOU_THRESHOLD,
    RuntimeAdapter,
    default_runtime_adapter,
)

__all__ = [
    "FROZEN_CONFIDENCE_THRESHOLD",
    "FROZEN_IOU_THRESHOLD",
    "FROZEN_DAMAGE_THRESHOLD",
    "RuntimeAdapter",
    "default_runtime_adapter",
]
