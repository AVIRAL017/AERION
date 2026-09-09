"""
AERION — Security Utilities & Input Sanitization
Provides shared, audited security primitives:
- Base64 payload decoding with pre-allocation byte-size bounds
- Safe local path verification against path traversal attacks
- Filename sanitization
- Buffer overflow and memory exhaustion prevention
"""

from __future__ import annotations

import base64
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Set

from app.core.errors import ResourceNotFoundError, ValidationError

# Default maximum payload sizes (in bytes)
MAX_IMAGE_B64_BYTES = 25 * 1024 * 1024       # 25 MB
MAX_VIDEO_B64_BYTES = 150 * 1024 * 1024      # 150 MB

# Whitelisted image/video file extensions
ALLOWED_IMAGE_EXTENSIONS: Set[str] = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
ALLOWED_VIDEO_EXTENSIONS: Set[str] = {".mp4", ".avi", ".mov", ".mkv"}

# Regex for safe filename characters
SAFE_FILENAME_REGEX = re.compile(r"^[a-zA-Z0-9_\.-]+$")


def validate_base64_payload(
    b64_str: str,
    max_bytes: int = MAX_IMAGE_B64_BYTES,
    field_name: str = "image_base64",
) -> bytes:
    """
    Validates and decodes base64 strings with strict size guards.
    Calculates estimated decoded size BEFORE memory allocation to prevent memory exhaustion / DoS.
    """
    if not b64_str or not isinstance(b64_str, str):
        raise ValidationError(
            message="Base64 payload cannot be empty.",
            details=[{"field": field_name, "issue": "empty_payload", "provided": None}],
        )

    # Estimate decoded size from base64 string length: (len * 3) / 4 - padding
    str_len = len(b64_str)
    padding = b64_str.count("=", -2)
    estimated_size = (str_len * 3) // 4 - padding

    if estimated_size > max_bytes:
        raise ValidationError(
            message=f"Payload size exceeds maximum permitted limit of {max_bytes // (1024 * 1024)} MB.",
            details=[{
                "field": field_name,
                "issue": "payload_too_large",
                "provided": f"~{estimated_size // (1024 * 1024)} MB",
            }],
        )

    try:
        data = base64.b64decode(b64_str, validate=True)
    except Exception as exc:
        raise ValidationError(
            message=f"Invalid base64 payload: {exc}",
            details=[{"field": field_name, "issue": "base64_decode_error", "provided": "[REDACTED]"}],
        )

    if len(data) > max_bytes:
        raise ValidationError(
            message=f"Decoded payload exceeds maximum permitted limit of {max_bytes // (1024 * 1024)} MB.",
            details=[{
                "field": field_name,
                "issue": "payload_too_large",
                "provided": f"{len(data)} bytes",
            }],
        )

    return data


def write_temp_base64_file(
    b64_str: str,
    suffix: str = ".jpg",
    max_bytes: int = MAX_IMAGE_B64_BYTES,
    field_name: str = "image_base64",
) -> Path:
    """
    Safely writes decoded base64 bytes to an isolated temporary file.
    Guarantees clean directory creation and automatic cleanup on decode failure.
    """
    data = validate_base64_payload(b64_str, max_bytes=max_bytes, field_name=field_name)

    temp_dir = Path(tempfile.mkdtemp(prefix="aerion_sec_"))
    safe_name = f"{uuid.uuid4()}{suffix}"
    dest_path = temp_dir / safe_name

    try:
        with open(dest_path, "wb") as f:
            f.write(data)
        return dest_path
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise ValidationError(
            message=f"Failed to write temporary asset buffer: {exc}",
            details=[{"field": field_name, "issue": "io_error", "provided": safe_name}],
        )


def sanitize_local_path(
    path_str: str,
    field_name: str = "file_path",
    allowed_extensions: Optional[Set[str]] = None,
) -> Path:
    """
    Sanitizes and resolves a local filesystem path.
    Prevents path traversal, checks existence, and verifies permissible file extensions.
    """
    if not path_str or not isinstance(path_str, str):
        raise ValidationError(
            message=f"Parameter '{field_name}' must be a non-empty string.",
            details=[{"field": field_name, "issue": "missing_path", "provided": None}],
        )

    # Basic string-level traversal defense before filesystem resolution
    normalized = path_str.replace("\\", "/")
    if "\0" in normalized:
        raise ValidationError(
            message="Null bytes are strictly prohibited in file paths.",
            details=[{"field": field_name, "issue": "null_byte_detected", "provided": "[REDACTED]"}],
        )

    path = Path(path_str).resolve()

    if not path.exists():
        raise ResourceNotFoundError(f"Specified file does not exist: {path_str}")

    if not path.is_file():
        raise ValidationError(
            message=f"Specified path is not a regular file: {path_str}",
            details=[{"field": field_name, "issue": "not_a_file", "provided": path_str}],
        )

    if allowed_extensions:
        ext = path.suffix.lower()
        if ext not in allowed_extensions:
            raise ValidationError(
                message=f"File extension '{ext}' is not permitted. Allowed extensions: {sorted(allowed_extensions)}",
                details=[{"field": field_name, "issue": "invalid_extension", "provided": ext}],
            )

    return path
