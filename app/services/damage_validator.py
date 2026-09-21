"""
AERION — Damage Pair Structural, Scene Correspondence & Metadata Validator (BUG-006 / Rem-005)
Validates bi-temporal disaster imagery pairs (T0/before and T1/after)
before allowing Siamese change detection inference:
1. Decodability, channels, and physical dimension compatibility
2. Authoritative geospatial metadata consistency (conflicting GPS rejected)
3. Deterministic visual and spatial scene correspondence (unrelated scenes rejected)
4. Location NEVER validates pair compatibility — scene correspondence is required
5. Returns DamagePairValidationResult; if incompatible, inference must be halted upstream.
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
DEFAULT_MAX_GPS_DISTANCE_KM = 10.0  # Configurable maximum allowable geodesic distance (~10 km) between bi-temporal centers


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates great-circle geodesic distance between two points on Earth using Haversine formula.
    """
    import math
    R = 6371.0088  # Mean Earth radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * (math.sin(d_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return R * c


@dataclass
class DamagePairValidationResult:
    is_compatible: bool
    status: str  # "STRUCTURALLY_COMPATIBLE", "SAME_SCENE_CONFIRMED", "PAIR_MISMATCH", "INSUFFICIENT_PAIR_EVIDENCE", "CONFLICTING_GEOGRAPHIC_METADATA"
    before_dimensions: Tuple[int, int]  # (width, height)
    after_dimensions: Tuple[int, int]
    before_channels: int
    after_channels: int
    aspect_ratio_before: float
    aspect_ratio_after: float
    aspect_ratio_disparity: float
    dimension_disparity: float
    geospatial_metadata_status: str  # "CO_REGISTERED", "ABSENT", "PARTIAL", "DISJOINT"
    rejection_reason: Optional[str] = None
    scene_correspondence_metrics: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    validation_latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["metrics"] = self.scene_correspondence_metrics
        return d


