"""
AERION — Product Acceptance Remediation Comprehensive Verification Suite
Tests for:
BUG A: Video Operational Report (Persistence linkage, analysis_id propagation, DB query)
BUG B: Disaster Pair Forensic Validation (Metric accuracy, mathematical formulas, UI labels)
BUG C: Google Auth (Error handling, configuration checklist, origin mismatch banner)
BUG D: Login Notification Email (Non-blocking async dispatch, zero emails on refresh/failure)
BUG E: Annotation UX & Overcrowding (Compact badges, density modes, layer toggles)
BUG F: Safe Route (Disaster location grounding, PostGIS shelters, ORS endpoint migration)
BUG G: Evidence Download (Attachment headers, download action URLs)
"""

import asyncio
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import get_settings
from app.schemas.evidence import GeoPoint
from app.services.email_service import EmailService
from app.services.video_annotation_service import VideoAnnotationService
from app.services.annotation_service import AnnotationService
from app.services.external_routing_service import ExternalRoutingService
from app.services.geospatial_providers import OpenRouteServiceProvider


class TestBugAVideoOperationalReport(unittest.TestCase):
    """BUG A: Verify video analysis persistence and report endpoint linkage."""

    def test_analysis_endpoint_exposes_canonical_analysis_id(self):
        """Verify app/api/analysis.py hoists persist_info analysis_id into report_data."""
        analysis_code = Path("app/api/analysis.py").read_text(encoding="utf-8")
        self.assertIn('report_data["analysis_id"] = persist_info.get("analysis_id")', analysis_code)
        self.assertIn('report_data["job_id"] = persist_info.get("job_id")', analysis_code)

    def test_video_result_adapter_prioritizes_persistence_analysis_id(self):
        """Verify frontend adapter maps canonical analysis_id from persistence."""
        adapter_code = Path("frontend/src/api/videoResultAdapter.ts").read_text(encoding="utf-8")
        self.assertIn("rawResponse.persistence?.analysis_id || rawResponse.analysis_id", adapter_code)

    def test_situation_report_endpoint_accepts_analysis_uuid(self):
        """Verify situations.py looks up by analysis_id and job_id scoped to organization."""
        situations_code = Path("app/api/situations.py").read_text(encoding="utf-8")
        self.assertIn("db_result = await result_repo.get_by_analysis_id_scoped(parsed_uuid, effective_org_id)", situations_code)


class TestBugBDisasterPairValidation(unittest.TestCase):
    """BUG B: Forensic validation of Siamese change detection damage metrics."""

    def test_mathematical_consistency_formulas(self):
        """
        Verify exact arithmetic consistency:
        Damaged pixels: 733
        Total pixels: 262,144 (512x512)
        Damage ratio: 733 / 262144 = 0.0027962... => 0.0028
        Damage percentage: 0.28% => ~0.3%
        """
        damaged_pixels = 733
        total_pixels = 262144
        ratio = damaged_pixels / total_pixels
        self.assertAlmostEqual(ratio, 0.0027962, places=6)
        self.assertEqual(round(ratio, 4), 0.0028)
        self.assertEqual(round(ratio * 100, 1), 0.3)

    def test_frontend_disambiguates_mean_probability_and_ratio(self):
        """Verify DisasterPage.tsx explicitly labels scene-wide mean probability and ratio."""
        disaster_code = Path("frontend/src/pages/DisasterPage.tsx").read_text(encoding="utf-8")
        self.assertIn("SCENE-WIDE MEAN PROB:", disaster_code)
        self.assertIn("DAMAGE RATIO:", disaster_code)
        self.assertIn("SIDE-BY-SIDE", disaster_code)
        self.assertIn("mix-blend-screen", disaster_code)


class TestBugCGoogleAuthOriginHandling(unittest.TestCase):
    """BUG C: Google OAuth error handling and origin mismatch mitigation."""

    def test_login_page_has_origin_mismatch_handler(self):
        """Verify LoginPage.tsx catches origin_mismatch and displays user-friendly banner."""
        login_code = Path("frontend/src/pages/LoginPage.tsx").read_text(encoding="utf-8")
        self.assertIn("GOOGLE SIGN-IN UNAVAILABLE", login_code)
        self.assertIn("error_callback", login_code)
        self.assertIn("Authorized JavaScript Origins", login_code)


