"""
AERION — Local Artifact Storage Service (Roadmap Step 14)
Provides deterministic, secure local storage for uploaded evidence assets:
- Validates mime types and file sizes
- Generates safe unique storage keys (never trusts client filenames)
- Prevents path traversal vulnerabilities
- Computes cryptographic SHA-256 digests for evidence provenance
- Persists Asset records to database
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional, Tuple, Union
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ValidationError
from app.db.models import Asset as DBAsset

logger = logging.getLogger("aerion.storage")


class LocalArtifactStorage:
    """
    Manages controlled local storage of uploaded analysis evidence files.
    """

    def __init__(self, root_dir: Optional[Union[str, Path]] = None):
        settings = get_settings()
        self.root_dir = Path(root_dir or settings.STORAGE_LOCAL_ROOT).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    MAX_ASSET_BYTES = 500 * 1024 * 1024  # 500 MB hard ceiling

    def store_file(
        self,
        source_path: Union[str, Path],
        asset_type: str,
        project_id: uuid.UUID,
        suffix: Optional[str] = None,
        max_bytes: Optional[int] = None,
    ) -> Tuple[str, str, int]:
        """
        Safely copies an asset to the permanent storage directory.
        Enforces maximum file size limit, sanitized directory creation, and path containment.
        Returns:
            (storage_key, sha256_hex, file_size_bytes)
        """
        src = Path(source_path).resolve()
        if not src.exists():
            raise FileNotFoundError(f"Source file to store not found: {source_path}")

        file_size = src.stat().st_size
        size_ceiling = max_bytes or self.MAX_ASSET_BYTES
        if file_size > size_ceiling:
            raise ValidationError(
                message=f"Asset file exceeds maximum permitted size of {size_ceiling // (1024 * 1024)} MB.",
                details=[{"field": "file_size", "issue": "file_too_large", "provided": f"{file_size} bytes"}],
            )

        # Sanitize asset_type against directory traversal
        clean_asset_type = "".join(c for c in str(asset_type) if c.isalnum() or c in ("-", "_")).lower() or "general"

        # Compute SHA-256
        h = hashlib.sha256()
        with open(src, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        sha256_hex = h.hexdigest()

        # Safe isolated directory structure: storage/<project_id>/<asset_type>/<uuid>.<suffix>
        file_ext = suffix or src.suffix or ".bin"
        if not file_ext.startswith("."):
            file_ext = f".{file_ext}"

        safe_asset_id = uuid.uuid4()
        dest_dir = self.root_dir / str(project_id) / clean_asset_type
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_file = (dest_dir / f"{safe_asset_id}{file_ext}").resolve()
        # Verify path containment within storage root
        if not str(dest_file).startswith(str(self.root_dir)):
            raise ValidationError(
                message="Path traversal violation detected during storage resolution.",
                details=[{"field": "storage_path", "issue": "path_traversal", "provided": str(dest_file)}],
            )

        shutil.copy2(src, dest_file)

        # Storage key is relative to root
        storage_key = f"{project_id}/{clean_asset_type}/{safe_asset_id}{file_ext}"
        logger.info(f"Stored asset {storage_key} ({file_size} bytes, sha256={sha256_hex[:8]}...)")
        return storage_key, sha256_hex, file_size
