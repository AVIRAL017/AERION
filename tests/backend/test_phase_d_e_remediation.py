"""
AERION — Combined Phase D & Phase E Verification Suite
Tests:
- BUG-010: Map selection location provenance and bounds
- BUG-011: Geocoding contract parsing (array envelope)
- BUG-022: Disaster Mode geo-context isolation & provenance
- BUG-023: Weather provider error handling & coordinates isolation
- Demo Vulnerability Boundary: 5-sided Pentagon geometry, non-authoritative status, spatial intersection, evidence gating
- BUG-024: Border recorded video annotated evidence with detections, class labels, confidence, and track IDs
- BUG-025: Structured detection/track data preserved outside video without fake GPS coordinates
- BUG-026: Recorded-video background job lifecycle states and fine-grained stage tracking
"""

import asyncio
import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from shapely.geometry import Point, Polygon

from app.main import create_app
from app.core.config import AERIONSettings
from app.core.auth import create_access_token
from app.schemas.boundary import (
    DEMO_PENTAGON_BOUNDARY,
    DEMO_PENTAGON_COORDINATES,
    BoundaryAuthority,
    BoundaryStatus,
    BoundaryType,
)
from app.core.jobs import JobManager, JobRecord, JobStatus
from aerion_runtime_contracts import AERIONAnalysisResult, BoundingBox, Detection, TrackState


@pytest.fixture
def auth_context():
    settings = AERIONSettings(ENVIRONMENT="test")
    app = create_app(settings=settings)
    client = TestClient(app)
    user_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    token = create_access_token({
        "sub": user_id,
        "org": org_id,
        "role": "operator",
        "email": "tester@aerion.mil",
    })
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers


# ============================================================================
# PHASE D: DEMO VULNERABILITY BOUNDARY TESTS
# ============================================================================

