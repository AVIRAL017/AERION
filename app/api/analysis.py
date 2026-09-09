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
from app.schemas.common import MetaBlock, ResponseEnvelope, utc_now_iso
from app.services.annotation_service import AnnotationService
from app.services.application_services import (
    BorderVideoJobService,
    DamageAnalysisService,
    ImageProcessingService,
    SatelliteAnalysisService,
)
from app.services.persistence_service import AnalysisPersistenceService

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

        persister = AnalysisPersistenceService()
        persist_info = await persister.persist_analysis(
            result=result,
            project_id=proj_uuid,
            situation_id=sit_uuid,
            source_asset_key=source_asset_key,
            annotated_artifact_key=annotated_artifact_key,
        )
        persist_info["database_available"] = True
        return persist_info
    except Exception as exc:
        logger.warning(f"Could not persist analysis {result.analysis_id} to database ({exc}); operating in session memory.")
        return {
            "persisted": False,
            "database_available": False,
            "reason": str(exc),
            "analysis_id": str(result.analysis_id),
            "situation_linked": False,
        }



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

    try:
        if req.source_type.lower() == "satellite":
            sat_service = SatelliteAnalysisService()
            result: AERIONAnalysisResult = await sat_service.analyze_satellite_image(
                image_path=str(target_path),
                terrain_context=req.terrain_context,
                run_intelligence=req.run_intelligence,
            )
        else:
            img_service = ImageProcessingService()
            result: AERIONAnalysisResult = await img_service.analyze_image(
                image_path=str(target_path),
                mode=req.mode,
                drone_model=req.drone_model,
                terrain_context=req.terrain_context,
                run_intelligence=req.run_intelligence,
            )

        result_dict = result.to_dict() if hasattr(result, "to_dict") else dict(result)

        # Roadmap Step 15: Annotated Visual Evidence Pipeline
        annotated_artifact_info: Optional[Dict[str, Any]] = None
        annotated_key: Optional[str] = None
        try:
            proj_uuid = uuid.UUID(req.project_id) if req.project_id and len(req.project_id) == 36 else uuid.UUID("00000000-0000-0000-0000-000000000001")
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
            annotated_artifact_key=annotated_key,
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

    try:
        damage_service = DamageAnalysisService()
        result: AERIONAnalysisResult = await damage_service.analyze_damage_pair(
            before_path=str(before_path),
            after_path=str(after_path),
            threshold=req.threshold,
            run_intelligence=req.run_intelligence,
        )
        result_dict = result.to_dict() if hasattr(result, "to_dict") else dict(result)
        persist_info = await _safely_persist_result(
            result=result,
            project_id_str=req.project_id,
            situation_id_str=req.situation_id,
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
            )
            report_data["persistence"] = persist_info

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