class DamagePairValidator:
    """
    Validates pre/post image pair integrity, geographic consistency, and
    scene/spatial compatibility before Siamese change detection inference.
    """

    @classmethod
    def validate_pair(
        cls,
        before_path: Union[str, Path],
        after_path: Union[str, Path],
        max_gps_distance_km: float = DEFAULT_MAX_GPS_DISTANCE_KM,
    ) -> DamagePairValidationResult:
        import time
        start_time = time.perf_counter()

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
                b_array = np.array(b_img)
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
                a_array = np.array(a_img)
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

        # 2. Aspect ratio and scale disparity
        ar_before = float(b_w) / float(b_h)
        ar_after = float(a_w) / float(a_h)
        ar_disparity = max(ar_before, ar_after) / max(min(ar_before, ar_after), 1e-6)

        max_dim_b = max(b_w, b_h)
        max_dim_a = max(a_w, a_h)
        dim_disparity = max(max_dim_b, max_dim_a) / max(min(max_dim_b, max_dim_a), 1)

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

        warnings: List[str] = []
        limitations: List[str] = []

        if (b_w != a_w) or (b_h != a_h):
            warnings.append(
                f"Dimension mismatch (pre: {b_w}x{b_h} vs post: {a_w}x{a_h}); input bilinearly aligned to model resolution."
            )

        # 3. Reliable Embedded GPS Metadata Verification (CASE 5)
        # If reliable GPS exists on BOTH images, a conflict (> threshold km) MUST reject the pair.
        # If GPS exists on only one or neither, visual validation continues (standalone perception does not require GPS).
        geo_status = "ABSENT"
        if b_exif and a_exif:
            b_lat, b_lon = b_exif
            a_lat, a_lon = a_exif
            dist_km = haversine_distance_km(b_lat, b_lon, a_lat, a_lon)
            if dist_km > max_gps_distance_km:
                geo_status = "DISJOINT"
                rejection_msg = (
                    f"Conflicting reliable embedded GPS metadata: Pre ({b_lat:.4f}, {b_lon:.4f}) and Post "
                    f"({a_lat:.4f}, {a_lon:.4f}) images are located {dist_km:.2f} km apart (maximum allowed: {max_gps_distance_km:.1f} km)."
                )
                logger.warning(f"Damage pair rejected on GPS conflict: {rejection_msg}")
                latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                return DamagePairValidationResult(
                    is_compatible=False,
                    status="CONFLICTING_GEOGRAPHIC_METADATA",
                    before_dimensions=(b_w, b_h),
                    after_dimensions=(a_w, a_h),
                    before_channels=3 if b_mode in ("RGB", "RGBA") else 1,
                    after_channels=3 if a_mode in ("RGB", "RGBA") else 1,
                    aspect_ratio_before=round(ar_before, 3),
                    aspect_ratio_after=round(ar_after, 3),
                    aspect_ratio_disparity=round(ar_disparity, 3),
                    dimension_disparity=round(dim_disparity, 3),
                    geospatial_metadata_status=geo_status,
                    rejection_reason=rejection_msg,
                    warnings=warnings + [rejection_msg],
                    limitations=limitations,
                    validation_latency_ms=latency_ms,
                )
            else:
                geo_status = "CO_REGISTERED"
        elif b_exif or a_exif:
            geo_status = "PARTIAL"
            limitations.append("Reliable embedded GPS metadata present on single image only; continuing visual/spatial scene correspondence evaluation.")
        else:
            limitations.append("Reliable embedded GPS metadata absent on both images; continuing visual/spatial scene correspondence evaluation.")

        # 4. Deterministic Visual & Spatial Scene Correspondence Gate (CASES 1-4, 6-7)
        # Location NEVER validates scene compatibility. Visual scene correspondence is MANDATORY.
        scene_passed, scene_status, scene_metrics, scene_reason = cls._verify_scene_correspondence(
            b_array, a_array
        )

        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        if not scene_passed:
            logger.warning(f"Damage pair rejected on scene correspondence: {scene_status} ({scene_reason})")
            return DamagePairValidationResult(
                is_compatible=False,
                status=scene_status,
                before_dimensions=(b_w, b_h),
                after_dimensions=(a_w, a_h),
                before_channels=3 if b_mode in ("RGB", "RGBA") else 1,
                after_channels=3 if a_mode in ("RGB", "RGBA") else 1,
                aspect_ratio_before=round(ar_before, 3),
                aspect_ratio_after=round(ar_after, 3),
                aspect_ratio_disparity=round(ar_disparity, 3),
                dimension_disparity=round(dim_disparity, 3),
                geospatial_metadata_status=geo_status,
                rejection_reason=scene_reason,
                scene_correspondence_metrics=scene_metrics,
                warnings=warnings,
                limitations=limitations,
                validation_latency_ms=latency_ms,
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
            rejection_reason=None,
            scene_correspondence_metrics=scene_metrics,
            warnings=warnings,
            limitations=limitations,
            validation_latency_ms=latency_ms,
        )

    @classmethod
    def _verify_scene_correspondence(
        cls,
        b_array: np.ndarray,
        a_array: np.ndarray,
    ) -> Tuple[bool, str, Dict[str, Any], Optional[str]]:
        """
        Evaluates visual and spatial scene correspondence between T0 and T1.
        Distinguishes valid disaster pairs (same scene + major damage) from
        mismatched scenes (e.g. Nepal vs Dubai) and untextured/featureless pairs.
        """
        # Resize to standard analysis resolution (512x512) for consistent multi-scale evaluation
        s1 = cv2.resize(b_array, (512, 512))
        s2 = cv2.resize(a_array, (512, 512))

        # Convert to guaranteed single-channel 2D grayscale array
        if len(s1.shape) == 3:
            if s1.shape[2] == 4:
                g1 = cv2.cvtColor(s1, cv2.COLOR_RGBA2GRAY)
            elif s1.shape[2] == 3:
                g1 = cv2.cvtColor(s1, cv2.COLOR_RGB2GRAY)
            else:
                g1 = s1[:, :, 0]
        else:
            g1 = s1.copy()

        if len(s2.shape) == 3:
            if s2.shape[2] == 4:
                g2 = cv2.cvtColor(s2, cv2.COLOR_RGBA2GRAY)
            elif s2.shape[2] == 3:
                g2 = cv2.cvtColor(s2, cv2.COLOR_RGB2GRAY)
            else:
                g2 = s2[:, :, 0]
        else:
            g2 = s2.copy()

        if g1.ndim > 2:
            g1 = g1[:, :, 0]
        if g2.ndim > 2:
            g2 = g2[:, :, 0]

        # Step A: Direct pixel similarity
        mean_abs_diff = float(np.mean(np.abs(g1.astype(np.float32) - g2.astype(np.float32))))
        has_pixel_identity = mean_abs_diff < 15.0

        # Step B: SIFT Local Invariant Features & Geometric Consensus (RANSAC Affine Partial 2D)
        sift = cv2.SIFT_create(nfeatures=2000, contrastThreshold=0.02)
        kp1, des1 = sift.detectAndCompute(g1, None)
        kp2, des2 = sift.detectAndCompute(g2, None)

        num_kp1 = len(kp1) if kp1 else 0
        num_kp2 = len(kp2) if kp2 else 0

        # If both images have virtually no texture/corners AND no pixel identity, insufficient evidence
        if num_kp1 < 12 and num_kp2 < 12 and not has_pixel_identity:
            metrics = {
                "sift_keypoints_before": num_kp1,
                "sift_keypoints_after": num_kp2,
                "sift_inliers": 0,
                "mean_abs_pixel_diff": round(mean_abs_diff, 2),
                "decision_evidence": [],
            }
            return False, "INSUFFICIENT_PAIR_EVIDENCE", metrics, "Insufficient texture and keypoint density between T0 and T1."

        sift_inliers = 0
        sift_scale = 1.0
        sift_spread = 0.0
        good_matches_count = 0

        if des1 is not None and des2 is not None and num_kp1 >= 4 and num_kp2 >= 4:
            bf = cv2.BFMatcher(cv2.NORM_L2)
            matches = bf.knnMatch(des1, des2, k=2)
            good_matches = [
                m for m_n in matches if len(m_n) == 2 for m, n in [m_n] if m.distance < 0.78 * n.distance
            ]
            good_matches_count = len(good_matches)
            if good_matches_count >= 4:
                pts1 = np.float32([kp1[m.queryIdx].pt for m in good_matches])
                pts2 = np.float32([kp2[m.trainIdx].pt for m in good_matches])
                M, inliers = cv2.estimateAffinePartial2D(pts1, pts2, method=cv2.RANSAC, ransacReprojThreshold=8.0)
                if inliers is not None:
                    sift_inliers = int(np.sum(inliers))
                    if sift_inliers >= 4 and M is not None:
                        inlier_pts = pts1[inliers.ravel() == 1]
                        sift_scale = float(np.sqrt(M[0, 0]**2 + M[0, 1]**2))
                        dx = float(np.ptp(inlier_pts[:, 0]) / 512.0)
                        dy = float(np.ptp(inlier_pts[:, 1]) / 512.0)
                        sift_spread = float(dx * dy)

        # Step C: Fourier Phase Correlation (checks rigid co-registration & translational shift)
        hann = cv2.createHanningWindow((256, 256), cv2.CV_32F)
        p1_f = cv2.resize(g1, (256, 256)).astype(np.float32)
        p2_f = cv2.resize(g2, (256, 256)).astype(np.float32)
        shift, phase_response = cv2.phaseCorrelate(p1_f, p2_f, hann)
        shift_dist = float(np.sqrt(shift[0]**2 + shift[1]**2))

        # Step D: Multi-Patch Grid Normalized Cross-Correlation (checks surviving ground/topography)
        corr_scores = []
        for r in range(4):
            for c in range(4):
                patch1 = g1[r*128:(r+1)*128, c*128:(c+1)*128]
                patch2 = g2[r*128:(r+1)*128, c*128:(c+1)*128]
                if patch1.std() > 6 and patch2.std() > 6:
                    res = cv2.matchTemplate(patch2, patch1, cv2.TM_CCOEFF_NORMED)[0, 0]
                    corr_scores.append(float(res))

        med_corr = float(np.median(corr_scores)) if corr_scores else 0.0
        high_corr_patches = sum(1 for c in corr_scores if c > 0.40)

        # Synthesis of correspondence criteria (Evidence Fusion - signals are independent, not conjunction gates):
        # Signal 1: Strong geometric correspondence (invariant keypoints, affine consensus)
        has_strong_geometry = (
            sift_inliers >= 5 and 0.45 <= sift_scale <= 2.2 and sift_spread >= 0.02
        )
        # Signal 2: Strong registration evidence (phase correlation peak with minimal translational shift)
        has_strong_registration = (
            phase_response >= 0.16 and shift_dist < 15.0 and high_corr_patches >= 2
        )
        # Signal 3: Co-registered grid alignment (surviving background/terrain structures correlate)
        has_grid_alignment = (
            high_corr_patches >= 3 and med_corr >= 0.18 and shift_dist < 25.0
        )
        # Signal 4: Multi-signal moderate consensus (for disaster scenes with severe structural disruption)
        has_moderate_consensus = (
            (sift_inliers >= 3 and (med_corr >= 0.15 or phase_response >= 0.10) and shift_dist < 40.0)
            or (high_corr_patches >= 2 and sift_inliers >= 3 and 0.40 <= sift_scale <= 2.5)
            or (good_matches_count >= 8 and med_corr >= 0.12 and shift_dist < 35.0)
        )

        passed = (
            has_pixel_identity
            or has_strong_geometry
            or has_strong_registration
            or has_grid_alignment
            or has_moderate_consensus
        )

        decision_evidence = []
        if has_pixel_identity:
            decision_evidence.append("pixel_identity")
        if has_strong_geometry:
            decision_evidence.append("strong_geometry")
        if has_strong_registration:
            decision_evidence.append("strong_registration")
        if has_grid_alignment:
            decision_evidence.append("grid_alignment")
        if has_moderate_consensus:
            decision_evidence.append("moderate_consensus")

        metrics = {
            "sift_keypoints_before": num_kp1,
            "sift_keypoints_after": num_kp2,
            "sift_good_matches": good_matches_count,
            "sift_inliers": sift_inliers,
            "sift_scale": round(sift_scale, 2),
            "sift_spread": round(sift_spread, 3),
            "phase_shift_distance": round(shift_dist, 1),
            "phase_response": round(float(phase_response), 3),
            "median_patch_correlation": round(med_corr, 3),
            "high_correlation_patches": high_corr_patches,
            "mean_abs_pixel_diff": round(mean_abs_diff, 2),
            "decision_evidence": decision_evidence,
        }

        if passed:
            return True, "SAME_SCENE_CONFIRMED", metrics, None

        # Determine rejection category
        if (num_kp1 < 12 and num_kp2 < 12) or (num_kp1 < 15 and num_kp2 < 15 and high_corr_patches == 0 and abs(phase_response) < 0.05):
            return (
                False,
                "INSUFFICIENT_PAIR_EVIDENCE",
                metrics,
                "Insufficient texture and keypoint density between T0 and T1 to establish correspondence.",
            )

        return (
            False,
            "PAIR_MISMATCH",
            metrics,
            "Insufficient evidence that T0 and T1 represent the same geographic area or scene.",
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
