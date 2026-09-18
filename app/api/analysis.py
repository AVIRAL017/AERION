"""
AERION — Analysis API Router (Roadmap Step 12)
Exposes inference endpoints for static drone/satellite imagery, bi-temporal damage pairs,
and border surveillance video processing.
Adheres to AERION_API_CONTRACT.md Sections 4 & 5.
Safety & Architectural Invariants:
- Route controllers call existing application services (never direct YOLO/PyTorch calls)
- GPU inference lock and runtime contracts fully respected
- Safe file path validation and base64 / path payload options
- Zero external package installation; works standard in existing environment
"""

from __future__ import annotations

import base64
import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from aerion_runtime_contracts import AERIONAnalysisResult
from app.api.deps import get_current_user_payload
from app.core.config import get_settings
from app.core.errors import ResourceNotFoundError, ValidationError
from app.core.jobs import JobManager, JobRecord, JobStatus, default_job_manager
from app.schemas.common import MetaBlock, ResponseEnvelope, utc_now_iso
from app.schemas.evidence import GeoPoint
from app.schemas.external import AdvisoryPriority, ProviderStatus
from app.db.session import get_async_session
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.repositories import (
    AnalysisJobRepository,
    AnalysisResultRepository,
    ProjectRepository,
)
from app.db.models import AnalysisJob as DBAnalysisJob, AnalysisResult as DBAnalysisResult, Project as DBProject, EvidenceRecord as DBEvidenceRecord
from app.services.storage_service import LocalArtifactStorage
from app.services.annotation_service import AnnotationService
from app.services.application_services import (
    BorderVideoJobService,
    DamageAnalysisService,
    ImageProcessingService,
    SatelliteAnalysisService,
)
from app.services.damage_validator import DamagePairValidator
from app.services.building_service import BuildingService
from app.services.external_geocoding_service import ExternalGeocodingService
from app.services.external_routing_service import ExternalRoutingService
from app.services.external_weather_service import ExternalWeatherService
from app.services.geospatial_service import GeospatialService
from app.services.infrastructure_service import InfrastructureService
from app.services.international_boundary_service import InternationalBoundaryService
from app.services.persistence_service import AnalysisPersistenceService
from app.services.shelter_service import ShelterService
from app.services.structured_intelligence import MistralAdvisoryClient
from protocols import get_protocol

logger = logging.getLogger("aerion.api.analysis")

router = APIRouter(prefix="/analysis", tags=["Analysis"])


def _extract_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req-unknown")