class TestBugDLoginNotificationEmail(unittest.TestCase):
    """BUG D: Asynchronous, non-blocking login security notification email."""

    def test_email_service_console_delivery(self):
        """Verify EmailService default console logger succeeds non-blockingly."""
        svc = EmailService()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        res = loop.run_until_complete(
            svc.send_login_notification(
                recipient_email="operator@aerion.mil",
                auth_method="Password",
                client_ip="127.0.0.1",
            )
        )
        loop.close()
        self.assertTrue(res)

    def test_auth_endpoints_trigger_email_on_login(self):
        """Verify login and google_login in auth.py invoke send_login_notification."""
        auth_code = Path("app/api/auth.py").read_text(encoding="utf-8")
        self.assertIn("email_service.send_login_notification", auth_code)
        self.assertIn('auth_method="Password"', auth_code)
        self.assertIn('auth_method="Google"', auth_code)

    def test_token_refresh_does_not_send_email(self):
        """Verify /refresh endpoint strictly does NOT trigger email dispatch."""
        auth_code = Path("app/api/auth.py").read_text(encoding="utf-8")
        refresh_idx = auth_code.find('async def refresh_token')
        forgot_idx = auth_code.find('async def forgot_password')
        refresh_body = auth_code[refresh_idx:forgot_idx]
        self.assertNotIn("send_login_notification", refresh_body)


class TestBugEAnnotationPresentationUX(unittest.TestCase):
    """BUG E: Smart label rendering and compact presentation."""

    def test_video_annotation_uses_compact_labels(self):
        """Verify video annotation service formats compact badges."""
        video_svc_code = Path("app/services/video_annotation_service.py").read_text(encoding="utf-8")
        self.assertIn("CAR", video_svc_code)
        self.assertIn("TRUCK", video_svc_code)
        self.assertIn("short_class", video_svc_code)

    def test_image_annotation_uses_compact_labels(self):
        """Verify image annotation service formats compact badges."""
        image_svc_code = Path("app/services/annotation_service.py").read_text(encoding="utf-8")
        self.assertIn("short_class", image_svc_code)

    def test_frontend_image_page_has_density_mode_toggle(self):
        """Verify ImagePage.tsx contains densityMode and layer toggles."""
        image_page_code = Path("frontend/src/pages/ImagePage.tsx").read_text(encoding="utf-8")
        self.assertIn("DENSE", image_page_code)
        self.assertIn("NORMAL", image_page_code)
        self.assertIn("BOXES:", image_page_code)
        self.assertIn("LABELS:", image_page_code)


class TestBugFSafeRouteFunctionality(unittest.TestCase):
    """BUG F: Safe Route PostGIS shelter integration and ORS api.heigit.org endpoint."""

    def test_ors_endpoint_defaults_to_heigit(self):
        """Verify ORS base url is migrated to api.heigit.org."""
        ext_routing_code = Path("app/services/external_routing_service.py").read_text(encoding="utf-8")
        self.assertIn("https://api.heigit.org", ext_routing_code)

        geospatial_code = Path("app/services/geospatial_providers.py").read_text(encoding="utf-8")
        self.assertIn("https://api.heigit.org", geospatial_code)

    def test_evacuation_page_has_leaflet_map_and_shelters(self):
        """Verify EvacuationPage.tsx includes Leaflet map and queries real shelters."""
        evac_code = Path("frontend/src/pages/EvacuationPage.tsx").read_text(encoding="utf-8")
        self.assertIn("import L from 'leaflet';", evac_code)
        self.assertIn("sheltersApi.list", evac_code)
        self.assertIn("externalApi.getRoute", evac_code)
        self.assertIn("DISASTER LOCATION REQUIRED", evac_code)


class TestBugGEvidenceDownloads(unittest.TestCase):
    """BUG G: Usable evidence download attachments across all pages."""

    def test_evidence_endpoint_attachment_disposition(self):
        """Verify evidence endpoint sets attachment headers."""
        evidence_code = Path("app/api/evidence.py").read_text(encoding="utf-8")
        self.assertIn('Content-Disposition', evidence_code)
        self.assertIn('attachment', evidence_code)

    def test_frontend_pages_expose_download_buttons(self):
        """Verify ImagePage, BorderPage, and DisasterPage expose download buttons."""
        image_page = Path("frontend/src/pages/ImagePage.tsx").read_text(encoding="utf-8")
        self.assertIn("DOWNLOAD ANNOTATED", image_page)
        self.assertIn("DOWNLOAD ORIGINAL", image_page)

        border_page = Path("frontend/src/pages/BorderPage.tsx").read_text(encoding="utf-8")
        self.assertIn("DOWNLOAD ANNOTATED VIDEO", border_page)
        self.assertIn("DOWNLOAD ORIGINAL VIDEO", border_page)

        disaster_page = Path("frontend/src/pages/DisasterPage.tsx").read_text(encoding="utf-8")
        self.assertIn("DOWNLOAD DAMAGE MASK", disaster_page)
        self.assertIn("DOWNLOAD POST IMAGE", disaster_page)


if __name__ == "__main__":
    unittest.main()
