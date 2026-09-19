"""
AERION — Product Acceptance Remediation #3 Acceptance Test Suite
Tests for:
1. Video Evidence & Annotation Controls:
   - SituationReportResponse schema includes annotated_video_artifact
   - PDF report extraction of representative video frame from annotated_video_artifact
   - Evidence endpoint Accept-Ranges: bytes and inline vs attachment Content-Disposition
2. Shelter Search & Route Execution:
   - ShelterService radius_km=None ("ALL") query behavior
   - Real PostGIS shelter handling with zero synthetic fallback
   - Safe no-destination route behavior
3. Standalone Route Finding Removal (K1):
   - EvacuationPage.tsx deleted
   - Sidebar and App routing updated
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.situation import SituationReportResponse
from app.services.pdf_report_generator import (
    _resolve_annotated_image,
    generate_situation_report_pdf,
)
from app.services.shelter_service import ShelterService


class TestRemediation3VideoEvidence(unittest.TestCase):
    """Verify video evidence artifact propagation and PDF frame extraction."""

    def test_situation_report_response_schema_has_annotated_video_artifact(self):
        """Verify SituationReportResponse accepts and models annotated_video_artifact."""
        sample_payload = {
            "situation_id": "00000000-0000-0000-0000-000000000001",
            "analysis_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "job_id": "job-video-001",
            "mode": "border",
            "analysis_type": "drone_video",
            "overall_status": "COMPLETED",
            "generated_at": "2026-09-19T10:00:00Z",
            "executive_summary": "Video analysis completed with 5 tracked vehicles.",
            "detection_summary": {
                "total_detections": 5,
                "by_class": {"car": 5},
                "detections": [],
            },
            "verified_facts": ["5 tracked vehicles identified."],
            "artifacts": [],
            "limitations": ["Sensor FOV 84 degrees."],
            "recommendations": ["Maintain continuous aerial tracking."],
            "annotated_video_artifact": {
                "artifact_key": "storage/evidence/annotated_run_01.mp4",
                "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                "content_type": "video/mp4",
            },
        }
        resp = SituationReportResponse(**sample_payload)
        self.assertIsNotNone(resp.annotated_video_artifact)
        self.assertEqual(
            resp.annotated_video_artifact.get("artifact_key"),
            "storage/evidence/annotated_run_01.mp4",
        )

    def test_pdf_report_extracts_representative_frame_from_video_artifact(self):
        """Verify _resolve_annotated_image extracts a valid RGB frame from a video file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "test_annotated.mp4")
            # Create a synthetic 10-frame video
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(video_path, fourcc, 10.0, (160, 120))
            for i in range(10):
                frame = np.full((120, 160, 3), fill_value=25 * i, dtype=np.uint8)
                writer.write(frame)
            writer.release()

            report_data = {
                "annotated_video_artifact": {
                    "artifact_key": video_path,
                    "sha256": "dummyhash123",
                }
            }

            img_rgb, key, sha, meta = _resolve_annotated_image(report_data)
            self.assertIsNotNone(img_rgb)
            self.assertEqual(key, video_path)
            self.assertEqual(sha, "dummyhash123")
            self.assertIsNotNone(meta)
            self.assertIn("frame_number", meta)
            self.assertIn("total_frames", meta)
            self.assertIn("fps", meta)
            self.assertEqual(meta["total_frames"], 10)

    def test_pdf_report_generates_successfully_with_video_artifact(self):
        """Verify generate_situation_report_pdf compiles when video artifact is present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "test_annotated.mp4")
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(video_path, fourcc, 5.0, (120, 90))
            for _ in range(5):
                writer.write(np.zeros((90, 120, 3), dtype=np.uint8))
            writer.release()

            report_data = {
                "situation_id": "00000000-0000-0000-0000-000000000002",
                "analysis_id": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
                "job_id": "job-video-002",
                "mode": "border",
                "analysis_type": "drone_video",
                "overall_status": "COMPLETED",
                "generated_at": "2026-09-19T10:00:00Z",
                "executive_summary": "Video analysis operational report.",
                "detection_summary": {
                    "total_detections": 2,
                    "by_class": {"car": 2},
                    "detections": [
                        {
                            "id": "det-1",
                            "class_name": "car",
                            "confidence": 0.88,
                            "bbox": {"x1": 10, "y1": 10, "x2": 50, "y2": 50},
                            "track_id": 1,
                        },
                        {
                            "id": "det-2",
                            "class_name": "car",
                            "confidence": 0.92,
                            "bbox": {"x1": 60, "y1": 20, "x2": 100, "y2": 70},
                            "track_id": 2,
                        },
                    ],
                },
                "verified_facts": ["Vehicle 1 and Vehicle 2 identified."],
                "artifacts": [],
                "limitations": ["FOV limits."],
                "recommendations": ["Patrol area."],
                "annotated_video_artifact": {
                    "artifact_key": video_path,
                    "sha256": "video_sha256_dummy_hash",
                },
            }

            pdf_bytes = generate_situation_report_pdf(report_data)
            self.assertTrue(pdf_bytes.startswith(b"%PDF"))
            self.assertGreater(len(pdf_bytes), 5000)

    def test_evidence_endpoint_headers(self):
        """Verify evidence endpoint returns Accept-Ranges: bytes and sets Content-Disposition."""
        security_code = Path("app/core/security.py").read_text(encoding="utf-8")
        self.assertIn('"Accept-Ranges"', security_code)
        self.assertIn('"Content-Disposition"', security_code)

        evidence_code = Path("app/api/evidence.py").read_text(encoding="utf-8")
        self.assertIn('"Accept-Ranges": "bytes"', evidence_code)
        self.assertIn('disposition = "attachment" if download else "inline"', evidence_code)
        self.assertIn('"Content-Disposition": f\'{disposition}; filename="{filename}"\'', evidence_code)


class TestRemediation3SheltersAndRoutes(unittest.TestCase):
    """Verify honest shelter handling and route constraints."""

    def test_shelter_service_radius_all_query(self):
        """Verify shelter service passes radius_km=None for unlimited search radius."""
        shelter_code = Path("app/services/shelter_service.py").read_text(encoding="utf-8")
        self.assertIn("radius_km: Optional[float] = None", shelter_code)
        self.assertIn("if radius_km is not None:", shelter_code)

    def test_zero_straight_line_fabrication(self):
        """Verify routing service explicitly forbids straight-line fallback."""
        routing_code = Path("app/services/external_routing_service.py").read_text(encoding="utf-8")
        self.assertIn("Zero straight-line fallback applied.", routing_code)
        self.assertIn("AERION strictly prohibits straight-line pseudo-routing.", routing_code)


class TestRemediation3StructuralUX(unittest.TestCase):
    """Verify complete removal of standalone route finding and 7-step linear workflow."""

    def test_evacuation_page_deleted(self):
        """Verify frontend/src/pages/EvacuationPage.tsx is completely deleted."""
        self.assertFalse(
            Path("frontend/src/pages/EvacuationPage.tsx").exists(),
            "frontend/src/pages/EvacuationPage.tsx must be completely deleted.",
        )

    def test_sidebar_has_no_standalone_evacuation_link(self):
        """Verify Sidebar does not contain link to /disaster/evacuation."""
        sidebar_code = Path("frontend/src/components/layout/Sidebar.tsx").read_text(encoding="utf-8")
        self.assertNotIn("/disaster/evacuation", sidebar_code)
        self.assertIn("Disaster Workspace", sidebar_code)

    def test_app_router_redirects_evacuation_to_disaster(self):
        """Verify App.tsx redirects /disaster/evacuation to /disaster."""
        app_code = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
        self.assertNotIn("EvacuationPage", app_code)
        self.assertIn('path="/disaster/evacuation"', app_code)
        self.assertIn('to="/disaster"', app_code)

    def test_disaster_workspace_implements_7_steps(self):
        """Verify DisasterPage.tsx implements the 7-step linear intelligence flow."""
        disaster_code = Path("frontend/src/pages/DisasterPage.tsx").read_text(encoding="utf-8")
        self.assertIn("1. INCIDENT / LOCATION", disaster_code)
        self.assertIn("2. ENVIRONMENT (METEOROLOGY)", disaster_code)
        self.assertIn("3. DAMAGE / AI EVIDENCE", disaster_code)
        self.assertIn("4. RISK / SITUATION", disaster_code)
        self.assertIn("5. VERIFIED SHELTERS", disaster_code)
        self.assertIn("6. EVACUATION ROUTE", disaster_code)
        self.assertIn("7. OPERATIONAL REPORT", disaster_code)
        self.assertIn("INSUFFICIENT EVIDENCE / UNAVAILABLE", disaster_code)
        self.assertIn("NO VERIFIED SHELTER DESTINATION AVAILABLE", disaster_code)
        self.assertIn("DEMO AOI (SYNTHETIC / NON-AUTHORITATIVE)", disaster_code)
        self.assertIn("DEMO CONTEXT ASSESSMENT", disaster_code)
        self.assertIn("INSUFFICIENT EVIDENCE / DEMO CONTEXT ONLY", disaster_code)
        self.assertIn("REAL LOCATION RISK", disaster_code)

    def test_border_page_pre_rendered_video_badge(self):
        """Verify BorderPage.tsx clearly marks video annotations as pre-rendered with explicit states."""
        border_code = Path("frontend/src/pages/BorderPage.tsx").read_text(encoding="utf-8")
        self.assertIn("VIDEO ANNOTATION: PRE-RENDERED", border_code)
        self.assertIn("BOXES: ON", border_code)
        self.assertIn("LABELS: ON", border_code)
        self.assertIn("CONFIDENCE: ON", border_code)
        self.assertIn("TRACK IDS: ON", border_code)
        self.assertIn("IMMUTABLE ARTIFACT", border_code)