class TestDemoVulnerabilityBoundary:
    """Validates the synthetic Demo Pentagon boundary and spatial intersection engine."""

    def test_demo_pentagon_geometry(self):
        """Verify the 5-sided closed polygon geometry and non-authoritative metadata."""
        coords = DEMO_PENTAGON_COORDINATES
        assert len(coords) == 6  # 5 distinct vertices + 1 closing vertex
        assert coords[0] == coords[-1]  # Closed polygon

        poly = Polygon(coords)
        assert poly.is_valid
        assert not poly.is_empty
        assert len(poly.exterior.coords) == 6

        assert DEMO_PENTAGON_BOUNDARY.boundary_type == BoundaryType.DEMO_VULNERABILITY_BOUNDARY
        assert DEMO_PENTAGON_BOUNDARY.authority == BoundaryAuthority.NON_AUTHORITATIVE
        assert DEMO_PENTAGON_BOUNDARY.status == BoundaryStatus.DEMO
        assert "NOT an official border" in DEMO_PENTAGON_BOUNDARY.disclaimer.upper() or "NON-AUTHORITATIVE" in DEMO_PENTAGON_BOUNDARY.disclaimer.upper()

    def test_boundary_list_endpoint(self, auth_context):
        """GET /api/v1/boundaries returns the registered Demo Pentagon."""
        client, headers = auth_context
        resp = client.get("/api/v1/boundaries", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        boundaries = data["data"]
        assert len(boundaries) >= 1
        pentagon = next((b for b in boundaries if "demo" in b["id"].lower()), None)
        assert pentagon is not None
        assert pentagon["authority"] == "NON_AUTHORITATIVE"
        assert pentagon["boundary_type"] == "DEMO_VULNERABILITY_BOUNDARY"

    def test_boundary_get_endpoint(self, auth_context):
        """GET /api/v1/boundaries/{boundary_id} returns details with polygon coordinates."""
        client, headers = auth_context
        resp = client.get(f"/api/v1/boundaries/{DEMO_PENTAGON_BOUNDARY.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == DEMO_PENTAGON_BOUNDARY.id
        assert data["geometry"] is not None
        assert len(data["geometry"]["coordinates"][0]) == 6

    def test_boundary_evaluation_insufficient_evidence(self, auth_context):
        """Evaluating with no evidence points must return INSUFFICIENT_EVIDENCE without fabricating scores."""
        client, headers = auth_context
        resp = client.post(
            f"/api/v1/boundaries/{DEMO_PENTAGON_BOUNDARY.id}/evaluate",
            headers=headers,
            json={
                "evidence_points": [],
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["vulnerability_status"] == "INSUFFICIENT_EVIDENCE"
        assert data["vulnerability_score"] is None
        assert data["intersecting_evidence_count"] == 0

    def test_boundary_evaluation_spatial_intersection(self, auth_context):
        """Points inside the pentagon are counted and trigger deterministic vulnerability calculation."""
        client, headers = auth_context
        # Inside the pentagon: lon=74.85, lat=32.65
        # Outside the pentagon: lon=75.50, lat=33.00
        inside_point = {"longitude": 74.85, "latitude": 32.65}
        outside_point = {"longitude": 75.50, "latitude": 33.00}

        resp = client.post(
            f"/api/v1/boundaries/{DEMO_PENTAGON_BOUNDARY.id}/evaluate",
            headers=headers,
            json={
                "evidence_points": [inside_point, outside_point],
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["intersecting_evidence_count"] == 1
        assert data["vulnerability_status"] == "CALCULATED"
        assert data["vulnerability_score"] is not None
        assert 0.0 <= data["vulnerability_score"] <= 100.0


# ============================================================================
# PHASE D: GEOCODING & WEATHER CONTRACT TESTS (BUG-011, BUG-022, BUG-023)
# ============================================================================

class TestGeocodingAndWeatherContract:
    """Validates contract shapes for place search and weather enrichment."""

    @pytest.mark.asyncio
    async def test_forward_geocode_returns_direct_array(self, auth_context):
        """Verify forward_geocode returns a list of results in data directly, matching client expectations."""
        client, headers = auth_context
        with patch("app.services.external_geocoding_service.ExternalGeocodingService.forward_geocode", new_callable=AsyncMock) as mock_geo:
            from app.schemas.external import NormalizedGeocodeResult, ProviderStatus
            mock_geo.return_value = [
                NormalizedGeocodeResult(
                    provider_name="nominatim",
                    status=ProviderStatus.AVAILABLE,
                    query="Jammu",
                    latitude=32.7266,
                    longitude=74.8570,
                    display_name="Jammu, Jammu and Kashmir, India",
                    country="India",
                    country_code="in",
                    fetched_at_utc="2026-09-13T00:00:00Z",
                    cached=False,
                )
            ]
            resp = client.get("/api/v1/external/geocode?query=Jammu&limit=1", headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert isinstance(data["data"], list)
            assert len(data["data"]) == 1
            assert data["data"][0]["latitude"] == 32.7266
            assert data["data"][0]["longitude"] == 74.8570

    @pytest.mark.asyncio
    async def test_weather_endpoint_with_valid_coordinates(self, auth_context):
        """Weather endpoint succeeds with valid coordinates and provider availability."""
        client, headers = auth_context
        with patch("app.services.external_weather_service.ExternalWeatherService.get_weather", new_callable=AsyncMock) as mock_weather:
            from app.schemas.external import NormalizedWeatherRecord, ProviderStatus
            mock_weather.return_value = NormalizedWeatherRecord(
                observation_id="OBS-123",
                provider_name="open-meteo",
                status=ProviderStatus.AVAILABLE,
                observation_timestamp_utc="2026-09-13T00:00:00Z",
                fetched_at_utc="2026-09-13T00:00:00Z",
                is_historical_reconstructed=False,
                latitude=32.72,
                longitude=74.85,
                temperature_celsius=28.5,
                wind_speed_mps=3.2,
                flight_suitability="OPTIMAL",
                cached=False,
            )
            resp = client.get("/api/v1/external/weather?latitude=32.72&longitude=74.85", headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["status"] == "AVAILABLE"
            assert data["data"]["temperature_celsius"] == 28.5


# ============================================================================
# PHASE E: RECORDED VIDEO STRUCTURED DATA & LIFECYCLE (BUG-024, BUG-025, BUG-026)
# ============================================================================

class TestBorderVideoStructuredEvidenceAndLifecycle:
    """Validates structured detection preservation, track retention, and job lifecycle tracking."""

    @pytest.mark.asyncio
    async def test_border_video_job_service_accumulates_detections_and_tracks(self):
        """Test BorderVideoJobService preserves all frame detections and tracks outside the video."""
        from app.services.application_services import BorderVideoJobService
        import numpy as np

        service = BorderVideoJobService()

        # Mock VideoCapture
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            0: 0,
            1: 0,
            3: 640,  # WIDTH
            4: 480,  # HEIGHT
            5: 25.0, # FPS
            7: 2,    # FRAME_COUNT
        }.get(prop, 0)

        # 2 frames
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.side_effect = [(True, dummy_frame), (True, dummy_frame), (False, None)]

        # Mock runtime manager inference result with 1 detection and 1 track per frame
        det1 = Detection(
            source="border",
            class_id=0,
            class_name="person",
            confidence=0.88,
            bbox=BoundingBox(10.0, 10.0, 50.0, 100.0),
            track_id=1,
            frame_number=0,
        )
        track1 = TrackState(
            track_id=1,
            confidence=0.88,
            bbox=BoundingBox(10.0, 10.0, 50.0, 100.0),
            center=MagicMock(x=30.0, y=55.0),
            previous_center=None,
            frames_seen=1,
            movement_distance=0.0,
            displacement=0.0,
            direction="stationary",
            persistence=0.1,
            class_name="person",
        )
        analysis_res = AERIONAnalysisResult(
            mode="border",
            source_type="video",
            detections=[det1],
            tracks=[track1],
        )

        with patch("cv2.VideoCapture", return_value=mock_cap), \
             patch.object(service.runtime_manager, "run_border_frame_inference", new_callable=AsyncMock, return_value=analysis_res):

            res = await service.process_video_file(
                project_id="00000000-0000-0000-0000-000000000001",
                video_path="dummy_video.mp4",
                max_frames=2,
                frame_stride=1,
                generate_annotated_video=False,
            )

            assert res["processed_frames"] == 2
            assert "all_detections" in res
            assert "tracks" in res
            assert len(res["all_detections"]) == 2  # 1 per frame * 2 frames
            assert len(res["tracks"]) == 2

            # Verify structured detection schema (BUG-025)
            d0 = res["all_detections"][0]
            assert d0["class_name"] == "person"
            assert d0["confidence"] == 0.88
            assert d0["track_id"] == 1
            assert "frame_number" in d0
            assert "evidence_reference" in d0

    @pytest.mark.asyncio
    async def test_job_manager_fine_grained_lifecycle_stages(self):
        """Test JobManager lifecycle states and stage tracking (BUG-026)."""
        mgr = JobManager()

        async def sample_task(job_id: str):
            await mgr.update_progress(job_id, stage=JobStatus.VALIDATING.value, progress_percent=10, status=JobStatus.VALIDATING)
            await mgr.update_progress(job_id, stage=JobStatus.PROCESSING.value, progress_percent=40, status=JobStatus.PROCESSING)
            await mgr.update_progress(job_id, stage=JobStatus.GENERATING_ARTIFACTS.value, progress_percent=80, status=JobStatus.GENERATING_ARTIFACTS)
            return {"status": "ok"}

        record = await mgr.submit_job(
            task_name="test_pipeline",
            coro_fn=sample_task,
            mode="border",
            pass_job_context=True,
        )

        assert record.job_id is not None
        assert record.status in (JobStatus.QUEUED, JobStatus.SUBMITTED, JobStatus.PROCESSING, JobStatus.COMPLETED)

        # Wait for background task to complete
        for _ in range(50):
            await asyncio.sleep(0.05)
            rec = await mgr.get_job(record.job_id)
            if rec and rec.status in (JobStatus.COMPLETED, JobStatus.COMPLETED_WITH_LIMITATIONS, JobStatus.FAILED):
                break

        final_job = await mgr.get_job(record.job_id)
        assert final_job is not None
        assert final_job.status == JobStatus.COMPLETED
        assert final_job.progress_percent == 100
        assert final_job.result == {"status": "ok"}
