"""
AERION — Structured Logging Foundation
Provides JSON-formatted structured logging with asynchronous request correlation
and automatic redaction of sensitive credentials, tokens, and payloads.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Context variable holding the correlation ID for the active async request
request_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id_ctx", default=None)

# Sensitive patterns that must never be exposed in log messages or metadata
REDACTED_KEYS = frozenset({
    "authorization",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "jwt",
    "s3_secret_key",
    "s3_access_key",
    "mistral_api_key",
    "mapbox_access_token",
    "openrouteservice_api_key",
})


def mask_sensitive_data(data: Any) -> Any:
    """Recursively mask sensitive values in dictionaries and lists."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if str(k).lower() in REDACTED_KEYS or any(secret in str(k).lower() for secret in ("token", "secret", "password")):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = mask_sensitive_data(v)
        return sanitized
    elif isinstance(data, list):
        return [mask_sensitive_data(item) for item in data]
    elif isinstance(data, str) and len(data) > 2000:
        # Prevent massive byte strings or base64 imagery from flooding stdout
        return f"[TRUNCATED_TEXT length={len(data)}]"
    elif isinstance(data, (bytes, bytearray)):
        return f"[BINARY_DATA length={len(data)}]"
    return data


class JSONFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects suitable for ingestion by
    CloudWatch, Datadog, or centralized logging pipelines.
    """
    def format(self, record: logging.LogRecord) -> str:
        req_id = request_id_ctx.get() or getattr(record, "request_id", None) or "-"
        
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": req_id,
        }

        # Include custom extra attributes if supplied
        if hasattr(record, "event"):
            log_entry["event"] = record.event
        if hasattr(record, "path"):
            log_entry["path"] = record.path
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        if hasattr(record, "status_code"):
            log_entry["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_entry["extra"] = mask_sensitive_data(record.extra_data)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


class RequestIDFilter(logging.Filter):
    """Ensures every log record contains a request_id attribute for standard formatting."""
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_ctx.get() or "-"
        return True


def setup_logging(level: str = "INFO", json_logs: bool = True) -> None:
    """
    Initialize root logging configuration for the AERION platform.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicate output
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.addFilter(RequestIDFilter())
    if json_logs:
        stream_handler.setFormatter(JSONFormatter())
    else:
        stream_handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] [req:%(request_id)s] %(message)s")
        )
    root_logger.addHandler(stream_handler)


def get_logger(name: str) -> logging.Logger:
    """Obtain a named logger instance."""
    return logging.getLogger(f"aerion.{name}")
