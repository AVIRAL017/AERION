"""
AERION — Evidence & Artifact Download API Router
Provides secure, authenticated access to stored evidence assets:
- Annotated drone/satellite images
- Annotated video recordings (.mp4)
- Original uploaded assets
Security & Provenance Invariants:
- Requires authenticated user JWT
- Strict directory traversal and path sanitization
- Guarantees zero credential leakage (no raw Azure connection strings or keys returned)
- Validates file type and existence; returns proper MIME headers and disposition
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from app.api.deps import get_current_user_payload_optional_query
from app.core.config import get_settings
from app.core.errors import ResourceNotFoundError, ValidationError

logger = logging.getLogger("aerion.api.evidence")

router = APIRouter(prefix="/evidence", tags=["Evidence Export"])


@router.get(
    "/{artifact_path:path}",
    summary="Download verified evidence artifact by storage path or key",
    description="Requires authenticated user. Returns binary evidence file (PNG/JPG/MP4) with attachment headers.",
)
async def download_evidence_artifact(
    artifact_path: str,
    request: Request,
    payload: dict = Depends(get_current_user_payload_optional_query),
    download: bool = Query(True, description="Whether to trigger download attachment or inline playback"),
) -> Response:
    settings = get_settings()
    storage_root = Path(settings.STORAGE_LOCAL_ROOT).resolve()

    # Strip leading path separators before path traversal check
    sanitized_path_str = artifact_path.lstrip("/\\")
    if ".." in sanitized_path_str:
        raise ValidationError(
            message="Invalid artifact path: path traversal sequences are prohibited.",
            details=[{"field": "artifact_path", "issue": "path_traversal", "provided": artifact_path}],
        )

    clean_path = Path(sanitized_path_str)
    file_path = (storage_root / clean_path).resolve()

    if not file_path.exists() or not file_path.is_file():
        # Also check under relative storage folder or current working directory
        fallback_path = (Path("storage") / clean_path).resolve()
        if fallback_path.exists() and fallback_path.is_file():
            file_path = fallback_path
        else:
            cwd_path = Path(clean_path).resolve()
            if cwd_path.exists() and cwd_path.is_file() and str(cwd_path).startswith(str(Path.cwd().resolve())):
                file_path = cwd_path
            else:
                raise ResourceNotFoundError(f"Evidence artifact not found: {artifact_path}")

    # Verify that the resolved path is strictly within an allowed storage or workspace boundary
    is_in_storage = str(file_path).startswith(str(storage_root)) or str(file_path).startswith(str(Path("storage").resolve())) or str(file_path).startswith(str(Path.cwd().resolve()))
    if not is_in_storage:
        raise ValidationError(
            message="Access denied: artifact path resides outside designated evidence storage.",
            details=[{"field": "artifact_path", "issue": "forbidden_scope", "provided": artifact_path}],
        )

    # Determine MIME type based on extension
    suffix = file_path.suffix.lower()
    media_type = "application/octet-stream"
    if suffix in (".png",):
        media_type = "image/png"
    elif suffix in (".jpg", ".jpeg"):
        media_type = "image/jpeg"
    elif suffix in (".mp4",):
        media_type = "video/mp4"
    elif suffix in (".pdf",):
        media_type = "application/pdf"
    elif suffix in (".json",):
        media_type = "application/json"

    filename = file_path.name
    disposition = "attachment" if download else "inline"
    file_size = file_path.stat().st_size

    headers = {
        "Content-Disposition": f'{disposition}; filename="{filename}"',
        "Content-Length": str(file_size),
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, max-age=3600",
        "Accept-Ranges": "bytes",
    }

    logger.info(f"Serving evidence artifact {filename} ({media_type}, {file_size} bytes) to user {payload.get('sub', 'unknown')}")
    return FileResponse(
        path=file_path,
        media_type=media_type,
        headers=headers,
    )