async def _safely_persist_result(
    result: AERIONAnalysisResult,
    project_id_str: Optional[str],
    situation_id_str: Optional[str] = None,
    source_asset_key: Optional[str] = None,
    annotated_artifact_key: Optional[str] = None,
    existing_job_id_str: Optional[str] = None,
    user_id_str: Optional[str] = None,
    org_id_str: Optional[str] = None,
    raw_payload_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Attempts to persist analysis result to PostgreSQL/PostGIS.
    If database is not connected (e.g. invalid credentials or network unreachable),
    logs gracefully and returns persistence metadata with database_available=False.
    Never crashes analysis response when DB is unreachable.
    """
    try:
        proj_uuid = uuid.UUID(project_id_str) if project_id_str and len(project_id_str) == 36 else uuid.UUID("00000000-0000-0000-0000-000000000001")
        sit_uuid = uuid.UUID(situation_id_str) if situation_id_str and len(situation_id_str) == 36 else None
        job_uuid = uuid.UUID(existing_job_id_str) if existing_job_id_str and len(existing_job_id_str) == 36 else None
        user_uuid = uuid.UUID(user_id_str) if user_id_str and len(user_id_str) == 36 else None
        org_uuid = uuid.UUID(org_id_str) if org_id_str and len(org_id_str) == 36 else None

        persister = AnalysisPersistenceService()
        persist_info = await persister.persist_analysis(
            result=result,
            project_id=proj_uuid,
            situation_id=sit_uuid,
            source_asset_key=source_asset_key,
            annotated_artifact_key=annotated_artifact_key,
            existing_job_id=job_uuid,
            user_id=user_uuid,
            organization_id=org_uuid,
            raw_payload_override=raw_payload_override,
        )
        persist_info["database_available"] = True
        return persist_info
    except Exception as exc:
        logger.warning(f"Could not persist analysis {result.analysis_id} to database ({exc}); operating in session memory.")
        return {
            "persisted": False,
            "database_available": False,
            "reason": str(exc),
        }


async def _check_quota_before_inference(org_id_str: Optional[str], dimension: str = "drone_image") -> None:
    """
    Checks if the organization has exceeded their monthly quota for the specified dimension.
    Raises QuotaExceededError if exhausted.
    """
    if not org_id_str:
        return
    try:
        import uuid
        from app.db.session import AsyncSessionLocal
        from app.db.repositories import UsageEventRepository, SubscriptionRepository
        from app.services.subscription_service import EntitlementService, PlanTier, UsageDimension
        from app.core.errors import QuotaExceededError

        org_uuid = uuid.UUID(org_id_str)
        async with AsyncSessionLocal() as session:
            sub_repo = SubscriptionRepository(session)
            sub = await sub_repo.get_by_organization(org_uuid)
            tier_str = (sub.plan if sub else "FREE").upper()
            tier = PlanTier.PRO if tier_str == "PRO" else PlanTier.FREE

            dim_enum = UsageDimension.DRONE_IMAGE
            if dimension == "satellite_tile":
                dim_enum = UsageDimension.SATELLITE_TILE
            elif dimension == "damage_pair":
                dim_enum = UsageDimension.DAMAGE_PAIR
            elif dimension == "video_minute":
                dim_enum = UsageDimension.VIDEO_MINUTE

            usage_repo = UsageEventRepository(session)
            used = await usage_repo.get_monthly_count(org_uuid, dimension=dimension)

            ent_svc = EntitlementService()
            eval_res = ent_svc.evaluate_quota(tier=tier, dimension=dim_enum, current_used=used, requested_quantity=1)
            if eval_res["is_exhausted"]:
                raise QuotaExceededError(
                    message=f"Monthly quota limit of {eval_res['limit']} for {dimension} reached under {tier.value} plan. Please upgrade to PRO to proceed.",
                    details=[{
                        "field": "quota",
                        "dimension": dimension,
                        "used": eval_res["used"],
                        "limit": eval_res["limit"],
                        "plan": tier.value,
                    }]
                )
    except QuotaExceededError:
        raise
    except Exception as exc:
        logger.debug(f"Quota pre-check skipped or unconfigured ({exc})")




# ============================================================================
# REQUEST SCHEMAS (AERION_API_CONTRACT.md Sections 4.1, 5.1)
# ============================================================================

class ImageAnalysisRequest(BaseModel):
    project_id: Optional[str] = Field(default="00000000-0000-0000-0000-000000000001")
    situation_id: Optional[str] = Field(default=None, description="Optional Situation ID to link evidence and events")
    image_path: Optional[str] = Field(default=None, description="Local server file path to aerial image")
    image_base64: Optional[str] = Field(default=None, description="Base64-encoded image bytes")
    source_type: str = Field(default="drone", description="'drone' or 'satellite'")
    mode: str = Field(default="disaster", description="'disaster' or 'border'")
    drone_model: str = Field(default="visdrone_only", description="'visdrone_only' or 'unified'")
    confidence_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
    iou_threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    terrain_context: Optional[str] = Field(default="arid")
    run_intelligence: bool = Field(default=True)


class DamageAnalysisRequest(BaseModel):
    project_id: Optional[str] = Field(default="00000000-0000-0000-0000-000000000001")
    situation_id: Optional[str] = Field(default=None, description="Optional Situation ID to link evidence and events")
    before_image_path: Optional[str] = Field(default=None, description="Local file path to pre-disaster image")
    after_image_path: Optional[str] = Field(default=None, description="Local file path to post-disaster image")
    before_base64: Optional[str] = Field(default=None, description="Base64 pre-disaster image bytes")
    after_base64: Optional[str] = Field(default=None, description="Base64 post-disaster image bytes")
    threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    run_intelligence: bool = Field(default=True)


class BorderVideoAnalysisRequest(BaseModel):
    project_id: Optional[str] = Field(default="00000000-0000-0000-0000-000000000001")
    situation_id: Optional[str] = Field(default=None, description="Optional Situation ID to link evidence and events")
    video_path: Optional[str] = Field(default=None, description="Local file path to recorded video file")
    video_base64: Optional[str] = Field(default=None, description="Base64-encoded video bytes")
    max_frames: Optional[int] = Field(default=30, ge=1, le=300)
    frame_stride: int = Field(default=5, ge=1, le=30)
    terrain_context: Optional[str] = Field(default="arid")
    generate_annotated_video: bool = Field(default=True, description="Whether to generate derived annotated video artifact")



from app.core.security_utils import (
    MAX_IMAGE_B64_BYTES,
    MAX_VIDEO_B64_BYTES,
    sanitize_local_path,
    write_temp_base64_file,
)


def _write_temp_base64(
    b64_str: str,
    suffix: str = ".jpg",
    max_bytes: int = MAX_IMAGE_B64_BYTES,
    field_name: str = "image_base64",
) -> Path:
    return write_temp_base64_file(b64_str=b64_str, suffix=suffix, max_bytes=max_bytes, field_name=field_name)


@router.post(
    "/image",
    response_model=ResponseEnvelope[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Execute perception inference on aerial or satellite imagery",
)
async def analyze_image(
    req: ImageAnalysisRequest,
    request: Request,
    payload: dict = Depends(get_current_user_payload),
) -> ResponseEnvelope[Dict[str, Any]]:
    settings = get_settings()

    target_path: Optional[Path] = None
    is_temp = False

    if req.image_path:
        p = Path(req.image_path)
        if not p.exists():
            raise ResourceNotFoundError(f"Specified image path does not exist: {req.image_path}")
        target_path = p
    elif req.image_base64:
        target_path = _write_temp_base64(req.image_base64)
        is_temp = True
    else:
        raise ValidationError(
            message="Either 'image_path' or 'image_base64' must be provided.",
            details=[{"field": "image_path", "issue": "missing_image_source", "provided": None}],
        )

    # Enforce quota check
    req_dim = "satellite_tile" if req.source_type.lower() == "satellite" else "drone_image"
    await _check_quota_before_inference(payload.get("org"), dimension=req_dim)


    try:
        if req.source_type.lower() == "satellite":
            sat_service = SatelliteAnalysisService()
            result: AERIONAnalysisResult = await sat_service.analyze_satellite_image(
                image_path=str(target_path),
                terrain_context=req.terrain_context,
                run_intelligence=req.run_intelligence,
                confidence_threshold=req.confidence_threshold,
                iou_threshold=req.iou_threshold,
            )
        else:
            img_service = ImageProcessingService()
            result: AERIONAnalysisResult = await img_service.analyze_image(
                image_path=str(target_path),
                mode=req.mode,
                drone_model=req.drone_model,
                terrain_context=req.terrain_context,
                run_intelligence=req.run_intelligence,
                confidence_threshold=req.confidence_threshold,
                iou_threshold=req.iou_threshold,
            )

        result_dict = result.to_dict() if hasattr(result, "to_dict") else dict(result)

        # Store verified original source image asset for secondary download
        source_key: Optional[str] = None
        source_artifact_info: Optional[Dict[str, Any]] = None
        proj_uuid = uuid.UUID(req.project_id) if req.project_id and len(req.project_id) == 36 else uuid.UUID("00000000-0000-0000-0000-000000000001")
        try:
            storage = LocalArtifactStorage()
            src_key, src_sha, src_bytes = storage.store_file(
                source_path=target_path,
                asset_type="source_image",
                project_id=proj_uuid,
                suffix=target_path.suffix or ".jpg",
            )
            source_key = src_key
            source_artifact_info = {
                "artifact_key": src_key,
                "mime_type": "image/jpeg" if (target_path.suffix.lower() in (".jpg", ".jpeg") or is_temp) else "image/png",
                "sha256": src_sha,
                "size_bytes": src_bytes,
            }
            result_dict["source_artifact"] = source_artifact_info
        except Exception as src_exc:
            logger.warning(f"Failed to store source image asset: {src_exc}")

        # Roadmap Step 15: Annotated Visual Evidence Pipeline
        annotated_artifact_info: Optional[Dict[str, Any]] = None
        annotated_key: Optional[str] = None
        try:
            annotator = AnnotationService()
            annot_res = annotator.annotate_and_store(
                source_image_path=target_path,
                analysis_result=result,
                project_id=proj_uuid,
            )
            annotated_key = annot_res.artifact_key
            annotated_artifact_info = {
                "artifact_key": annot_res.artifact_key,
                "mime_type": annot_res.mime_type,
                "sha256": annot_res.sha256,
                "size_bytes": annot_res.file_size_bytes,
                "image_width": annot_res.image_width,
                "image_height": annot_res.image_height,
                "is_zero_detection": annot_res.is_zero_detection,
            }
            # Attach base64 preview for immediate frontend rendering
            result_dict["annotated_image_base64"] = annot_res.annotated_base64
            result_dict["annotated_artifact"] = annotated_artifact_info
        except Exception as annot_exc:
            logger.warning(
                f"Annotation generation failed for analysis {result.analysis_id}: {annot_exc}. "
                "Analysis response proceeds without visual annotation."
            )

        persist_info = await _safely_persist_result(
            result=result,
            project_id_str=req.project_id,
            situation_id_str=req.situation_id,
            source_asset_key=source_key,
            annotated_artifact_key=annotated_key,
            user_id_str=payload.get("sub"),
            org_id_str=payload.get("org"),
            raw_payload_override=result_dict,
        )
        result_dict["persistence"] = persist_info

        meta = MetaBlock(
            timestamp=utc_now_iso(),
            request_id=_extract_request_id(request),
            version=settings.API_VERSION,
        )
        return ResponseEnvelope(success=True, data=result_dict, meta=meta)
    finally:
        if is_temp and target_path and target_path.exists():
            try:
                target_path.unlink(missing_ok=True)
                if target_path.parent.exists():
                    shutil.rmtree(target_path.parent, ignore_errors=True)
            except Exception as exc:
                logger.warning(f"Error cleaning up temp file {target_path}: {exc}")


@router.post(
    "/damage",
    response_model=ResponseEnvelope[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Execute bi-temporal Siamese damage assessment on pre/post image pair",
)
async def analyze_damage(
    req: DamageAnalysisRequest,
    request: Request,
    payload: dict = Depends(get_current_user_payload),
) -> ResponseEnvelope[Dict[str, Any]]:
    settings = get_settings()

    before_path: Optional[Path] = None
    after_path: Optional[Path] = None
    temp_dirs: List[Path] = []

    if req.before_image_path and req.after_image_path:
        bp = Path(req.before_image_path)
        ap = Path(req.after_image_path)
        if not bp.exists():
            raise ResourceNotFoundError(f"Pre-disaster image path does not exist: {req.before_image_path}")
        if not ap.exists():
            raise ResourceNotFoundError(f"Post-disaster image path does not exist: {req.after_image_path}")
        before_path = bp
        after_path = ap
    elif req.before_base64 and req.after_base64:
        before_path = _write_temp_base64(req.before_base64, field_name="before_base64")
        after_path = _write_temp_base64(req.after_base64, field_name="after_base64")
        temp_dirs.extend([before_path.parent, after_path.parent])
    else:
        raise ValidationError(
            message="Both before and after image sources must be provided (via file paths or base64).",
            details=[{"field": "before_image_path", "issue": "missing_damage_pair", "provided": None}],
        )

    # Enforce quota check
    await _check_quota_before_inference(payload.get("org"), dimension="damage_pair")


    try:
        # Validate structural & geospatial compatibility of before/after pair (BUG-006)
        validation_res = DamagePairValidator.validate_pair(str(before_path), str(after_path))

        damage_service = DamageAnalysisService()
        result: AERIONAnalysisResult = await damage_service.analyze_damage_pair(
            before_path=str(before_path),
            after_path=str(after_path),
            threshold=req.threshold,
            run_intelligence=req.run_intelligence,
        )
        result_dict = result.to_dict() if hasattr(result, "to_dict") else dict(result)
        result_dict["pair_validation"] = validation_res.to_dict()

        # Generate and store visual damage mask overlay artifact (BUG-021)
        annotated_key: Optional[str] = None
        try:
            proj_uuid = uuid.UUID(req.project_id) if req.project_id and len(req.project_id) == 36 else uuid.UUID("00000000-0000-0000-0000-000000000001")
            annotator = AnnotationService()
            annot_res = annotator.render_damage_overlay_and_store(
                after_image_path=after_path,
                before_image_path=before_path,
                damage_analysis=result.damage_analysis,
                project_id=proj_uuid,
            )
            annotated_key = annot_res.artifact_key
            result_dict["damage_mask_base64"] = annot_res.annotated_base64
            result_dict["damage_artifact"] = {
                "artifact_key": annot_res.artifact_key,
                "mime_type": annot_res.mime_type,
                "sha256": annot_res.sha256,
                "size_bytes": annot_res.file_size_bytes,
                "image_width": annot_res.image_width,
                "image_height": annot_res.image_height,
                "is_zero_damage": annot_res.is_zero_detection,
            }
        except Exception as annot_exc:
            logger.warning(f"Damage overlay artifact generation failed: {annot_exc}")

        persist_info = await _safely_persist_result(
            result=result,
            project_id_str=req.project_id,
            situation_id_str=req.situation_id,
            annotated_artifact_key=annotated_key,
            user_id_str=payload.get("sub"),
            org_id_str=payload.get("org"),
        )
        result_dict["persistence"] = persist_info

        meta = MetaBlock(
            timestamp=utc_now_iso(),
            request_id=_extract_request_id(request),
            version=settings.API_VERSION,
        )
        return ResponseEnvelope(success=True, data=result_dict, meta=meta)

    finally:
        for tdir in temp_dirs:
            try:
                if tdir.exists():
                    shutil.rmtree(tdir, ignore_errors=True)
            except Exception as exc:
                logger.warning(f"Error cleaning up temp dir {tdir}: {exc}")


@router.post(
    "/border/video",
    response_model=ResponseEnvelope[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Process recorded border surveillance video through frame iterator and ByteTrack",
)
async def analyze_border_video(
    req: BorderVideoAnalysisRequest,
    request: Request,
    payload: dict = Depends(get_current_user_payload),
) -> ResponseEnvelope[Dict[str, Any]]:
    settings = get_settings()

    target_video_path: Optional[Path] = None
    is_temp = False

    if req.video_path:
        p = Path(req.video_path)
        if not p.exists():
            raise ResourceNotFoundError(f"Specified video file does not exist: {req.video_path}")
        target_video_path = p
    elif req.video_base64:
        target_video_path = _write_temp_base64(
            req.video_base64,
            suffix=".mp4",
            max_bytes=MAX_VIDEO_B64_BYTES,
            field_name="video_base64",
        )
        is_temp = True
    else:
        raise ValidationError(
            message="Either 'video_path' or 'video_base64' must be provided.",
            details=[{"field": "video_path", "issue": "missing_video_source", "provided": None}],
        )

    # Enforce quota check
    await _check_quota_before_inference(payload.get("org"), dimension="video_minute")


    try:
        video_service = BorderVideoJobService()
        report_data = await video_service.process_video_file(
            project_id=req.project_id or "00000000-0000-0000-0000-000000000001",
            video_path=str(target_video_path),
            max_frames=req.max_frames,
            frame_stride=req.frame_stride,
            terrain_context=req.terrain_context,
            generate_annotated_video=req.generate_annotated_video,
        )

        annotated_artifact = report_data.get("annotated_video_artifact")
        annotated_key = annotated_artifact.get("artifact_key") if annotated_artifact else None
        last_result = report_data.pop("last_analysis_result", None)

        if last_result is not None and annotated_key is not None:
            persist_info = await _safely_persist_result(
                result=last_result,
                project_id_str=req.project_id,
                situation_id_str=req.situation_id,
                annotated_artifact_key=annotated_key,
                user_id_str=payload.get("sub"),
                org_id_str=payload.get("org"),
            )
            report_data["persistence"] = persist_info
            if persist_info.get("analysis_id"):
                report_data["analysis_id"] = persist_info.get("analysis_id")
            if persist_info.get("job_id"):
                report_data["job_id"] = persist_info.get("job_id")

        meta = MetaBlock(
            timestamp=utc_now_iso(),
            request_id=_extract_request_id(request),
            version=settings.API_VERSION,
        )
        return ResponseEnvelope(success=True, data=report_data, meta=meta)
    finally:
        if is_temp and target_video_path and target_video_path.exists():
            try:
                target_video_path.unlink(missing_ok=True)
                if target_video_path.parent.exists():
                    shutil.rmtree(target_video_path.parent, ignore_errors=True)
            except Exception as exc:
                logger.warning(f"Error cleaning up temp video file {target_video_path}: {exc}")


# ============================================================================
# BATCH 2 — STEP 25 & 26: DISASTER & BORDER SECURITY MODE E2E WORKFLOWS
# ============================================================================

class DisasterModeE2ERequest(BaseModel):
    project_id: Optional[str] = Field(default="00000000-0000-0000-0000-000000000001")
    situation_id: Optional[str] = Field(default=None)
    before_image_path: Optional[str] = Field(default=None)
    after_image_path: Optional[str] = Field(default=None)
    before_base64: Optional[str] = Field(default=None)
    after_base64: Optional[str] = Field(default=None)
    threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    # Optional georeferencing
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    # Evacuation destination for routing
    evacuation_dest_lat: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    evacuation_dest_lon: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    radius_km: float = Field(default=15.0, ge=0.5, le=100.0)
    run_intelligence: bool = Field(default=True)


class BorderSecurityModeE2ERequest(BaseModel):
    project_id: Optional[str] = Field(default="00000000-0000-0000-0000-000000000001")
    situation_id: Optional[str] = Field(default=None)
    video_path: Optional[str] = Field(default=None)
    video_base64: Optional[str] = Field(default=None)
    image_path: Optional[str] = Field(default=None)
    image_base64: Optional[str] = Field(default=None)
    max_frames: Optional[int] = Field(default=30, ge=1, le=300)
    frame_stride: int = Field(default=5, ge=1, le=30)
    terrain_context: Optional[str] = Field(default="arid")
    # Optional georeferencing for border sensor position
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    generate_annotated_video: bool = Field(default=True)
    run_intelligence: bool = Field(default=True)


@router.post(
    "/disaster/e2e",
    response_model=ResponseEnvelope[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Execute comprehensive Disaster Mode E2E workflow with real ML, PostGIS, weather, routing, and Mistral advisory",
)
async def analyze_disaster_e2e(
    req: DisasterModeE2ERequest,
    request: Request,
    payload: dict = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_async_session),
) -> ResponseEnvelope[Dict[str, Any]]:
    settings = get_settings()

    before_path: Optional[Path] = None
    after_path: Optional[Path] = None
    temp_dirs: List[Path] = []

    if req.before_image_path and req.after_image_path:
        bp = Path(req.before_image_path)
        ap = Path(req.after_image_path)
        if not bp.exists():
            raise ResourceNotFoundError(f"Pre-disaster image not found: {req.before_image_path}")
        if not ap.exists():
            raise ResourceNotFoundError(f"Post-disaster image not found: {req.after_image_path}")
        before_path = bp
        after_path = ap
    elif req.before_base64 and req.after_base64:
        before_path = _write_temp_base64(req.before_base64, field_name="before_base64")
        after_path = _write_temp_base64(req.after_base64, field_name="after_base64")
        temp_dirs.extend([before_path.parent, after_path.parent])
    else:
        raise ValidationError(
            message="Both before and after image sources must be provided for Disaster E2E analysis.",
            details=[{"field": "before_image_path", "issue": "missing_damage_pair", "provided": None}],
        )

    try:
        # Validate structural & geospatial compatibility of before/after pair (BUG-006)
        validation_res = DamagePairValidator.validate_pair(str(before_path), str(after_path))

        # 1. Run frozen damage detection model
        damage_service = DamageAnalysisService()
        try:
            runtime_result: AERIONAnalysisResult = await damage_service.analyze_damage_pair(
                before_path=str(before_path),
                after_path=str(after_path),
                threshold=req.threshold,
                run_intelligence=req.run_intelligence,
            )
        except Exception as inf_exc:
            if "identify image" in str(inf_exc).lower() or "unidentified" in str(inf_exc).lower():
                raise ValidationError(
                    message=f"Corrupt or unsupported image asset provided: {inf_exc}",
                    details=[{"field": "before_base64", "issue": "corrupt_image_payload", "provided": None}],
                )
            raise
        result_dict = runtime_result.to_dict() if hasattr(runtime_result, "to_dict") else dict(runtime_result)

        # Generate and store visual damage mask overlay artifact (BUG-021)
        annotated_damage_key: Optional[str] = None
        damage_artifact_info: Optional[Dict[str, Any]] = None
        damage_mask_b64: Optional[str] = None
        try:
            proj_uuid = uuid.UUID(req.project_id) if req.project_id and len(req.project_id) == 36 else uuid.UUID("00000000-0000-0000-0000-000000000001")
            annotator = AnnotationService()
            annot_res = annotator.render_damage_overlay_and_store(
                after_image_path=after_path,
                before_image_path=before_path,
                damage_analysis=runtime_result.damage_analysis,
                project_id=proj_uuid,
            )
            annotated_damage_key = annot_res.artifact_key
            damage_mask_b64 = annot_res.annotated_base64
            damage_artifact_info = {
                "artifact_key": annot_res.artifact_key,
                "mime_type": annot_res.mime_type,
                "sha256": annot_res.sha256,
                "size_bytes": annot_res.file_size_bytes,
                "image_width": annot_res.image_width,
                "image_height": annot_res.image_height,
                "is_zero_damage": annot_res.is_zero_detection,
            }
        except Exception as annot_exc:
            logger.warning(f"Damage overlay artifact generation failed in E2E: {annot_exc}")

        # 2. Extract damage metrics safely
        damage_analysis = runtime_result.damage_analysis
        damage_pixels = getattr(damage_analysis, "damage_pixels", 0)
        damage_ratio = getattr(damage_analysis, "damage_ratio", 0.0)
        damage_percentage = getattr(damage_analysis, "damage_percentage", 0.0)

        # 3. Handle Location & Georeferencing Invariant
        has_coords = req.latitude is not None and req.longitude is not None
        georeferencing_status = "AVAILABLE" if has_coords else "UNAVAILABLE"

        administrative_context: Optional[Dict[str, Any]] = None
        historical_hazards: List[Dict[str, Any]] = []
        seismic_events: List[Dict[str, Any]] = []
        shelters: List[Dict[str, Any]] = []
        buildings_count: int = 0
        infrastructure_count: int = 0
        weather_data: Optional[Dict[str, Any]] = None
        route_data: Optional[Dict[str, Any]] = None

        if has_coords:
            lat = float(req.latitude)  # type: ignore[arg-type]
            lon = float(req.longitude)  # type: ignore[arg-type]

            # 3a. Geospatial service enrichment (admin boundaries + historical hazards)
            try:
                geo_svc = GeospatialService(session)
                admin_res = await geo_svc.resolve_admin_point(latitude=lat, longitude=lon)
                if admin_res.available:
                    administrative_context = admin_res.model_dump()

                # Query historical earthquakes (including Step 21 USGS ComCat data)
                haz_res = await geo_svc.query_historical_hazards(
                    latitude=lat,
                    longitude=lon,
                    radius_km=req.radius_km,
                    hazard_type="EARTHQUAKE",
                    limit=20,
                )
                if haz_res and getattr(haz_res, "records", None):
                    seismic_events = [r.model_dump() for r in haz_res.records]
            except Exception as geo_err:
                logger.warning(f"Geospatial hazard query degraded ({geo_err})")

            # 3b. Emergency shelters
            try:
                shelter_svc = ShelterService(session)
                sh_res = await shelter_svc.query_shelters(
                    latitude=lat,
                    longitude=lon,
                    radius_km=req.radius_km,
                    limit=10,
                )
                if sh_res.available and sh_res.shelters:
                    shelters = [s.model_dump() for s in sh_res.shelters]
            except Exception as sh_err:
                logger.warning(f"Shelter query degraded ({sh_err})")

            # 3c. Building footprints & critical infrastructure in vicinity
            try:
                bldg_svc = BuildingService(session)
                bldg_res = await bldg_svc.query_buildings_proximity(
                    latitude=lat,
                    longitude=lon,
                    radius_km=min(req.radius_km, 5.0),
                    limit=50,
                )
                buildings_count = bldg_res.record_count if bldg_res.available else 0

                infra_svc = InfrastructureService(session)
                infra_res = await infra_svc.query_infrastructure_proximity(
                    latitude=lat,
                    longitude=lon,
                    radius_km=req.radius_km,
                    limit=20,
                )
                infrastructure_count = infra_res.record_count if infra_res.available else 0
            except Exception as bldg_err:
                logger.warning(f"Building/infrastructure query degraded ({bldg_err})")

            # 3d. Real Weather via Open-Meteo
            try:
                weather_svc = ExternalWeatherService()
                w_rec = await weather_svc.get_weather(latitude=lat, longitude=lon)
                weather_data = w_rec.model_dump()
            except Exception as w_err:
                logger.warning(f"Weather query degraded ({w_err})")
                weather_data = {"status": "UNAVAILABLE", "error": str(w_err)}

            # 3e. Real Road Routing via OpenRouteService/Mapbox
            dest_lat = req.evacuation_dest_lat
            dest_lon = req.evacuation_dest_lon
            # If explicit destination not provided, route to nearest registered open shelter if available
            if (dest_lat is None or dest_lon is None) and shelters:
                dest_loc = shelters[0].get("location") or {}
                dest_lat = dest_loc.get("latitude") if isinstance(dest_loc, dict) else getattr(dest_loc, "latitude", None)
                dest_lon = dest_loc.get("longitude") if isinstance(dest_loc, dict) else getattr(dest_loc, "longitude", None)

            if dest_lat is not None and dest_lon is not None:
                try:
                    routing_svc = ExternalRoutingService()
                    r_rec = await routing_svc.calculate_route(
                        origin_lat=lat,
                        origin_lon=lon,
                        dest_lat=dest_lat,
                        dest_lon=dest_lon,
                    )
                    route_data = r_rec.model_dump()
                except Exception as r_err:
                    logger.warning(f"Routing query degraded ({r_err})")
                    route_data = {"status": "UNAVAILABLE", "error": str(r_err)}
            else:
                route_data = {
                    "status": "UNAVAILABLE",
                    "reason": "No evacuation destination coordinates provided or resolved.",
                }
        else:
            route_data = {
                "status": "UNAVAILABLE",
                "reason": "Geographic coordinates unavailable for source asset.",
            }
            weather_data = {
                "status": "UNAVAILABLE",
                "reason": "Geographic coordinates unavailable for source asset.",
            }

        # 4. Deterministic Priority Calculation (Reuse intelligence_engine thresholds)
        # CRITICAL >= 0.75, HIGH >= 0.50, MEDIUM >= 0.25
        score = damage_ratio
        if score >= 0.75:
            det_priority = AdvisoryPriority.CRITICAL
        elif score >= 0.50:
            det_priority = AdvisoryPriority.HIGH
        elif score >= 0.25:
            det_priority = AdvisoryPriority.MEDIUM
        else:
            det_priority = AdvisoryPriority.LOW

        standard_protocol = get_protocol("disaster", "building_damage")

        # 5. Build Grounded Evidence Package for Mistral
        evidence_package = {
            "analysis_id": str(runtime_result.analysis_id),
            "mode": "DISASTER_RESPONSE",
            "georeferencing_status": georeferencing_status,
            "coordinates": {"latitude": req.latitude, "longitude": req.longitude} if has_coords else None,
            "damage_evaluations_count": 1,
            "damage_pixels": damage_pixels,
            "mean_damage_ratio": damage_ratio,
            "damage_percentage": damage_percentage,
            "administrative_context": administrative_context,
            "historical_hazards_count": len(seismic_events),
            "shelters_count": len(shelters),
            "registered_buildings_count": buildings_count,
            "critical_infrastructure_count": infrastructure_count,
            "weather_status": weather_data.get("status") if weather_data else "UNAVAILABLE",
            "weather_details": {
                "temp_c": weather_data.get("temperature_celsius") if weather_data else None,
                "wind_speed_mps": weather_data.get("wind_speed_mps") if weather_data else None,
                "condition": weather_data.get("condition_description") if weather_data else None,
                "flight_suitability": weather_data.get("flight_suitability") if weather_data else "UNAVAILABLE",
            } if weather_data and weather_data.get("status") == "AVAILABLE" else None,
            "routing_status": route_data.get("status") if route_data else "UNAVAILABLE",
            "route_summary": {
                "distance_m": route_data.get("total_distance_meters") if route_data else None,
                "duration_s": route_data.get("total_duration_seconds") if route_data else None,
                "steps_count": len(route_data.get("steps", [])) if route_data else 0,
            } if route_data and route_data.get("status") == "AVAILABLE" else None,
            "road_blockage_status": "NOT_ESTABLISHED (requires corroborated on-ground or hazard data)",
            "limitations": [
                "Road blockage cannot be inferred solely from adjacent structural damage.",
                "Shelter operational and capacity status reflects registered dataset records, not real-time inspection.",
            ],
        }

        # 6. Generate Grounded Mistral Advisory
        mistral_client = MistralAdvisoryClient()
        advisory = await mistral_client.generate_grounded_advisory(
            mode="DISASTER_RESPONSE",
            evidence_package=evidence_package,
            standard_protocol=standard_protocol,
            deterministic_priority=det_priority,
        )

        # 7. Persist Analysis and Evidence
        persist_info = await _safely_persist_result(
            result=runtime_result,
            project_id_str=req.project_id,
            situation_id_str=req.situation_id,
            annotated_artifact_key=annotated_damage_key,
            user_id_str=payload.get("sub"),
            org_id_str=payload.get("org"),
        )

        e2e_response = {
            "analysis_id": str(runtime_result.analysis_id),
            "mode": "DISASTER_RESPONSE",
            "georeferencing_status": georeferencing_status,
            "pair_validation": validation_res.to_dict(),
            "damage_mask_base64": damage_mask_b64,
            "damage_artifact": damage_artifact_info,
            "damage_analysis": {
                "damage_pixels": damage_pixels,
                "damage_ratio": damage_ratio,
                "damage_percentage": damage_percentage,
                "threshold_applied": req.threshold,
                "claim": (
                    f"Damage probability exceeds threshold ({req.threshold}) across {damage_percentage:.2f}% of evaluated region."
                    if damage_pixels > 0 else "No damage detected exceeding configured threshold."
                ),
            },
            "geospatial_context": {
                "administrative": administrative_context,
                "seismic_events": seismic_events,
                "shelters": shelters,
                "buildings_in_radius": buildings_count,
                "critical_infrastructure_in_radius": infrastructure_count,
            },
            "external_context": {
                "weather": weather_data,
                "routing": route_data,
            },
            "advisory": advisory.model_dump(),
            "persistence": persist_info,
            "limitations": advisory.limitations,
        }

        meta = MetaBlock(
            timestamp=utc_now_iso(),
            request_id=_extract_request_id(request),
            version=settings.API_VERSION,
        )
        return ResponseEnvelope(success=True, data=e2e_response, meta=meta)

    finally:
        for tdir in temp_dirs:
            try:
                if tdir.exists():
                    shutil.rmtree(tdir, ignore_errors=True)
            except Exception as exc:
                logger.warning(f"Error cleaning up temp dir {tdir}: {exc}")


@router.post(
    "/border/e2e",
    response_model=ResponseEnvelope[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Execute comprehensive Border Security Mode E2E workflow with tracking, persistence filtering, boundary verification, and Mistral advisory",
)
async def analyze_border_e2e(
    req: BorderSecurityModeE2ERequest,
    request: Request,
    payload: dict = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_async_session),
) -> ResponseEnvelope[Dict[str, Any]]:
    settings = get_settings()

    target_video_path: Optional[Path] = None
    target_image_path: Optional[Path] = None
    is_temp = False

    if req.video_path:
        vp = Path(req.video_path)
        if not vp.exists():
            raise ResourceNotFoundError(f"Specified video file does not exist: {req.video_path}")
        target_video_path = vp
    elif req.video_base64:
        target_video_path = _write_temp_base64(
            req.video_base64,
            suffix=".mp4",
            max_bytes=MAX_VIDEO_B64_BYTES,
            field_name="video_base64",
        )
        is_temp = True
    elif req.image_path:
        ip = Path(req.image_path)
        if not ip.exists():
            raise ResourceNotFoundError(f"Specified image file does not exist: {req.image_path}")
        target_image_path = ip
    elif req.image_base64:
        target_image_path = _write_temp_base64(req.image_base64, field_name="image_base64")
        is_temp = True
    else:
        raise ValidationError(
            message="A video or image source must be provided for Border Security E2E analysis.",
            details=[{"field": "video_path", "issue": "missing_visual_source", "provided": None}],
        )

    try:
        annotated_artifact_info: Optional[Dict[str, Any]] = None
        annotated_key: Optional[str] = None
        last_result: Optional[AERIONAnalysisResult] = None
        unique_tracks_count = 0
        total_detections_count = 0
        filtered_crossing_indicators: List[Dict[str, Any]] = []

        if target_video_path is not None:
            # 1a. Run BorderVideoJobService with ByteTrack & persistence filtering
            video_service = BorderVideoJobService()
            report_data = await video_service.process_video_file(
                project_id=req.project_id or "00000000-0000-0000-0000-000000000001",
                video_path=str(target_video_path),
                max_frames=req.max_frames,
                frame_stride=req.frame_stride,
                terrain_context=req.terrain_context,
                generate_annotated_video=req.generate_annotated_video,
            )
            annotated_artifact_info = report_data.get("annotated_video_artifact")
            annotated_key = annotated_artifact_info.get("artifact_key") if annotated_artifact_info else None
            last_result = report_data.pop("last_analysis_result", None)

            report_obj = report_data.get("report", {})
            crossing_indicators = report_obj.get("potential_unauthorized_crossing_indicators", [])
            filtered_crossing_indicators = crossing_indicators
            total_detections_count = report_obj.get("detections_summary", {}).get("total_observations", 0)
        else:
            # 1b. Single aerial drone image inference
            img_service = ImageProcessingService()
            last_result = await img_service.analyze_image(
                image_path=str(target_image_path),
                mode="border",
                drone_model="visdrone_only",
                terrain_context=req.terrain_context,
                run_intelligence=req.run_intelligence,
            )
            total_detections_count = len(last_result.detections)
            for idx, d in enumerate(last_result.detections):
                if d.class_name in ("person", "light_vehicle", "truck", "motorbike") and d.confidence >= 0.50:
                    det_id = str(d.track_id) if d.track_id is not None else f"det-{idx + 1}"
                    filtered_crossing_indicators.append({
                        "event_type": "POTENTIAL_UNAUTHORIZED_CROSSING_INDICATOR",
                        "detection_id": det_id,
                        "class_name": d.class_name,
                        "confidence": d.confidence,
                        "terminology": "Potential Unauthorized Crossing Indicator (never uncorroborated infiltration)",
                    })

            # Generate image annotation
            try:
                annotator = AnnotationService()
                annot_res = annotator.annotate_and_store(
                    source_image_path=target_image_path,
                    analysis_result=last_result,
                    project_id=uuid.UUID(req.project_id) if req.project_id and len(req.project_id) == 36 else uuid.UUID("00000000-0000-0000-0000-000000000001"),
                )
                annotated_key = annot_res.artifact_key
                annotated_artifact_info = {
                    "artifact_key": annot_res.artifact_key,
                    "sha256": annot_res.sha256,
                    "mime_type": annot_res.mime_type,
                }
            except Exception as ann_err:
                logger.warning(f"Border image annotation failed: {ann_err}")

        # 2. Authoritative Boundary Contract Check (Step 19)
        boundary_svc = InternationalBoundaryService(session)
        border_contract = await boundary_svc.get_border_contract_status()
        authoritative_border_status = border_contract.acquisition_status.value

        # Geodesic proximity if georeferenced
        border_proximity_info: Optional[Dict[str, Any]] = None
        has_coords = req.latitude is not None and req.longitude is not None
        if has_coords:
            prox_res = await boundary_svc.resolve_border_proximity(
                latitude=float(req.latitude),  # type: ignore[arg-type]
                longitude=float(req.longitude),  # type: ignore[arg-type]
            )
            border_proximity_info = prox_res.model_dump()

        # 3. Weather context via Open-Meteo if coordinates provided
        weather_info: Optional[Dict[str, Any]] = None
        if has_coords:
            try:
                weather_svc = ExternalWeatherService()
                w_rec = await weather_svc.get_weather(
                    latitude=float(req.latitude),  # type: ignore[arg-type]
                    longitude=float(req.longitude),  # type: ignore[arg-type]
                )
                weather_info = w_rec.model_dump()
            except Exception as w_err:
                logger.warning(f"Border weather lookup degraded: {w_err}")
                weather_info = {"status": "UNAVAILABLE", "error": str(w_err)}
        else:
            weather_info = {"status": "UNAVAILABLE", "reason": "No geographic coordinates for sensor position."}

        # 4. Deterministic Threat/Priority Bucketing
        # Priority rules: CRITICAL >= 0.75, HIGH >= 0.50, MEDIUM >= 0.25
        num_indicators = len(filtered_crossing_indicators)
        if num_indicators >= 3:
            det_priority = AdvisoryPriority.CRITICAL
        elif num_indicators >= 1:
            det_priority = AdvisoryPriority.HIGH
        elif total_detections_count > 0:
            det_priority = AdvisoryPriority.MEDIUM
        else:
            det_priority = AdvisoryPriority.LOW

        standard_protocol = get_protocol("border", "person")

        # 5. Build Grounded Evidence Package for Mistral
        evidence_package = {
            "mode": "BORDER_SECURITY",
            "detection_count": total_detections_count,
            "crossing_indicators_count": num_indicators,
            "indicators": filtered_crossing_indicators,
            "authoritative_border_status": authoritative_border_status,
            "border_contract_message": border_contract.status_message,
            "sensor_coordinates": {"latitude": req.latitude, "longitude": req.longitude} if has_coords else None,
            "border_proximity": border_proximity_info,
            "weather_status": weather_info.get("status") if weather_info else "UNAVAILABLE",
            "limitations": [
                "A detection alone is NOT a confirmed infiltration event.",
                "Authoritative Survey of India boundary data is NOT acquired; proximity claims are suspended.",
                "Operational zone alerts reflect configured BorderZone parameters, not official international frontier geometry.",
            ],
        }

        # 6. Generate Grounded Mistral Advisory
        mistral_client = MistralAdvisoryClient()
        advisory = await mistral_client.generate_grounded_advisory(
            mode="BORDER_SECURITY",
            evidence_package=evidence_package,
            standard_protocol=standard_protocol,
            deterministic_priority=det_priority,
        )

        # 7. Persistence
        persist_info: Optional[Dict[str, Any]] = None
        if last_result is not None:
            persist_info = await _safely_persist_result(
                result=last_result,
                project_id_str=req.project_id,
                situation_id_str=req.situation_id,
                annotated_artifact_key=annotated_key,
                user_id_str=payload.get("sub"),
                org_id_str=payload.get("org"),
            )

        e2e_response = {
            "mode": "BORDER_SECURITY",
            "detection_count": total_detections_count,
            "potential_unauthorized_crossing_indicators": filtered_crossing_indicators,
            "indicators_count": num_indicators,
            "authoritative_border_contract": {
                "operational_border_available": border_contract.operational_border_available,
                "acquisition_status": border_contract.acquisition_status.value,
                "status_message": border_contract.status_message,
                "reason_unavailable": border_contract.reason_unavailable,
            },
            "border_proximity": border_proximity_info,
            "external_context": {
                "weather": weather_info,
            },
            "annotated_artifact": annotated_artifact_info,
            "advisory": advisory.model_dump(),
            "persistence": persist_info,
            "limitations": advisory.limitations,
        }

        meta = MetaBlock(
            timestamp=utc_now_iso(),
            request_id=_extract_request_id(request),
            version=settings.API_VERSION,
        )
        return ResponseEnvelope(success=True, data=e2e_response, meta=meta)

    finally:
        if is_temp:
            target = target_video_path or target_image_path
            if target and target.exists():
                try:
                    target.unlink(missing_ok=True)
                    if target.parent.exists():
                        shutil.rmtree(target.parent, ignore_errors=True)
                except Exception as exc:
                    logger.warning(f"Error cleaning up temp file {target}: {exc}")


# ============================================================================
# STEP 27 & 28 — ASYNCHRONOUS JOB PIPELINES & LIFECYCLE MANAGEMENT
# ============================================================================

class CreateDisasterJobRequest(BaseModel):
    project_id: Optional[str] = Field(default="00000000-0000-0000-0000-000000000001")
    situation_id: Optional[str] = Field(default=None)
    before_image_path: Optional[str] = Field(default=None)
    after_image_path: Optional[str] = Field(default=None)
    before_base64: Optional[str] = Field(default=None)
    after_base64: Optional[str] = Field(default=None)
    threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    evacuation_dest_lat: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    evacuation_dest_lon: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    radius_km: float = Field(default=15.0, ge=0.5, le=100.0)
    idempotency_key: Optional[str] = Field(default=None, description="Client-provided key to guarantee idempotent submission")


class CreateBorderJobRequest(BaseModel):
    project_id: Optional[str] = Field(default="00000000-0000-0000-0000-000000000001")
    situation_id: Optional[str] = Field(default=None)
    video_path: Optional[str] = Field(default=None)
    video_base64: Optional[str] = Field(default=None)
    image_path: Optional[str] = Field(default=None)
    image_base64: Optional[str] = Field(default=None)
    max_frames: Optional[int] = Field(default=30, ge=1, le=300)
    frame_stride: int = Field(default=5, ge=1, le=30)
    terrain_context: Optional[str] = Field(default="arid")
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    generate_annotated_video: bool = Field(default=True)
    idempotency_key: Optional[str] = Field(default=None, description="Client-provided key to guarantee idempotent submission")


async def _run_disaster_job_pipeline(job_id: str, req: CreateDisasterJobRequest, user_id: Optional[str], org_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Executes the 9-stage disaster analysis lifecycle:
    SUBMITTED -> VALIDATING -> QUEUED -> PROCESSING -> ENRICHING -> GENERATING_ADVISORY -> GENERATING_ARTIFACTS -> PERSISTING -> COMPLETED
    """
    settings = get_settings()
    mgr = default_job_manager
    temp_dirs: List[Path] = []
    limitations: List[str] = []

    try:
        # Stage 1: VALIDATING
        await mgr.update_progress(job_id, stage=JobStatus.VALIDATING.value, progress_percent=10, status=JobStatus.VALIDATING)

        before_path: Optional[Path] = None
        after_path: Optional[Path] = None

        if req.before_image_path and req.after_image_path:
            bp = Path(req.before_image_path)
            ap = Path(req.after_image_path)
            if not bp.exists():
                raise ValidationError(f"Pre-disaster image does not exist: {req.before_image_path}")
            if not ap.exists():
                raise ValidationError(f"Post-disaster image does not exist: {req.after_image_path}")
            before_path = bp
            after_path = ap
        elif req.before_base64 and req.after_base64:
            before_path = _write_temp_base64(req.before_base64, field_name="before_base64")
            after_path = _write_temp_base64(req.after_base64, field_name="after_base64")
            temp_dirs.extend([before_path.parent, after_path.parent])
        else:
            raise ValidationError("Both before and after image sources are required for disaster job.")

        # Validate pair structural compatibility (BUG-006)
        validation_res = DamagePairValidator.validate_pair(str(before_path), str(after_path))

        # Stage 2: QUEUED
        await mgr.update_progress(job_id, stage=JobStatus.QUEUED.value, progress_percent=20, status=JobStatus.QUEUED)

        # Stage 3: PROCESSING (Inference)
        await mgr.update_progress(job_id, stage=JobStatus.PROCESSING.value, progress_percent=30, status=JobStatus.PROCESSING)
        damage_service = DamageAnalysisService()
        runtime_result: AERIONAnalysisResult = await damage_service.analyze_damage_pair(
            before_path=str(before_path),
            after_path=str(after_path),
            threshold=req.threshold,
            run_intelligence=False,
        )
        analysis_id = str(runtime_result.analysis_id)
        await mgr.update_progress(job_id, stage=JobStatus.PROCESSING.value, progress_percent=45, analysis_id=analysis_id)

        damage_analysis = runtime_result.damage_analysis
        damage_pixels = getattr(damage_analysis, "damage_pixels", 0)
        damage_ratio = getattr(damage_analysis, "damage_ratio", 0.0)
        damage_percentage = getattr(damage_analysis, "damage_percentage", 0.0)

        # Stage 4: ENRICHING (Geospatial & External APIs)
        await mgr.update_progress(job_id, stage=JobStatus.ENRICHING.value, progress_percent=55, status=JobStatus.ENRICHING)
        has_coords = req.latitude is not None and req.longitude is not None
        administrative_context = None
        seismic_events: List[Dict[str, Any]] = []
        shelters: List[Dict[str, Any]] = []
        buildings_count = 0
        infrastructure_count = 0
        weather_data: Dict[str, Any] = {"status": "UNAVAILABLE", "reason": "No coordinates provided."}
        route_data: Dict[str, Any] = {"status": "UNAVAILABLE", "reason": "No coordinates provided."}

        if has_coords:
            lat = float(req.latitude)  # type: ignore[arg-type]
            lon = float(req.longitude)  # type: ignore[arg-type]
            try:
                geo_svc = GeospatialService()
                admin_res = await geo_svc.reverse_geocode(latitude=lat, longitude=lon)
                if admin_res.matched:
                    administrative_context = {
                        "state_name": admin_res.state_name,
                        "district_name": admin_res.district_name,
                        "state_code": admin_res.state_code,
                        "district_code": admin_res.district_code,
                    }
                seismic_events = await geo_svc.query_historical_hazards(latitude=lat, longitude=lon, radius_km=req.radius_km, limit=10)
                shelter_svc = ShelterService()
                shelters = await shelter_svc.query_shelters_proximity(latitude=lat, longitude=lon, radius_km=req.radius_km, limit=5)
            except Exception as g_err:
                logger.warning(f"Job {job_id} geospatial enrichment degraded: {g_err}")
                limitations.append(f"Geospatial enrichment partially degraded: {g_err}")

            # Weather
            try:
                weather_svc = ExternalWeatherService()
                w_rec = await weather_svc.get_weather(latitude=lat, longitude=lon)
                weather_data = w_rec.model_dump()
            except Exception as w_err:
                logger.warning(f"Job {job_id} weather degraded: {w_err}")
                weather_data = {"status": "UNAVAILABLE", "reason": str(w_err)}
                limitations.append("Live weather data unavailable.")

            # Routing
            dest_lat = req.evacuation_dest_lat
            dest_lon = req.evacuation_dest_lon
            if (dest_lat is None or dest_lon is None) and shelters:
                dest_loc = shelters[0].get("location") or {}
                dest_lat = dest_loc.get("latitude") if isinstance(dest_loc, dict) else getattr(dest_loc, "latitude", None)
                dest_lon = dest_loc.get("longitude") if isinstance(dest_loc, dict) else getattr(dest_loc, "longitude", None)

            if dest_lat is not None and dest_lon is not None:
                try:
                    routing_svc = ExternalRoutingService()
                    r_rec = await routing_svc.calculate_route(origin_lat=lat, origin_lon=lon, dest_lat=dest_lat, dest_lon=dest_lon)
                    route_data = r_rec.model_dump()
                except Exception as r_err:
                    logger.warning(f"Job {job_id} routing degraded: {r_err}")
                    route_data = {"status": "UNAVAILABLE", "reason": str(r_err)}
                    limitations.append("Evacuation routing service unavailable.")
            else:
                route_data = {"status": "UNAVAILABLE", "reason": "No evacuation destination coordinates."}
        else:
            limitations.append("Geographic coordinates unavailable; external and spatial enrichment skipped.")

        # Stage 5: GENERATING_ADVISORY (Mistral Intelligence)
        await mgr.update_progress(job_id, stage=JobStatus.GENERATING_ADVISORY.value, progress_percent=70, status=JobStatus.GENERATING_ADVISORY)
        if damage_ratio >= 0.75:
            det_priority = AdvisoryPriority.CRITICAL
        elif damage_ratio >= 0.50:
            det_priority = AdvisoryPriority.HIGH
        elif damage_ratio >= 0.25:
            det_priority = AdvisoryPriority.MEDIUM
        else:
            det_priority = AdvisoryPriority.LOW

        evidence_package = {
            "analysis_id": analysis_id,
            "mode": "DISASTER_RESPONSE",
            "coordinates": {"latitude": req.latitude, "longitude": req.longitude} if has_coords else None,
            "damage_evaluations_count": 1,
            "damage_pixels": damage_pixels,
            "mean_damage_ratio": damage_ratio,
            "damage_percentage": damage_percentage,
            "administrative_context": administrative_context,
            "historical_hazards_count": len(seismic_events),
            "shelters_count": len(shelters),
            "weather_status": weather_data.get("status"),
            "routing_status": route_data.get("status"),
            "limitations": limitations + [
                "Road blockage cannot be inferred solely from adjacent structural damage.",
                "Shelter operational status reflects registered dataset records.",
            ],
        }

        mistral_client = MistralAdvisoryClient()
        advisory = await mistral_client.generate_grounded_advisory(
            mode="DISASTER_RESPONSE",
            evidence_package=evidence_package,
            standard_protocol=get_protocol("disaster", "building_damage"),
            deterministic_priority=det_priority,
        )

        # Stage 6: GENERATING_ARTIFACTS
        await mgr.update_progress(job_id, stage=JobStatus.GENERATING_ARTIFACTS.value, progress_percent=85, status=JobStatus.GENERATING_ARTIFACTS)
        annotated_damage_key: Optional[str] = None
        damage_artifact_info: Optional[Dict[str, Any]] = None
        damage_mask_b64: Optional[str] = None
        try:
            proj_uuid = uuid.UUID(req.project_id) if req.project_id and len(req.project_id) == 36 else uuid.UUID("00000000-0000-0000-0000-000000000001")
            annotator = AnnotationService()
            annot_res = annotator.render_damage_overlay_and_store(
                after_image_path=after_path,
                before_image_path=before_path,
                damage_analysis=runtime_result.damage_analysis,
                project_id=proj_uuid,
            )
            annotated_damage_key = annot_res.artifact_key
            damage_mask_b64 = annot_res.annotated_base64
            damage_artifact_info = {
                "artifact_key": annot_res.artifact_key,
                "mime_type": annot_res.mime_type,
                "sha256": annot_res.sha256,
                "size_bytes": annot_res.file_size_bytes,
                "image_width": annot_res.image_width,
                "image_height": annot_res.image_height,
                "is_zero_damage": annot_res.is_zero_detection,
            }
        except Exception as annot_exc:
            logger.warning(f"Damage overlay artifact generation failed in disaster job: {annot_exc}")

        # Stage 7: PERSISTING
        await mgr.update_progress(job_id, stage=JobStatus.PERSISTING.value, progress_percent=92, status=JobStatus.PERSISTING)
        persist_info = await _safely_persist_result(
            result=runtime_result,
            project_id_str=req.project_id,
            situation_id_str=req.situation_id,
            annotated_artifact_key=annotated_damage_key,
            existing_job_id_str=job_id,
            user_id_str=user_id,
            org_id_str=org_id,
        )

        final_status = JobStatus.COMPLETED_WITH_LIMITATIONS if limitations else JobStatus.COMPLETED
        await mgr.update_progress(
            job_id,
            stage=final_status.value,
            progress_percent=100,
            status=final_status,
            analysis_id=analysis_id,
            limitations=limitations,
        )

        return {
            "job_id": job_id,
            "analysis_id": analysis_id,
            "mode": "DISASTER_RESPONSE",
            "damage_analysis": {
                "damage_pixels": damage_pixels,
                "damage_ratio": damage_ratio,
                "damage_percentage": damage_percentage,
                "threshold_applied": req.threshold,
            },
            "pair_validation": validation_res.to_dict(),
            "damage_mask_base64": damage_mask_b64,
            "damage_artifact": damage_artifact_info,
            "geospatial_context": {
                "administrative": administrative_context,
                "seismic_events": seismic_events,
                "shelters": shelters,
            },
            "external_context": {
                "weather": weather_data,
                "routing": route_data,
            },
            "advisory": advisory.model_dump(),
            "persistence": persist_info,
            "limitations": advisory.limitations + limitations,
        }

    finally:
        for tdir in temp_dirs:
            try:
                if tdir.exists():
                    shutil.rmtree(tdir, ignore_errors=True)
            except Exception as exc:
                logger.warning(f"Error cleaning up temp dir {tdir}: {exc}")


async def _run_border_job_pipeline(job_id: str, req: CreateBorderJobRequest, user_id: Optional[str], org_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Executes the 9-stage border analysis lifecycle:
    SUBMITTED -> VALIDATING -> QUEUED -> PROCESSING -> ENRICHING -> GENERATING_ADVISORY -> GENERATING_ARTIFACTS -> PERSISTING -> COMPLETED
    """
    settings = get_settings()
    mgr = default_job_manager
    temp_dirs: List[Path] = []
    limitations: List[str] = []

    try:
        # Stage 1: VALIDATING
        await mgr.update_progress(job_id, stage=JobStatus.VALIDATING.value, progress_percent=10, status=JobStatus.VALIDATING)

        target_path: Optional[Path] = None
        is_video = False

        if req.video_path:
            vp = Path(req.video_path)
            if not vp.exists():
                raise ValidationError(f"Border video file does not exist: {req.video_path}")
            target_path = vp
            is_video = True
        elif req.video_base64:
            target_path = write_temp_base64_file(req.video_base64, suffix=".mp4", max_bytes=MAX_VIDEO_B64_BYTES, field_name="video_base64")
            temp_dirs.append(target_path.parent)
            is_video = True
        elif req.image_path:
            ip = Path(req.image_path)
            if not ip.exists():
                raise ValidationError(f"Border image file does not exist: {req.image_path}")
            target_path = ip
            is_video = False
        elif req.image_base64:
            target_path = _write_temp_base64(req.image_base64, field_name="image_base64")
            temp_dirs.append(target_path.parent)
            is_video = False
        else:
            raise ValidationError("Either video or image input source must be provided for border job.")

        # Stage 2: QUEUED
        await mgr.update_progress(job_id, stage=JobStatus.QUEUED.value, progress_percent=20, status=JobStatus.QUEUED)

        # Stage 3: PROCESSING (Inference & Tracking)
        await mgr.update_progress(job_id, stage=JobStatus.PROCESSING.value, progress_percent=30, status=JobStatus.PROCESSING)

        analysis_id = str(uuid.uuid4())
        total_detections_count = 0
        crossing_indicators: List[Dict[str, Any]] = []
        annotated_artifact_info: Optional[Dict[str, Any]] = None
        annotated_key: Optional[str] = None
        last_result: Optional[AERIONAnalysisResult] = None

        if is_video:
            border_job_service = BorderVideoJobService()
            report_data = await border_job_service.process_video_file(
                project_id=req.project_id or "00000000-0000-0000-0000-000000000001",
                video_path=str(target_path),
                max_frames=req.max_frames,
                frame_stride=req.frame_stride,
                terrain_context=req.terrain_context,
                generate_annotated_video=req.generate_annotated_video,
            )
            annotated_video_res = report_data.get("annotated_video_artifact") or report_data.get("annotated_video")
            if annotated_video_res:
                if isinstance(annotated_video_res, dict):
                    annotated_artifact_info = annotated_video_res
                    annotated_key = annotated_video_res.get("artifact_key")
                else:
                    annotated_artifact_info = {
                        "artifact_key": getattr(annotated_video_res, "artifact_key", None),
                        "sha256": getattr(annotated_video_res, "sha256", None),
                        "file_size_bytes": getattr(annotated_video_res, "file_size_bytes", 0),
                        "mime_type": "video/mp4",
                    }
                    annotated_key = getattr(annotated_video_res, "artifact_key", None)
            total_detections_count = report_data.get("total_detections_count", 0)
            crossing_indicators = report_data.get("potential_unauthorized_crossing_indicators", [])
            last_result = report_data.get("last_analysis_result")
            if last_result:
                analysis_id = str(last_result.analysis_id)
        else:
            img_service = ImageProcessingService()
            runtime_result = await img_service.analyze_image(
                image_path=str(target_path),
                drone_model="visdrone_only",
                terrain_context=req.terrain_context,
                run_intelligence=False,
            )
            analysis_id = str(runtime_result.analysis_id)
            total_detections_count = len(runtime_result.detections)
            last_result = runtime_result

        await mgr.update_progress(job_id, stage=JobStatus.PROCESSING.value, progress_percent=55, analysis_id=analysis_id)

        # Stage 4: ENRICHING (Geospatial & Boundary Verification)
        await mgr.update_progress(job_id, stage=JobStatus.ENRICHING.value, progress_percent=65, status=JobStatus.ENRICHING)
        boundary_svc = InternationalBoundaryService()
        try:
            border_contract = await boundary_svc.get_border_contract_status()
        except Exception as b_err:
            logger.warning(f"Border contract check failed for job {job_id}: {b_err}")
            from app.schemas.geospatial import BorderContractStatus, BorderAcquisitionStatus
            border_contract = BorderContractStatus(
                operational_border_available=False,
                acquisition_status=BorderAcquisitionStatus.NOT_ACQUIRED,
                authoritative_source_name="Survey of India (SOI)",
                status_message=f"Border contract check degraded: {b_err}",
            )
            limitations.append("Authoritative border verification database query degraded.")

        has_coords = req.latitude is not None and req.longitude is not None
        border_proximity_info = None
        weather_info: Optional[Dict[str, Any]] = None

        if has_coords:
            prox_res = await boundary_svc.resolve_border_proximity(
                latitude=float(req.latitude),  # type: ignore[arg-type]
                longitude=float(req.longitude),  # type: ignore[arg-type]
            )
            border_proximity_info = prox_res.model_dump()
            try:
                weather_svc = ExternalWeatherService()
                w_rec = await weather_svc.get_weather(latitude=float(req.latitude), longitude=float(req.longitude))  # type: ignore[arg-type]
                weather_info = w_rec.model_dump()
            except Exception as w_err:
                logger.warning(f"Border job {job_id} weather degraded: {w_err}")
                weather_info = {"status": "UNAVAILABLE", "error": str(w_err)}
                limitations.append("Live weather data unavailable.")
        else:
            limitations.append("Sensor coordinates not provided; border proximity and weather skipped.")

        # Stage 5: GENERATING_ADVISORY (Mistral Intelligence)
        await mgr.update_progress(job_id, stage=JobStatus.GENERATING_ADVISORY.value, progress_percent=75, status=JobStatus.GENERATING_ADVISORY)
        num_indicators = len(crossing_indicators)
        if num_indicators >= 3:
            det_priority = AdvisoryPriority.CRITICAL
        elif num_indicators >= 1:
            det_priority = AdvisoryPriority.HIGH
        elif total_detections_count > 0:
            det_priority = AdvisoryPriority.MEDIUM
        else:
            det_priority = AdvisoryPriority.LOW

        evidence_package = {
            "mode": "BORDER_SECURITY",
            "detection_count": total_detections_count,
            "crossing_indicators_count": num_indicators,
            "indicators": crossing_indicators,
            "authoritative_border_status": border_contract.acquisition_status.value,
            "border_contract_message": border_contract.status_message,
            "sensor_coordinates": {"latitude": req.latitude, "longitude": req.longitude} if has_coords else None,
            "border_proximity": border_proximity_info,
            "weather_status": weather_info.get("status") if weather_info else "UNAVAILABLE",
            "limitations": limitations + [
                "A detection alone is NOT a confirmed infiltration event.",
                "Authoritative Survey of India boundary data is NOT acquired; proximity claims are suspended.",
                "Operational zone alerts reflect configured BorderZone parameters, not official international frontier geometry.",
            ],
        }

        mistral_client = MistralAdvisoryClient()
        advisory = await mistral_client.generate_grounded_advisory(
            mode="BORDER_SECURITY",
            evidence_package=evidence_package,
            standard_protocol=get_protocol("border", "person"),
            deterministic_priority=det_priority,
        )

        # Stage 6: GENERATING_ARTIFACTS
        await mgr.update_progress(job_id, stage=JobStatus.GENERATING_ARTIFACTS.value, progress_percent=85, status=JobStatus.GENERATING_ARTIFACTS)

        # Stage 7: PERSISTING
        await mgr.update_progress(job_id, stage=JobStatus.PERSISTING.value, progress_percent=92, status=JobStatus.PERSISTING)
        persist_info: Optional[Dict[str, Any]] = None
        if last_result is not None:
            persist_info = await _safely_persist_result(
                result=last_result,
                project_id_str=req.project_id,
                situation_id_str=req.situation_id,
                annotated_artifact_key=annotated_key,
                existing_job_id_str=job_id,
                user_id_str=user_id,
                org_id_str=org_id,
            )

        final_status = JobStatus.COMPLETED_WITH_LIMITATIONS if limitations else JobStatus.COMPLETED
        await mgr.update_progress(
            job_id,
            stage=final_status.value,
            progress_percent=100,
            status=final_status,
            analysis_id=analysis_id,
            limitations=limitations,
        )

        res_dict: Dict[str, Any] = {
            "job_id": job_id,
            "analysis_id": analysis_id,
            "mode": "BORDER_SECURITY",
            "detection_count": total_detections_count,
            "potential_unauthorized_crossing_indicators": crossing_indicators,
            "indicators_count": num_indicators,
            "authoritative_border_contract": {
                "operational_border_available": border_contract.operational_border_available,
                "acquisition_status": border_contract.acquisition_status.value,
                "status_message": border_contract.status_message,
            },
            "border_proximity": border_proximity_info,
            "external_context": {"weather": weather_info},
            "annotated_artifact": annotated_artifact_info,
            "annotated_video_artifact": annotated_artifact_info if is_video else None,
            "advisory": advisory.model_dump(),
            "persistence": persist_info,
            "limitations": advisory.limitations + limitations,
        }

        if is_video and 'report_data' in locals():
            res_dict["processed_frames"] = report_data.get("processed_frames")
            res_dict["total_video_frames"] = report_data.get("total_video_frames")
            res_dict["all_detections"] = report_data.get("all_detections", [])
            res_dict["tracks"] = report_data.get("tracks", [])
            res_dict["unique_tracks_count"] = report_data.get("unique_tracks_count", 0)
            res_dict["report"] = report_data.get("report")

        return res_dict

    finally:
        for tdir in temp_dirs:
            try:
                if tdir.exists():
                    shutil.rmtree(tdir, ignore_errors=True)
            except Exception as exc:
                logger.warning(f"Error cleaning up temp dir {tdir}: {exc}")


@router.post(
    "/jobs/disaster",
    response_model=ResponseEnvelope[Dict[str, Any]],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit an asynchronous Disaster Mode analysis job with idempotency and fine-grained lifecycle tracking",
)
async def submit_disaster_job(
    req: CreateDisasterJobRequest,
    request: Request,
    payload: dict = Depends(get_current_user_payload),
) -> ResponseEnvelope[Dict[str, Any]]:
    settings = get_settings()
    user_id = payload.get("sub")

    org_id = payload.get("org")

    async def job_runner(jid: str):
        return await _run_disaster_job_pipeline(jid, req, user_id, org_id)

    record = await default_job_manager.submit_job(
        task_name="disaster_analysis_pipeline",
        coro_fn=job_runner,
        mode="disaster",
        project_id=req.project_id,
        user_id=user_id,
        input_asset_reference=req.before_image_path or req.after_image_path or "base64_pair",
        idempotency_key=req.idempotency_key,
        initial_status=JobStatus.SUBMITTED,
        pass_job_context=True,
    )

    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(
        success=True,
        data=record.to_dict(),
        meta=meta,
    )


@router.post(
    "/jobs/border",
    response_model=ResponseEnvelope[Dict[str, Any]],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit an asynchronous Border Security Mode analysis job with idempotency and fine-grained lifecycle tracking",
)
async def submit_border_job(
    req: CreateBorderJobRequest,
    request: Request,
    payload: dict = Depends(get_current_user_payload),
) -> ResponseEnvelope[Dict[str, Any]]:
    settings = get_settings()
    user_id = payload.get("sub")

    org_id = payload.get("org")

    async def job_runner(jid: str):
        return await _run_border_job_pipeline(jid, req, user_id, org_id)

    record = await default_job_manager.submit_job(
        task_name="border_analysis_pipeline",
        coro_fn=job_runner,
        mode="border",
        project_id=req.project_id,
        user_id=user_id,
        input_asset_reference=req.video_path or req.image_path or "base64_asset",
        idempotency_key=req.idempotency_key,
        initial_status=JobStatus.SUBMITTED,
        pass_job_context=True,
    )

    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(
        success=True,
        data=record.to_dict(),
        meta=meta,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=ResponseEnvelope[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Inspect status, progress, stage, and result of an asynchronous analysis job",
)
async def get_job_status(
    job_id: str,
    request: Request,
    payload: dict = Depends(get_current_user_payload),
) -> ResponseEnvelope[Dict[str, Any]]:
    settings = get_settings()
    record = await default_job_manager.get_job(job_id)
    if not record:
        raise ResourceNotFoundError(f"Analysis job not found: {job_id}")

    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(
        success=True,
        data=record.to_dict(),
        meta=meta,
    )


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=ResponseEnvelope[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Cancel an active asynchronous analysis job safely without orphaned artifacts",
)
async def cancel_job_endpoint(
    job_id: str,
    request: Request,
    payload: dict = Depends(get_current_user_payload),
) -> ResponseEnvelope[Dict[str, Any]]:
    settings = get_settings()
    record = await default_job_manager.get_job(job_id)
    if not record:
        raise ResourceNotFoundError(f"Analysis job not found: {job_id}")

    cancelled = await default_job_manager.cancel_job(job_id)
    record = await default_job_manager.get_job(job_id)

    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(
        success=True,
        data={
            "job_id": job_id,
            "cancelled": cancelled,
            "status": record.status.value if record else "UNKNOWN",
            "current_stage": record.current_stage if record else "UNKNOWN",
        },
        meta=meta,
    )


@router.get(
    "/jobs",
    response_model=ResponseEnvelope[List[Dict[str, Any]]],
    status_code=status.HTTP_200_OK,
    summary="List recent analysis jobs for the authenticated tenant",
)
async def list_jobs_endpoint(
    request: Request,
    limit: int = 50,
    status_filter: Optional[str] = None,
    project_id: Optional[str] = None,
    payload: dict = Depends(get_current_user_payload),
) -> ResponseEnvelope[List[Dict[str, Any]]]:
    settings = get_settings()
    user_id = payload.get("sub")

    s_enum = None
    if status_filter:
        try:
            s_enum = JobStatus(status_filter)
        except ValueError:
            pass

    records = await default_job_manager.list_jobs(
        limit=min(max(1, limit), 100),
        status=s_enum,
        project_id=project_id,
        user_id=user_id,
    )

    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(
        success=True,
        data=[r.to_dict() for r in records],
        meta=meta,
    )


@router.get(
    "/history",
    response_model=ResponseEnvelope[List[Dict[str, Any]]],
    status_code=status.HTTP_200_OK,
    summary="List persisted analyses and background jobs for the authenticated organization",
)
async def list_analysis_history(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    mode: Optional[str] = None,
    status: Optional[str] = None,
    payload: dict = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_async_session),
) -> ResponseEnvelope[List[Dict[str, Any]]]:
    """
    Returns user-scoped and tenant-isolated analysis history from the database.
    Falls back cleanly to JobManager records if database is unreachable.
    Guarantees tenant isolation: User A cannot see User B's analyses from a different organization.
    """
    settings = get_settings()
    org_id_str = payload.get("org")
    user_id_str = payload.get("sub")
    effective_org_id = uuid.UUID(org_id_str) if org_id_str and len(org_id_str) == 36 else uuid.UUID("00000000-0000-0000-0000-000000000001")

    history_items: List[Dict[str, Any]] = []

    try:
        job_repo = AnalysisJobRepository(session)
        db_jobs = await job_repo.list_by_organization(
            organization_id=effective_org_id,
            limit=min(max(1, limit), 100),
            offset=max(0, offset),
            mode=mode,
            status=status,
        )

        for job in db_jobs:
            # Check for linked analysis result
            stmt = select(DBAnalysisResult).where(DBAnalysisResult.job_id == job.id)
            res = await session.execute(stmt)
            ar = res.scalar_one_or_none()

            raw_payload = ar.raw_payload if ar and isinstance(ar.raw_payload, dict) else {}
            summary = {
                "critical": ar.summary_critical if ar else 0,
                "high": ar.summary_high if ar else 0,
                "medium": ar.summary_medium if ar else 0,
                "low": ar.summary_low if ar else 0,
            }

            analysis_id_str = str(ar.analysis_id) if ar else None

            # Check for damage metrics in raw_payload
            damage_summary = None
            if raw_payload.get("damage_analysis"):
                dmg = raw_payload["damage_analysis"]
                damage_summary = {
                    "damage_percentage": dmg.get("damage_percentage", 0.0),
                    "damage_pixels": dmg.get("damage_pixels", 0),
                    "total_pixels": dmg.get("total_pixels", 0),
                    "mean_damage_probability": dmg.get("probability_mean", 0.0),
                    "classification": dmg.get("classification", "NO_DAMAGE"),
                }

            history_items.append({
                "job_id": str(job.id),
                "analysis_id": analysis_id_str,
                "mode": job.mode,
                "status": job.status,
                "current_stage": job.current_stage or job.status,
                "progress_percent": job.progress_percent,
                "input_asset_reference": job.input_asset_reference,
                "limitations": job.limitations or [],
                "error_message": job.error_message,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "summary": summary,
                "detections_count": len(raw_payload.get("detections", [])) if "detections" in raw_payload else None,
                "damage_summary": damage_summary,
                "has_result": ar is not None,
            })

    except Exception as db_exc:
        logger.warning(f"Could not retrieve analysis history from DB ({db_exc}); falling back to JobManager memory.")
        # Fallback to JobManager
        records = await default_job_manager.list_jobs(
            limit=min(max(1, limit), 100),
            status=JobStatus(status) if status else None,
            user_id=user_id_str,
        )
        for r in records:
            if mode and r.mode != mode:
                continue
            history_items.append({
                "job_id": r.job_id,
                "analysis_id": r.analysis_id,
                "mode": r.mode or "border",
                "status": r.status.value,
                "current_stage": r.current_stage,
                "progress_percent": r.progress_percent,
                "input_asset_reference": r.input_asset_reference,
                "limitations": r.limitations,
                "error_message": r.error,
                "started_at": r.started_at,
                "completed_at": r.completed_at,
                "created_at": r.created_at,
                "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                "detections_count": None,
                "damage_summary": None,
                "has_result": r.result is not None,
            })

    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=history_items, meta=meta)


@router.get(
    "/{analysis_id}",
    response_model=ResponseEnvelope[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Retrieve canonical persisted analysis result by stable ID with tenant authorization",
)
async def get_analysis_by_id(
    analysis_id: str,
    request: Request,
    payload: dict = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_async_session),
) -> ResponseEnvelope[Dict[str, Any]]:
    """
    Retrieves the canonical analysis result and metadata by either analysis_id (UUID) or job_id (UUID/string).
    Enforces tenant authorization: verifies that the analysis belongs to the user's organization.
    """
    settings = get_settings()
    org_id_str = payload.get("org")
    effective_org_id = uuid.UUID(org_id_str) if org_id_str and len(org_id_str) == 36 else uuid.UUID("00000000-0000-0000-0000-000000000001")

    # Try parsing as UUID
    parsed_uuid: Optional[uuid.UUID] = None
    try:
        parsed_uuid = uuid.UUID(analysis_id)
    except ValueError:
        pass

    db_result: Optional[DBAnalysisResult] = None
    db_job: Optional[DBAnalysisJob] = None

    if parsed_uuid:
        try:
            # First attempt: lookup by analysis_id with tenant scoping
            result_repo = AnalysisResultRepository(session)
            db_result = await result_repo.get_by_analysis_id_scoped(parsed_uuid, effective_org_id)

            if not db_result:
                # Second attempt: check if parsed_uuid matches a job_id for this tenant
                job_repo = AnalysisJobRepository(session)
                db_job = await job_repo.get_by_id_scoped(parsed_uuid, effective_org_id)
                if db_job:
                    stmt = select(DBAnalysisResult).where(DBAnalysisResult.job_id == db_job.id)
                    res = await session.execute(stmt)
                    db_result = res.scalar_one_or_none()
        except Exception:
            db_result = None

    if db_result is not None:
        payload_data = dict(db_result.raw_payload) if isinstance(db_result.raw_payload, dict) else {}
        # Ensure analysis_id and job_id are populated
        payload_data["analysis_id"] = str(db_result.analysis_id)
        payload_data["job_id"] = str(db_result.job_id)
        payload_data["overall_status"] = db_result.overall_status

        # If annotated_artifact is not already in payload_data, lookup from evidence lineage
        if not payload_data.get("annotated_artifact") and db_job:
            try:
                ev_stmt = select(DBEvidenceRecord).where(
                    (DBEvidenceRecord.project_id == db_job.project_id) &
                    (DBEvidenceRecord.raw_payload_uri.is_not(None))
                ).order_by(DBEvidenceRecord.created_at.desc())
                ev_rows = (await session.execute(ev_stmt)).scalars().all()
                for ev in ev_rows:
                    uri = ev.raw_payload_uri or ""
                    if "annotated" in uri.lower() or uri.endswith(".jpg") or uri.endswith(".png") or uri.endswith(".mp4"):
                        payload_data["annotated_artifact"] = {
                            "artifact_key": uri,
                            "mime_type": "video/mp4" if uri.endswith(".mp4") else "image/jpeg",
                            "sha256": (ev.sensor_metadata or {}).get("sha256") or "VERIFIED_RECORD",
                        }
                        break
            except Exception as ev_lookup_exc:
                logger.debug(f"Could not load fallback evidence artifact: {ev_lookup_exc}")

        meta = MetaBlock(
            timestamp=utc_now_iso(),
            request_id=_extract_request_id(request),
            version=settings.API_VERSION,
        )
        return ResponseEnvelope(success=True, data=payload_data, meta=meta)

    # Fallback to in-memory JobManager (for active or transient session jobs)
    record = await default_job_manager.get_job_by_id_or_analysis_id(analysis_id)
    if record and record.result:
        # Verify user ownership if user_id was tracked
        sub_id = payload.get("sub")
        if record.user_id and sub_id and record.user_id != sub_id:
            raise ResourceNotFoundError(f"Analysis {analysis_id} not found.")

        result_obj = record.result
        if isinstance(result_obj, dict):
            res_data = dict(result_obj)
        elif hasattr(result_obj, "to_dict"):
            res_data = result_obj.to_dict()
        else:
            res_data = {"result": str(result_obj)}

        meta = MetaBlock(
            timestamp=utc_now_iso(),
            request_id=_extract_request_id(request),
            version=settings.API_VERSION,
        )
        return ResponseEnvelope(success=True, data=res_data, meta=meta)

    raise ResourceNotFoundError(f"Analysis result not found or access denied: {analysis_id}")



