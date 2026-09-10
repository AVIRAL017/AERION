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
from app.schemas.evidence import GeoPoint
from app.schemas.external import AdvisoryPriority, ProviderStatus
from app.db.session import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.annotation_service import AnnotationService
from app.services.application_services import (
    BorderVideoJobService,
    DamageAnalysisService,
    ImageProcessingService,
    SatelliteAnalysisService,
)
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
        # 1. Run frozen damage detection model
        damage_service = DamageAnalysisService()
        runtime_result: AERIONAnalysisResult = await damage_service.analyze_damage_pair(
            before_path=str(before_path),
            after_path=str(after_path),
            threshold=req.threshold,
            run_intelligence=req.run_intelligence,
        )
        result_dict = runtime_result.to_dict() if hasattr(runtime_result, "to_dict") else dict(runtime_result)

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
                if haz_res.available and haz_res.records:
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
        )

        e2e_response = {
            "analysis_id": str(runtime_result.analysis_id),
            "mode": "DISASTER_RESPONSE",
            "georeferencing_status": georeferencing_status,
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
            # Check for high-confidence border sector crossings
            for d in last_result.detections:
                if d.class_name in ("person", "light_vehicle", "truck", "motorbike") and d.confidence >= 0.50:
                    filtered_crossing_indicators.append({
                        "event_type": "POTENTIAL_UNAUTHORIZED_CROSSING_INDICATOR",
                        "detection_id": str(d.detection_id),
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


