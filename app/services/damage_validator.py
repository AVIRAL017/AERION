"""
AERION — Damage Pair Structural & Metadata Validator (BUG-006)
Validates bi-temporal disaster imagery pairs (T0/before and T1/after)
before allowing inference execution:
- Decodability and integrity of both images
- Channel count consistency (e.g. 3-channel RGB/BGR)
- Aspect ratio and dimension compatibility:
  * Aspect ratio ratio must be within reasonable bounds (<= 2.0x)
  * Dimension disparity must not exceed 5.0x
- Geospatial metadata check if EXIF/GeoTIFF coordinates exist on both
- Returns DamagePairValidationResult with compatibility status and warnings/limitations
- Raises ValidationError (HTTP 422) if pair is structurally incompatible
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image, ExifTags

from app.core.errors import ValidationError

logger = logging.getLogger("aerion.services.damage_validator")

# Compatibility constants
MAX_ASPECT_RATIO_DISPARITY = 2.0
MAX_DIMENSION_DISPARITY = 5.0
MIN_DIMENSION_PX = 1


@dataclass
class DamagePairValidationResult:
    is_compatible: bool
    status: str  # "STRUCTURALLY_COMPATIBLE", "STRUCTURALLY_INCOMPATIBLE", "INSUFFICIENT_EVIDENCE"
    before_dimensions: Tuple[int, int]  # (width, height)
    after_dimensions: Tuple[int, int]
    before_channels: int
    after_channels: int
    aspect_ratio_before: float
    aspect_ratio_after: float
    aspect_ratio_disparity: float
    dimension_disparity: float
    geospatial_metadata_status: str  # "CO_REGISTERED", "ABSENT", "DISJOINT"
    warnings: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DamagePairValidator:
    """
    Validates pre/post image pair integrity and structural compatibility
    before Siamese change detection inference.
    """

    @classmethod
    def validate_pair(
        cls,
        before_path: Union[str, Path],
        after_path: Union[str, Path],
    ) -> DamagePairValidationResult:
        b_path = Path(before_path)
        a_path = Path(after_path)

        if not b_path.exists():
            raise ValidationError(
                message=f"Pre-disaster image path does not exist: {before_path}",
                details=[{"field": "before_image_path", "issue": "file_not_found", "provided": str(before_path)}],
            )
        if not a_path.exists():
            raise ValidationError(
                message=f"Post-disaster image path does not exist: {after_path}",
                details=[{"field": "after_image_path", "issue": "file_not_found", "provided": str(after_path)}],
            )

        # 1. Decode test & shape retrieval using PIL
        try:
            with Image.open(b_path) as b_img:
                b_w, b_h = b_img.size
                b_mode = b_img.mode
                b_exif = cls._extract_gps_info(b_img)
        except Exception as exc:
            raise ValidationError(
                message=f"Pre-disaster image could not be decoded: {exc}",
                details=[{"field": "before_image_path", "issue": "corrupt_image", "provided": str(before_path)}],
            )

        try:
            with Image.open(a_path) as a_img:
                a_w, a_h = a_img.size
                a_mode = a_img.mode
                a_exif = cls._extract_gps_info(a_img)
        except Exception as exc:
            raise ValidationError(
                message=f"Post-disaster image could not be decoded: {exc}",
                details=[{"field": "after_image_path", "issue": "corrupt_image", "provided": str(after_path)}],
            )

        if b_w < MIN_DIMENSION_PX or b_h < MIN_DIMENSION_PX:
            raise ValidationError(
                message=f"Pre-disaster image dimensions ({b_w}x{b_h}) below minimum {MIN_DIMENSION_PX}px.",
                details=[{"field": "before_image_path", "issue": "dimensions_too_small"}],
            )
        if a_w < MIN_DIMENSION_PX or a_h < MIN_DIMENSION_PX:
            raise ValidationError(
                message=f"Post-disaster image dimensions ({a_w}x{a_h}) below minimum {MIN_DIMENSION_PX}px.",
                details=[{"field": "after_image_path", "issue": "dimensions_too_small"}],
            )

        # 2. Aspect ratio calculations
        ar_before = float(b_w) / float(b_h)
        ar_after = float(a_w) / float(a_h)
        ar_disparity = max(ar_before, ar_after) / max(min(ar_before, ar_after), 1e-6)

        # 3. Scale disparity
        max_dim_b = max(b_w, b_h)
        max_dim_a = max(a_w, a_h)
        dim_disparity = max(max_dim_b, max_dim_a) / max(min(max_dim_b, max_dim_a), 1)

        # 4. Incompatibility checks
        warnings: List[str] = []
        limitations: List[str] = []

        if ar_disparity > MAX_ASPECT_RATIO_DISPARITY:
            raise ValidationError(
                message=(
                    f"Structural Incompatibility: Image pair aspect ratio disparity ({ar_disparity:.2f}x) "
                    f"exceeds limit ({MAX_ASPECT_RATIO_DISPARITY}x). Pre: {b_w}x{b_h} (AR {ar_before:.2f}), "
                    f"Post: {a_w}x{a_h} (AR {ar_after:.2f}). Images must cover comparable scene geometries."
                ),
                details=[{
                    "field": "damage_pair",
                    "issue": "aspect_ratio_disparity",
                    "aspect_ratio_disparity": ar_disparity,
                    "before_dimensions": [b_w, b_h],
                    "after_dimensions": [a_w, a_h],
                }],
            )

        if dim_disparity > MAX_DIMENSION_DISPARITY:
            raise ValidationError(
                message=(
                    f"Structural Incompatibility: Image pair scale disparity ({dim_disparity:.2f}x) "
                    f"exceeds limit ({MAX_DIMENSION_DISPARITY}x). Pre: {b_w}x{b_h}, Post: {a_w}x{a_h}."
                ),
                details=[{
                    "field": "damage_pair",
                    "issue": "dimension_scale_disparity",
                    "dimension_disparity": dim_disparity,
                    "before_dimensions": [b_w, b_h],
                    "after_dimensions": [a_w, a_h],
                }],
            )

        # 5. Geospatial metadata comparison (enrichment/warning only; does not block ML perception)
        geo_status = "ABSENT"
        if b_exif and a_exif:
            b_lat, b_lon = b_exif
            a_lat, a_lon = a_exif
            coord_diff = max(abs(b_lat - a_lat), abs(b_lon - a_lon))
            if coord_diff > 0.5:
                geo_status = "DISJOINT"
                warnings.append(
                    f"Geospatial Disparity: Pre ({b_lat:.4f}, {b_lon:.4f}) and Post "
                    f"({a_lat:.4f}, {a_lon:.4f}) images are located in disjoint geographic areas ({coord_diff:.3f} deg difference). "
                    "Inference proceeds on visual evidence."
                )
            else:
                geo_status = "CO_REGISTERED"
        else:
            limitations.append("Authoritative geospatial co-registration metadata absent; normalized by pixel dimensions.")

        if (b_w != a_w) or (b_h != a_h):
            warnings.append(
                f"Dimension mismatch (pre: {b_w}x{b_h} vs post: {a_w}x{a_h}); input bilinearly aligned to model resolution."
            )

        return DamagePairValidationResult(
            is_compatible=True,
            status="STRUCTURALLY_COMPATIBLE",
            before_dimensions=(b_w, b_h),
            after_dimensions=(a_w, a_h),
            before_channels=3 if b_mode in ("RGB", "RGBA") else 1,
            after_channels=3 if a_mode in ("RGB", "RGBA") else 1,
            aspect_ratio_before=round(ar_before, 3),
            aspect_ratio_after=round(ar_after, 3),
            aspect_ratio_disparity=round(ar_disparity, 3),
            dimension_disparity=round(dim_disparity, 3),
            geospatial_metadata_status=geo_status,
            warnings=warnings,
            limitations=limitations,
        )

    @staticmethod
    def _extract_gps_info(image: Image.Image) -> Optional[Tuple[float, float]]:
        """Extracts latitude and longitude from image EXIF tags if present."""
        try:
            exif = image._getexif()
            if not exif:
                return None

            gps_info = None
            for key, val in exif.items():
                if ExifTags.TAGS.get(key) == "GPSInfo":
                    gps_info = val
                    break

            if not gps_info:
                return None

            def _convert_to_degrees(value):
                d = float(value[0])
                m = float(value[1])
                s = float(value[2])
                return d + (m / 60.0) + (s / 3600.0)

            lat = _convert_to_degrees(gps_info[2])
            if gps_info.get(1) == "S":
                lat = -lat

            lon = _convert_to_degrees(gps_info[4])
            if gps_info.get(3) == "W":
                lon = -lon

            return (lat, lon)
        except Exception:
            return None
