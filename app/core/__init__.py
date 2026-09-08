"""
AERION — Core Foundation Package
Exports core configuration, logging, security, error handling, rate limiting, and synchronization primitives.
"""

from app.core.config import AERIONSettings, get_settings
from app.core.errors import (
    AERIONException,
    InferenceTimeoutError,
    ModelUnavailableError,
    RateLimitExceededError,
    ResourceNotFoundError,
    ValidationError,
    register_error_handlers,
)
from app.core.inference_lock import InferenceLock, default_inference_lock
from app.core.jobs import JobManager, JobRecord, JobStatus, default_job_manager
from app.core.logging import get_logger, request_id_ctx, setup_logging
from app.core.rate_limit import InMemoryRateLimiter, RateLimiter, RateLimitDependency, default_rate_limiter
from app.core.security import RequestIDMiddleware, SecurityHeadersMiddleware, configure_cors

__all__ = [
    "AERIONSettings",
    "get_settings",
    "AERIONException",
    "ValidationError",
    "ResourceNotFoundError",
    "InferenceTimeoutError",
    "ModelUnavailableError",
    "RateLimitExceededError",
    "register_error_handlers",
    "InferenceLock",
    "default_inference_lock",
    "JobStatus",
    "JobRecord",
    "JobManager",
    "default_job_manager",
    "get_logger",
    "request_id_ctx",
    "setup_logging",
    "RateLimiter",
    "InMemoryRateLimiter",
    "default_rate_limiter",
    "RateLimitDependency",
    "RequestIDMiddleware",
    "SecurityHeadersMiddleware",
    "configure_cors",
]
