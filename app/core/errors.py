"""
AERION — Standard API Error Architecture
Provides domain exception classes and unified FastAPI exception handlers conforming
strictly to AERION_API_CONTRACT.md Section 1.3 error envelopes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger, request_id_ctx
from app.schemas.common import utc_now_iso
from app.schemas.errors import ErrorBlock, ErrorDetail, ErrorEnvelope, StandardErrorCode

logger = get_logger("errors")


class AERIONException(Exception):
    """
    Base exception for all domain-specific AERION errors.
    """
    def __init__(
        self,
        message: str,
        code: str = StandardErrorCode.PROCESSING_FAILURE,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_type: str = "ServerError",
        details: Optional[List[Dict[str, Any]]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.error_type = error_type
        self.details = details or []
        self.headers = headers or {}


class ValidationError(AERIONException):
    """Raised when incoming client parameters violate validation rules."""
    def __init__(
        self,
        message: str = "Request validation failed.",
        details: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(
            message=message,
            code=StandardErrorCode.VALIDATION_ERROR,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_type="ClientError",
            details=details,
        )


class ResourceNotFoundError(AERIONException):
    """Raised when a requested resource (project, asset, job, result) does not exist."""
    def __init__(
        self,
        message: str = "Requested resource not found.",
        details: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(
            message=message,
            code=StandardErrorCode.RESOURCE_NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
            error_type="ClientError",
            details=details,
        )


class InferenceTimeoutError(AERIONException):
    """Raised when GPU inference queue wait exceeds the configured timeout."""
    def __init__(
        self,
        message: str = "GPU inference acquisition timed out. Resource is currently saturated.",
        details: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(
            message=message,
            code=StandardErrorCode.INFERENCE_TIMEOUT,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_type="ResourceExhaustionError",
            details=details,
        )


class ModelUnavailableError(AERIONException):
    """Raised when a frozen model fails to initialize or memory limits prevent execution."""
    def __init__(
        self,
        message: str = "Perception model currently unavailable.",
        details: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(
            message=message,
            code=StandardErrorCode.MODEL_UNAVAILABLE,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_type="ServerError",
            details=details,
        )


class AuthenticationError(AERIONException):
    """Raised when client fails authentication (missing, invalid, or expired token)."""
    def __init__(
        self,
        message: str = "Authentication required. Invalid or expired credentials.",
        details: Optional[List[Dict[str, Any]]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(
            message=message,
            code=StandardErrorCode.AUTHENTICATION_REQUIRED,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_type="AuthenticationError",
            details=details,
            headers=headers or {"WWW-Authenticate": "Bearer"},
        )


class PermissionDeniedError(AERIONException):
    """Raised when user lacks required role or access permission."""
    def __init__(
        self,
        message: str = "Access denied. Insufficient permissions.",
        details: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(
            message=message,
            code=StandardErrorCode.PERMISSION_DENIED,
            status_code=status.HTTP_403_FORBIDDEN,
            error_type="AuthorizationError",
            details=details,
        )


class RateLimitExceededError(AERIONException):
    """Raised when a client exceeds allowed request frequency."""
    def __init__(
        self,
        message: str = "Rate limit exceeded. Please throttle your requests.",
        details: Optional[List[Dict[str, Any]]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(
            message=message,
            code=StandardErrorCode.RATE_LIMIT_EXCEEDED,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_type="ClientError",
            details=details,
            headers=headers,
        )


def _get_request_id(request: Request) -> str:
    """Extract correlation request ID from request state or context variable."""
    if hasattr(request, "state") and hasattr(request.state, "request_id"):
        return request.state.request_id
    ctx_id = request_id_ctx.get()
    if ctx_id:
        return ctx_id
    return "unknown"


def build_error_response(
    status_code: int,
    code: str,
    message: str,
    error_type: str,
    request_id: str,
    details: Optional[List[ErrorDetail]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> JSONResponse:
    """Helper to assemble a schema-conforming ErrorEnvelope JSONResponse."""
    envelope = ErrorEnvelope(
        success=False,
        error=ErrorBlock(
            code=code,
            message=message,
            error_type=error_type,
            details=details or [],
            timestamp=utc_now_iso(),
            request_id=request_id,
        ),
    )
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(),
        headers=headers or {},
    )


async def aerion_exception_handler(request: Request, exc: AERIONException) -> JSONResponse:
    """Handler for custom AERION domain exceptions."""
    req_id = _get_request_id(request)
    logger.warning(
        f"Domain exception occurred: {exc.code} - {exc.message}",
        extra={"event": "domain_exception", "path": request.url.path, "method": request.method, "request_id": req_id},
    )
    details = [
        ErrorDetail(
            field=d.get("field"),
            issue=d.get("issue", "error"),
            provided=d.get("provided"),
        )
        for d in exc.details
    ]
    return build_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        error_type=exc.error_type,
        request_id=req_id,
        details=details,
        headers=exc.headers,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handler for FastAPI / Pydantic validation failures (HTTP 422)."""
    req_id = _get_request_id(request)
    details: List[ErrorDetail] = []
    for err in exc.errors():
        field_path = ".".join(str(loc) for loc in err.get("loc", []))
        details.append(
            ErrorDetail(
                field=field_path,
                issue=err.get("msg", "validation_error"),
                provided=err.get("input") if not isinstance(err.get("input"), (bytes, bytearray)) else "[BINARY_DATA]",
            )
        )

    logger.info(
        f"Request validation failure on {request.method} {request.url.path}",
        extra={"event": "validation_error", "path": request.url.path, "method": request.method, "request_id": req_id},
    )
    return build_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code=StandardErrorCode.VALIDATION_ERROR,
        message="Request payload or parameters failed validation.",
        error_type="ClientError",
        request_id=req_id,
        details=details,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handler for standard Starlette / FastAPI HTTPExceptions."""
    req_id = _get_request_id(request)
    code_map = {
        401: StandardErrorCode.AUTHENTICATION_REQUIRED,
        403: StandardErrorCode.PERMISSION_DENIED,
        404: StandardErrorCode.RESOURCE_NOT_FOUND,
        429: StandardErrorCode.RATE_LIMIT_EXCEEDED,
        503: StandardErrorCode.MODEL_UNAVAILABLE,
    }
    code = code_map.get(exc.status_code, StandardErrorCode.PROCESSING_FAILURE)
    error_type = "ClientError" if exc.status_code < 500 else "ServerError"

    logger.warning(
        f"HTTP exception {exc.status_code}: {exc.detail}",
        extra={"event": "http_exception", "path": request.url.path, "method": request.method, "status_code": exc.status_code, "request_id": req_id},
    )
    return build_error_response(
        status_code=exc.status_code,
        code=code,
        message=str(exc.detail),
        error_type=error_type,
        request_id=req_id,
        headers=getattr(exc, "headers", None),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler for unexpected runtime exceptions (HTTP 500).
    Logs the full exception trace internally but never exposes internal tracebacks to clients.
    """
    req_id = _get_request_id(request)
    logger.exception(
        f"Unhandled server exception on {request.method} {request.url.path}: {exc}",
        extra={"event": "unhandled_exception", "path": request.url.path, "method": request.method, "request_id": req_id},
    )
    return build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code=StandardErrorCode.PROCESSING_FAILURE,
        message="An unexpected server error occurred during processing. Please reference the request_id for support.",
        error_type="ServerError",
        request_id=req_id,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register all unified exception handlers on the FastAPI application instance."""
    app.add_exception_handler(AERIONException, aerion_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
