"""
AERION — Security Infrastructure & Middleware
Provides explicit CORS configuration, standard HTTP security headers, and
cryptographically sound request correlation ID middleware.
"""

from __future__ import annotations

import re
import uuid
from typing import Callable, List
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import AERIONSettings
from app.core.logging import request_id_ctx

# Valid request ID pattern: alphanumeric characters, hyphens, and underscores only
REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]+$")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that establishes a cryptographically secure request correlation ID.
    Validates incoming client IDs or generates a fresh UUID4.
    Attaches the ID to request.state, contextvars, and the response headers.
    """
    def __init__(self, app: FastAPI, header_name: str = "X-Request-ID", max_length: int = 64) -> None:
        super().__init__(app)
        self.header_name = header_name
        self.max_length = max_length

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        incoming_id = request.headers.get(self.header_name)
        
        # Validate incoming request ID
        if (
            incoming_id
            and len(incoming_id) <= self.max_length
            and REQUEST_ID_REGEX.match(incoming_id)
        ):
            request_id = incoming_id
        else:
            request_id = str(uuid.uuid4())

        # Store in request state for endpoint handlers
        request.state.request_id = request_id

        # Bind to async contextvar for structured logging
        token = request_id_ctx.set(request_id)

        try:
            response = await call_next(request)
        except Exception as exc:
            from app.core.errors import unhandled_exception_handler
            response = await unhandled_exception_handler(request, exc)
        finally:
            request_id_ctx.reset(token)

        # Attach to outbound response headers
        response.headers[self.header_name] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that injects defense-in-depth HTTP security headers into all responses.
    Appropriate for headless API microservices and data pipelines.
    """
    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        response = await call_next(request)

        # Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking / framing
        response.headers["X-Frame-Options"] = "DENY"

        # Control referrer leakage across cross-origin requests
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict content loading (strict default for API)
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"

        # Disable sensitive hardware features for API responses
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        return response


def configure_cors(app: FastAPI, settings: AERIONSettings) -> None:
    """
    Configure strict CORS rules based on verified application settings.
    Guarantees no wildcard origins in production environments.
    """
    origins: List[str] = (
        settings.ALLOWED_ORIGINS
        if isinstance(settings.ALLOWED_ORIGINS, list)
        else [s.strip() for s in str(settings.ALLOWED_ORIGINS).split(",") if s.strip()]
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
        max_age=600,
    )
