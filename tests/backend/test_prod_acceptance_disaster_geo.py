"""
AERION — Production Acceptance Remediation #2 Tests:
Disaster Geo-Context, Shelter PostGIS Discovery, Real Road Routing, Video Annotation & Multi-Page PDF Report
"""

import base64
import os
import re
import zlib
import cv2
import numpy as np
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from aerion_runtime_contracts import AERIONAnalysisResult, BoundingBox, Detection
from app.services.external_geocoding_service import ExternalGeocodingService, OFFLINE_DISASTER_LOCATIONS
from app.services.external_routing_service import ExternalRoutingService
from app.services.video_annotation_service import VideoAnnotationService
from app.services.pdf_report_generator import generate_situation_report_pdf, FROZEN_MODEL_REGISTRY
from app.schemas.external import ProviderStatus, NormalizedGeocodeResult, NormalizedRouteRecord


@pytest.mark.asyncio
async def test_disaster_geocoding_offline_curated_fallback():
    """Item 1 & 2: Offline curated fallback returns valid WGS84 coordinates for disaster places."""
    service = ExternalGeocodingService()

    # Test with simulated network failure to ensure fallback triggers cleanly
    with patch("httpx.AsyncClient.get", side_effect=Exception("Connection refused")):
        results = await service.forward_geocode("Joshimath", limit=1, use_cache=False)
        assert len(results) == 1
        res = results[0]
        assert res.locality == "Joshimath"
        assert res.state == "Uttarakhand"
        assert abs(res.latitude - 30.5574) < 0.01
        assert abs(res.longitude - 79.5670) < 0.01
        assert res.status == ProviderStatus.AVAILABLE
        assert res.provider_name == "Curated-Offline-Disaster-Registry"


@pytest.mark.asyncio
async def test_disaster_geocoding_multiple_curated_places():
    """Item 2: Curated fallback supports all critical Indian disaster-prone locations."""
    service = ExternalGeocodingService()

    test_queries = ["Chamoli", "Kedarnath", "Uttarkashi", "Wayanad", "Silchar", "Cuttack", "Mandi"]
    with patch("httpx.AsyncClient.get", side_effect=Exception("Offline")):
        for query in test_queries:
            results = await service.forward_geocode(query, limit=1, use_cache=False)
            assert len(results) >= 1, f"Failed to geocode curated place: {query}"
            assert -90.0 <= results[0].latitude <= 90.0
            assert -180.0 <= results[0].longitude <= 180.0


@pytest.mark.asyncio
async def test_disaster_reverse_geocoding_curated_fallback():
    """Item 3: Reverse geocoding resolves nearest curated place when Nominatim fails."""
    service = ExternalGeocodingService()

    # Joshimath coordinates
    with patch("httpx.AsyncClient.get", side_effect=Exception("Offline")):
        res = await service.reverse_geocode(30.5574, 79.5670, use_cache=False)
        assert res is not None
        assert "Joshimath" in res.display_name or "Chamoli" in res.display_name


@pytest.mark.asyncio
async def test_real_road_routing_zero_straight_line_enforcement():
    """Item 8 & 9: Real road routing via ORS never fabricates straight-line geometry."""
    service = ExternalRoutingService()

    # Mock both ORS and Mapbox as returning HTTP 503
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 503
    mock_post_resp.text = "Service Unavailable"
    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 503
    mock_get_resp.text = "Service Unavailable"

    with patch("httpx.AsyncClient.post", return_value=mock_post_resp), \
         patch("httpx.AsyncClient.get", return_value=mock_get_resp):
        route = await service.calculate_route(
            origin_lat=30.5574,
            origin_lon=79.5670,
            dest_lat=28.6139,
            dest_lon=77.2090,
            use_cache=False,
        )
        assert route.status != ProviderStatus.AVAILABLE
        assert route.total_distance_meters is None
        assert route.total_duration_seconds is None
        assert len(route.warnings) > 0
        assert any("straight-line" in w.lower() for w in route.warnings)


def test_video_annotation_no_center_point_dots():
    """Item 17: Video annotation service renders bounding boxes without center-point dots."""
    service = VideoAnnotationService()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    analysis_res = AERIONAnalysisResult(
        analysis_id="test-uuid-01",
        mode="border",
        source_type="video",
        overall_status="COMPLETED",
        detections=[
            Detection(
                source="model",
                class_id=0,
                class_name="light_vehicle",
                confidence=0.814,
                bbox=BoundingBox(x1=100.0, y1=100.0, x2=200.0, y2=250.0),
                track_id=19,
            )
        ],
    )

    history = {
        19: [{"x": 140.0, "y": 160.0}, {"x": 145.0, "y": 165.0}, {"x": 150.0, "y": 175.0}]
    }

    # Track cv2.circle calls
    circle_calls = []
    original_circle = cv2.circle

    def mock_circle(img, center, radius, color, thickness=-1, **kwargs):
        circle_calls.append({"center": center, "radius": radius})
        return original_circle(img, center, radius, color, thickness, **kwargs)

    with patch("cv2.circle", side_effect=mock_circle):
        annotated = service.annotate_frame(
            canvas=frame,
            analysis_result=analysis_res,
            frame_idx=1,
            total_source_frames=10,
            tracker_history=history,
        )

    # In our updated service, center-point dots are completely removed (circle_calls == 0)
    assert len(circle_calls) == 0, f"Expected 0 center-point dots, but found {len(circle_calls)}"
    assert annotated.shape == (480, 640, 3)


