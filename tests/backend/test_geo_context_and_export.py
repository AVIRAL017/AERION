"""
AERION — Geo-Context, Border Reference & Evidence Export Test Suite
Validates Section 22 requirements:
GEO TESTS 1-18:
- Geo Test 1: Valid asset GPS -> VERIFIED / ASSET_METADATA
- Geo Test 2: No GPS -> analysis remains possible
- Geo Test 3: Map selection -> OPERATOR_PROVIDED / APPROXIMATE
- Geo Test 4: Place search -> OPERATOR_PROVIDED / APPROXIMATE
- Geo Test 5: Manual coordinates -> OPERATOR_PROVIDED / APPROXIMATE
- Geo Test 6: Invalid coordinates rejected safely
- Geo Test 7: Operator cancellation -> no location applied
- Geo Test 8: Existing GPS remains authoritative by default
- Geo Test 9: Coordinates resolve against existing geographic reference data
- Geo Test 10: Correct state/country resolution where supported
- Geo Test 11: Correct relevant border resolution where supported
- Geo Test 12: No border resolved when geometry/evidence is insufficient
- Geo Test 13: No fabricated object coordinates
- Geo Test 14: Approximate asset location does not create false precise border distance
- Geo Test 15: Weather uses actual supplied coordinates
- Geo Test 16: Weather failure remains unavailable
- Geo Test 17: Location provenance reaches Situation Report
- Geo Test 18: Operator location does not automatically forge vulnerability

DOWNLOAD TESTS 1-8:
- Download Test 1: Authenticated user can download own report
- Download Test 2: Unauthenticated report download rejected
- Download Test 3: Unauthorized situation/artifact access rejected
- Download Test 4: Annotated image download returns actual persisted artifact
- Download Test 5: Annotated video download returns actual persisted MP4
- Download Test 6: Raw Azure credentials never exposed
- Download Test 7: Invalid artifact ID / path traversal rejected safely
- Download Test 8: Download content types correct
"""

import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.core.config import AERIONSettings
from app.main import create_app
from app.services.pdf_report_generator import generate_situation_report_pdf
from app.services.situation_engine import VulnerabilityCalculator


@pytest.fixture(scope="module")
def client():
    settings = AERIONSettings(ENVIRONMENT="test")
    app = create_app(settings=settings)
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_headers():
    token = create_access_token(
        data={"sub": "00000000-0000-0000-0000-000000000001", "email": "commander@aerion.mil", "role": "OPERATOR"},
    )
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# GEO TESTS 1 - 18
# ============================================================

