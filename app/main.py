"""
AERION — FastAPI Application Factory & Main Entrypoint
Constructs and configures the FastAPI application instance with security middleware,
exception handlers, structured logging, and lifecycle event management.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.router import api_router
from app.core.config import AERIONSettings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import get_logger, setup_logging
from app.core.security import RequestIDMiddleware, SecurityHeadersMiddleware, configure_cors

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan manager.
    Handles startup configuration and graceful termination.
    """
    settings = getattr(app.state, "settings", get_settings())
    setup_logging(level="DEBUG" if settings.DEBUG else "INFO", json_logs=(settings.ENVIRONMENT != "development"))
    
    logger.info(
        f"AERION Platform starting up in '{settings.ENVIRONMENT}' mode (API {settings.API_VERSION})",
        extra={"event": "startup", "environment": settings.ENVIRONMENT, "api_version": settings.API_VERSION},
    )
    yield
    logger.info("AERION Platform shutting down", extra={"event": "shutdown"})


def create_app(settings: Optional[AERIONSettings] = None) -> FastAPI:
    """
    FastAPI application factory.
    Enables isolated instances for unit and integration testing without shared state.
    """
    app_settings = settings or get_settings()

    app = FastAPI(
        title=app_settings.APP_NAME,
        version=app_settings.API_VERSION,
        description="AERION AI-Powered Satellite & Drone Geospatial Intelligence Platform",
        docs_url="/docs" if app_settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if app_settings.ENVIRONMENT != "production" else None,
        openapi_url="/openapi.json" if app_settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # Attach settings to application state
    app.state.settings = app_settings

    # 1. Register Error Handlers (formats all errors to standard AERION envelopes)
    register_error_handlers(app)

    # 2. Register Middleware (LIFO order: outermost executes first)
    # Security headers on all outbound responses
    app.add_middleware(SecurityHeadersMiddleware)

    # Request ID extraction, validation, and generation
    app.add_middleware(
        RequestIDMiddleware,
        header_name=app_settings.REQUEST_ID_HEADER,
        max_length=app_settings.MAX_REQUEST_ID_LENGTH,
    )

    # Explicit CORS configuration
    configure_cors(app, app_settings)

    # 3. Register Routers
    # Unversioned operational probes at root: GET /health, GET /ready
    app.include_router(health_router)

    # Versioned API routes: /api/v1/...
    app.include_router(api_router)

    return app


# Default ASGI application instance for Uvicorn runner
app = create_app()