def test_video_annotation_compact_label_format():
    """Item 18: Video annotation service formats labels cleanly and compactly."""
    service = VideoAnnotationService()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    analysis_res = AERIONAnalysisResult(
        analysis_id="test-uuid-02",
        mode="border",
        source_type="video",
        overall_status="COMPLETED",
        detections=[
            Detection(
                source="model",
                class_id=0,
                class_name="light_vehicle",
                confidence=0.81,
                bbox=BoundingBox(x1=50.0, y1=50.0, x2=150.0, y2=150.0),
                track_id=19,
            )
        ],
    )

    put_text_calls = []
    original_put_text = cv2.putText

    def mock_put_text(*args, **kwargs):
        if len(args) > 1:
            put_text_calls.append(str(args[1]))
        elif "text" in kwargs:
            put_text_calls.append(str(kwargs["text"]))
        return original_put_text(*args, **kwargs)

    with patch("cv2.putText", side_effect=mock_put_text):
        service.annotate_frame(
            canvas=frame,
            analysis_result=analysis_res,
            frame_idx=1,
            total_source_frames=10,
        )

    # Verify label was drawn with compact format "CAR 81%" or "LIGHT VEHICLE 81%"
    assert any("81%" in t for t in put_text_calls), f"Label calls: {put_text_calls}"
    # Verify raw decimal format "0.81 ID:" was NOT drawn
    assert not any("0.81 ID:" in t for t in put_text_calls)


def test_disaster_operational_report_structure_and_verification_statement():
    """Item 21: Disaster operational PDF report generates with 4 pages and exact verification statement."""
    damage_mask = np.zeros((256, 256), dtype=np.uint8)
    damage_mask[50:150, 50:150] = 255  # ~15% damaged
    _, buffer = cv2.imencode(".jpg", damage_mask)
    damage_mask_b64 = base64.b64encode(buffer).decode("utf-8")

    report_data = {
        "situation_id": "00000000-0000-0000-0000-000000000002",
        "analysis_id": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
        "job_id": "job-disaster-acceptance-01",
        "mode": "disaster",
        "analysis_type": "damage",
        "overall_status": "COMPLETED",
        "generated_at": "2026-09-18T12:00:00Z",
        "damage_analysis": {
            "damage_percentage": 15.2,
            "damage_pixels": 10000,
            "total_pixels": 65536,
            "damage_ratio": 0.1526,
            "probability_mean": 0.221,
            "classification": "MODERATE",
            "damage_mask_base64": damage_mask_b64,
        },
        "location_context": {
            "latitude": 30.5574,
            "longitude": 79.5670,
            "label": "Chamoli / Joshimath Incident Sector",
            "location_source": "OPERATOR_PROVIDED",
            "location_precision": "APPROXIMATE",
        },
        "shelter_enrichment": {
            "shelters": [
                {
                    "name": "Delhi Regional Safe Haven",
                    "shelter_type": "DISASTER_RELIEF_CENTER",
                    "latitude": 28.6139,
                    "longitude": 77.2090,
                    "distance_km": 303.4,
                    "operational_status": "OPEN",
                    "capacity": 250,
                    "current_occupancy": 85,
                }
            ],
            "total_count": 1,
            "search_radius_km": 500.0,
        },
        "routing_summary": {
            "routes": [
                {
                    "name": "Delhi Regional Corridor",
                    "distance_km": 345.2,
                    "duration_min": 420.0,
                    "is_viable": True,
                    "provider": "OpenRouteService",
                }
            ],
            "route_provider": "OpenRouteService",
        },
        "model_provenance": {
            "model_name": "AERION Bi-Temporal Siamese Damage ResNet-18",
            "sha256": FROZEN_MODEL_REGISTRY["damage"]["sha256"],
            "input_resolution": "512x512",
            "detection_threshold": 0.50,
        },
    }

    pdf_bytes = generate_situation_report_pdf(report_data)

    # 1. Output must be a non-empty PDF
    assert pdf_bytes.startswith(b"%PDF-"), "Generated file must be a valid PDF"
    assert len(pdf_bytes) > 5000, "PDF size too small"

    # 2. Check 4 pages created
    pages_count = len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))
    assert pages_count >= 4, f"Expected at least 4 pages, got {pages_count}"

    # 3. Extract uncompressed character streams
    stream_texts = []
    for stream in re.findall(rb"stream[\r\n]+(.*?)[\r\n]+endstream", pdf_bytes, re.DOTALL):
        try:
            dec = zlib.decompress(stream).decode("latin-1", "ignore")
            chars = "".join(re.findall(r"\((.*?)\)", dec))
            stream_texts.append(chars)
        except Exception:
            pass
    all_text = " ".join(stream_texts)
    # Normalize font ligature
    normalized_text = all_text.replace("\x00", "fi")

    # 4. Verify exact mandatory statements in decompressed PDF text
    assert "AERION AI Perception Services" in normalized_text, "AERION AI Perception Services must be in report"
    assert "HUMAN VERIFICATION" in normalized_text, "HUMAN VERIFICATION header must be in report"
    assert "advisory and require human verification" in normalized_text
    assert "personnel before operational action" in normalized_text

    # 5. Check Siamese damage model SHA-256 is embedded
    model_hash = FROZEN_MODEL_REGISTRY["damage"]["sha256"]
    assert model_hash in normalized_text or model_hash.encode("ascii") in pdf_bytes