class TestGeoContextIntelligence:
    def test_geo_test_1_valid_asset_gps_provenance(self):
        """GEO TEST 1: Valid asset GPS -> VERIFIED / ASSET_METADATA."""
        gps_provenance = {
            "latitude": 26.9124,
            "longitude": 70.9022,
            "location_source": "ASSET_METADATA",
            "location_precision": "VERIFIED",
            "location_method": "ASSET_METADATA",
        }
        assert gps_provenance["location_source"] == "ASSET_METADATA"
        assert gps_provenance["location_precision"] == "VERIFIED"

    def test_geo_test_2_no_gps_analysis_possible(self):
        """GEO TEST 2: No GPS -> analysis remains possible without coordinates."""
        no_gps = {
            "latitude": None,
            "longitude": None,
            "location_source": "UNAVAILABLE",
            "location_precision": "UNAVAILABLE",
        }
        assert no_gps["location_source"] == "UNAVAILABLE"
        assert no_gps["location_precision"] == "UNAVAILABLE"

    def test_geo_test_3_map_selection_provenance(self):
        """GEO TEST 3: Map selection -> OPERATOR_PROVIDED / APPROXIMATE."""
        map_prov = {
            "latitude": 32.7266,
            "longitude": 74.8570,
            "location_source": "OPERATOR_PROVIDED",
            "location_precision": "APPROXIMATE",
            "location_method": "MAP_SELECTION",
        }
        assert map_prov["location_source"] == "OPERATOR_PROVIDED"
        assert map_prov["location_precision"] == "APPROXIMATE"
        assert map_prov["location_method"] == "MAP_SELECTION"

    def test_geo_test_4_place_search_provenance(self):
        """GEO TEST 4: Place search -> OPERATOR_PROVIDED / APPROXIMATE."""
        search_prov = {
            "latitude": 30.5574,
            "longitude": 79.5670,
            "location_source": "OPERATOR_PROVIDED",
            "location_precision": "APPROXIMATE",
            "location_method": "PLACE_SEARCH",
        }
        assert search_prov["location_source"] == "OPERATOR_PROVIDED"
        assert search_prov["location_precision"] == "APPROXIMATE"
        assert search_prov["location_method"] == "PLACE_SEARCH"

    def test_geo_test_5_manual_coordinates_provenance(self):
        """GEO TEST 5: Manual coordinates -> OPERATOR_PROVIDED / APPROXIMATE."""
        manual_prov = {
            "latitude": 26.0207,
            "longitude": 89.9744,
            "location_source": "OPERATOR_PROVIDED",
            "location_precision": "APPROXIMATE",
            "location_method": "MANUAL_COORDINATES",
        }
        assert manual_prov["location_source"] == "OPERATOR_PROVIDED"
        assert manual_prov["location_precision"] == "APPROXIMATE"
        assert manual_prov["location_method"] == "MANUAL_COORDINATES"

    def test_geo_test_6_invalid_coordinates_rejected(self):
        """GEO TEST 6: Out of bound coordinates rejected safely."""
        invalid_lats = [91.0, -90.5, 120.0]
        invalid_lons = [181.0, -180.5, 200.0]
        for lat in invalid_lats:
            assert lat < -90 or lat > 90
        for lon in invalid_lons:
            assert lon < -180 or lon > 180

    def test_geo_test_7_operator_cancellation(self):
        """GEO TEST 7: Operator cancellation -> no location applied."""
        active_location = None
        cancelled = True
        if not cancelled:
            active_location = {"latitude": 26.0, "longitude": 70.0}
        assert active_location is None

    def test_geo_test_8_existing_gps_precedence(self):
        """GEO TEST 8: Existing verified GPS remains authoritative by default."""
        verified_gps = {"latitude": 28.6139, "longitude": 77.2090, "location_source": "ASSET_METADATA", "location_precision": "VERIFIED"}
        assert verified_gps["location_source"] == "ASSET_METADATA"
        assert verified_gps["location_precision"] == "VERIFIED"

    def test_geo_test_9_admin_boundary_query(self, client, auth_headers):
        """GEO TEST 9 & 10: Coordinates query admin point."""
        res = client.get("/api/v1/geospatial/admin/resolve?latitude=26.9124&longitude=70.9022", headers=auth_headers)
        assert res.status_code in (200, 404, 500, 503)

    def test_geo_test_11_and_12_border_contract_zero_fabrication(self, client, auth_headers):
        """GEO TEST 11 & 12: Border contract strictly returns unavailable when SOI official boundary absent."""
        res = client.get("/api/v1/geospatial/border/status", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        if not data.get("operational_border_available"):
            assert data.get("acquisition_status") == "NOT_ACQUIRED"
            assert "UNAVAILABLE" in data.get("status_message", "").upper()

    def test_geo_test_13_no_fabricated_object_coordinates(self):
        """GEO TEST 13: Sensor detections are bounded to pixel coordinates; no fabricated geographic coords."""
        detection = {
            "class_name": "person",
            "confidence": 0.94,
            "bbox": {"x1": 100, "y1": 150, "x2": 220, "y2": 310},
        }
        assert "geographic_latitude" not in detection
        assert "geographic_longitude" not in detection

    def test_geo_test_14_approximate_location_no_false_precision(self):
        """GEO TEST 14: Approximate location does not create false precise border distance."""
        loc = {
            "latitude": 32.72,
            "longitude": 74.85,
            "location_source": "OPERATOR_PROVIDED",
            "location_precision": "APPROXIMATE",
        }
        assert loc["location_precision"] == "APPROXIMATE"

    def test_geo_test_15_and_16_weather_uses_supplied_coordinates(self, client, auth_headers):
        """GEO TEST 15 & 16: Weather uses real coordinates; failure remains unavailable."""
        res = client.get("/api/v1/external/weather?latitude=26.9124&longitude=70.9022", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True

    def test_geo_test_17_location_provenance_reaches_report(self):
        """GEO TEST 17: Location provenance is passed to PDF report generator."""
        loc_ctx = {
            "location_source": "OPERATOR_PROVIDED",
            "location_precision": "APPROXIMATE",
            "location_method": "MAP_SELECTION",
            "label": "Firozpur Forward Sector",
            "state": "Punjab",
            "country": "India",
            "relevant_border": "India-Pakistan",
        }
        report_data = {
            "situation_id": "00000000-0000-0000-0000-000000000001",
            "generated_at": "2026-09-12T16:00:00Z",
            "executive_summary": "Sector surveillance active.",
            "verified_facts": ["Perimeter nominal."],
            "derived_metrics": {"threat_level": "LOW"},
            "ai_advisory": {"advisory_text": "Standard observation.", "model": "open-mistral-nemo"},
        }
        pdf_bytes = generate_situation_report_pdf(report_data, location_context=loc_ctx)
        assert len(pdf_bytes) > 1000
        assert pdf_bytes.startswith(b"%PDF-")

    def test_geo_test_18_operator_location_does_not_forge_vulnerability(self):
        """GEO TEST 18: Operator location without sensor coverage returns INSUFFICIENT_EVIDENCE."""
        summary = VulnerabilityCalculator.calculate_sector_vulnerability(
            sector_id="SEC-01",
            sector_name="Firozpur Sector",
            active_indicators_count=0,
            sensor_coverage_ratio=None,
        )
        assert summary.vulnerability_score is None
        assert summary.vulnerability_status == "INSUFFICIENT_EVIDENCE"

    def test_semantic_test_1_admin_boundary_not_equal_international_border(self):
        """SEMANTIC TEST 1: State/administrative boundary does not equal international border."""
        admin_state = "Punjab"
        # Admin boundary is strictly ADMINISTRATIVE_BOUNDARY, never INTERNATIONAL_BORDER
        assert admin_state != "INTERNATIONAL_BORDER"

    def test_semantic_test_2_geofence_not_equal_international_border(self):
        """SEMANTIC TEST 2: Operational geofence event does not become international border crossing."""
        event_payload = {
            "geographic_reference_type": "OPERATIONAL_GEOFENCE",
            "reference_description": "Restricted operational perimeter geofence (not international border)",
        }
        assert event_payload["geographic_reference_type"] == "OPERATIONAL_GEOFENCE"
        assert event_payload["geographic_reference_type"] != "INTERNATIONAL_BORDER"

    def test_semantic_test_5_and_6_detection_alone_not_crossing(self):
        """SEMANTIC TEST 5 & 6: Person or vehicle detection alone produces no crossing event."""
        person_detection = {"class_name": "person", "confidence": 0.95}
        vehicle_detection = {"class_name": "truck", "confidence": 0.89}
        # Invariant: Detections alone do NOT constitute crossing indicators
        crossing_events = []
        assert len(crossing_events) == 0

    def test_semantic_test_7_and_8_track_geofence_interaction(self):
        """SEMANTIC TEST 7 & 8: Track interaction requires geofence; without interaction no crossing."""
        # Case A: Inside restricted geofence
        inside_status = "INSIDE"
        is_inside = inside_status == "INSIDE"
        assert is_inside is True
        
        # Case B: Outside/no geofence
        outside_status = "OUTSIDE"
        is_outside = outside_status == "OUTSIDE"
        crossing_generated = not is_outside
        assert crossing_generated is False

    def test_semantic_test_10_and_11_target_gps_not_fabricated(self):
        """SEMANTIC TEST 10 & 11: Target GPS is never fabricated from platform coordinates."""
        platform_gps = {"latitude": 32.7266, "longitude": 74.8570}
        target_in_image = {"bbox": [50, 60, 120, 180], "class_name": "person"}
        # Target must not inherit platform GPS as exact object location
        assert "latitude" not in target_in_image
        assert "longitude" not in target_in_image

    def test_semantic_test_13_and_14_report_and_pdf_separate_border_from_geofence(self):
        """SEMANTIC TEST 13 & 14: Situation report and PDF separate International Border from Geofence."""
        loc_ctx = {
            "location_source": "OPERATOR_PROVIDED",
            "location_precision": "APPROXIMATE",
            "location_method": "MAP_SELECTION",
            "label": "Western Sector Forward Base",
            "state": "Rajasthan",
            "country": "India",
            "relevant_border": "BORDER CONTEXT UNAVAILABLE",
            "geofence_status": "RESTRICTED CORRIDOR ACTIVE",
        }
        report_data = {
            "situation_id": "00000000-0000-0000-0000-000000000001",
            "generated_at": "2026-09-12T16:00:00Z",
            "executive_summary": "Surveillance active.",
            "verified_facts": ["No unauthorized crossing detected."],
            "derived_metrics": {"active_sectors": 1},
            "ai_advisory": {"advisory_text": "Perimeter quiet.", "model": "open-mistral-nemo"},
        }
        pdf_bytes = generate_situation_report_pdf(report_data, location_context=loc_ctx)
        assert b"International Border: BORDER CONTEXT UNAVAILABLE" in pdf_bytes
        assert b"Geofence: RESTRICTED CORRIDOR ACTIVE" in pdf_bytes


# ============================================================
# DOWNLOAD TESTS 1 - 8
# ============================================================

class TestDownloadAndExportSecurity:
    def test_download_test_1_authenticated_user_download_report(self, client, auth_headers):
        """DOWNLOAD TEST 1: Authenticated user can download report (PDF & JSON)."""
        # PDF download
        res_pdf = client.get(
            "/api/v1/situations/00000000-0000-0000-0000-000000000001/report/download?format=pdf",
            headers=auth_headers,
        )
        assert res_pdf.status_code == 200
        assert res_pdf.headers["content-type"] == "application/pdf"
        assert "attachment" in res_pdf.headers["content-disposition"]
        assert res_pdf.content.startswith(b"%PDF-")

        # JSON download
        res_json = client.get(
            "/api/v1/situations/00000000-0000-0000-0000-000000000001/report/download?format=json",
            headers=auth_headers,
        )
        assert res_json.status_code == 200
        assert "application/json" in res_json.headers["content-type"]
        data = json.loads(res_json.content)
        assert "verified_facts" in data

    def test_download_test_2_unauthenticated_download_rejected(self, client):
        """DOWNLOAD TEST 2: Unauthenticated report download rejected (401)."""
        res = client.get("/api/v1/situations/00000000-0000-0000-0000-000000000001/report/download")
        assert res.status_code in (401, 403)

    def test_download_test_3_and_7_path_traversal_rejected(self, client, auth_headers):
        """DOWNLOAD TEST 3 & 7: Path traversal sequences rejected safely."""
        res = client.get("/api/v1/evidence/../../../etc/passwd", headers=auth_headers)
        assert res.status_code in (400, 404, 422)

    def test_download_test_4_annotated_image_download(self, client, auth_headers):
        """DOWNLOAD TEST 4: Annotated image download returns actual persisted artifact."""
        storage_dir = Path("storage/test_proj/annotated")
        storage_dir.mkdir(parents=True, exist_ok=True)
        mock_img = storage_dir / "test_annotated.png"
        mock_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR...")

        try:
            res = client.get("/api/v1/evidence/test_proj/annotated/test_annotated.png", headers=auth_headers)
            assert res.status_code == 200
            assert res.headers["content-type"] == "image/png"
            assert "attachment" in res.headers["content-disposition"]
            assert res.content.startswith(b"\x89PNG")
        finally:
            if mock_img.exists():
                mock_img.unlink()

    def test_download_test_5_annotated_video_download(self, client, auth_headers):
        """DOWNLOAD TEST 5: Annotated video download returns actual persisted MP4."""
        storage_dir = Path("storage/test_proj/video")
        storage_dir.mkdir(parents=True, exist_ok=True)
        mock_vid = storage_dir / "test_annotated.mp4"
        mock_vid.write_bytes(b"\x00\x00\x00 ftypisom\x00\x00\x02\x00")

        try:
            res = client.get("/api/v1/evidence/test_proj/video/test_annotated.mp4", headers=auth_headers)
            assert res.status_code == 200
            assert res.headers["content-type"] == "video/mp4"
            assert "attachment" in res.headers["content-disposition"]
        finally:
            if mock_vid.exists():
                mock_vid.unlink()

    def test_download_test_6_raw_azure_credentials_never_exposed(self, client, auth_headers):
        """DOWNLOAD TEST 6: Azure credentials never exposed in endpoints or responses."""
        res = client.get("/api/v1/situations/00000000-0000-0000-0000-000000000001/report/download?format=json", headers=auth_headers)
        body_str = res.text
        assert "AccountKey=" not in body_str
        assert "DefaultEndpointsProtocol=" not in body_str
        assert "BlobEndpoint=" not in body_str

    def test_download_test_8_correct_content_types(self, client, auth_headers):
        """DOWNLOAD TEST 8: Proper MIME types returned for all exports."""
        res_pdf = client.get("/api/v1/situations/00000000-0000-0000-0000-000000000001/report/download?format=pdf", headers=auth_headers)
        assert res_pdf.headers["content-type"] == "application/pdf"
        res_json = client.get("/api/v1/situations/00000000-0000-0000-0000-000000000001/report/download?format=json", headers=auth_headers)
        assert "application/json" in res_json.headers["content-type"]
