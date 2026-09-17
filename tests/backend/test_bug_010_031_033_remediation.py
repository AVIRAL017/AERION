"""
AERION — Verification Suite for Targeted Acceptance Remediation
BUG-010: Geo-context "SELECT ON MAP" (Real Leaflet WGS-84 Map, No Synthetic Interpolation)
BUG-031: Authenticated Session Expiry & Token Refresh (401 Interception, Retry, Safe Fallback)
BUG-033: Forgot-Password & Reset-Password End-to-End Lifecycle & Security
"""

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.core.errors import AuthenticationError, ValidationError
from app.db.models import Organization, User
from app.db.session import close_db_connections, get_session_factory
from app.schemas.auth import UserLoginRequest, UserRegisterRequest
from app.services.auth_service import AuthService


class TestBug010MapRemediation(unittest.TestCase):
    """BUG-010: Verify removal of synthetic linear interpolation and integration of genuine Leaflet map."""

    def setUp(self):
        self.modal_path = Path("frontend/src/components/OperatorLocationModal.tsx")
        self.client_path = Path("frontend/src/api/client.ts")
        self.assertTrue(self.modal_path.exists(), "OperatorLocationModal.tsx must exist")
        self.modal_content = self.modal_path.read_text(encoding="utf-8")

    def test_bug_010_no_synthetic_linear_interpolation(self):
        """Verify that synthetic bounding box (68°E–92°E, 20°N–36°N) interpolation is completely removed."""
        self.assertNotIn("interpLon", self.modal_content, "Synthetic interpLon must not exist")
        self.assertNotIn("interpLat", self.modal_content, "Synthetic interpLat must not exist")
        self.assertNotIn("linear interpolation", self.modal_content.lower(), "Linear interpolation comment/logic must not exist")
        self.assertNotIn("92.0 - 68.0", self.modal_content, "Hardcoded longitude range formula must not exist")
        self.assertNotIn("36.0 - 20.0", self.modal_content, "Hardcoded latitude range formula must not exist")

    def test_bug_010_real_geographic_leaflet_map_integration(self):
        """Verify that genuine Leaflet map library and WGS-84 projection handling are implemented."""
        self.assertIn("import L from 'leaflet';", self.modal_content, "Leaflet must be imported")
        self.assertIn("L.map(", self.modal_content, "Leaflet map initialization must be present")
        self.assertIn("L.tileLayer(", self.modal_content, "Leaflet tile layer must be present")
        self.assertIn("e.latlng.lat", self.modal_content, "Map click must use real Leaflet event latlng")
        self.assertIn("e.latlng.lng", self.modal_content, "Map click must use real Leaflet event latlng")
        self.assertIn("location_method: locationMethod", self.modal_content, "Location method must be preserved")
        self.assertIn("MAP_SELECTION", self.modal_content, "MAP_SELECTION provenance method must be recorded")

    def test_bug_010_no_false_authoritative_claims(self):
        """Verify that the UI includes an explicit disclaimer that selected points are not authoritative borders."""
        self.assertIn("DISCLAIMER:", self.modal_content)
        self.assertIn("not represent authoritative international border demarcations", self.modal_content)

    def test_bug_010_global_frontend_static_audit(self):
        """Audit the entire frontend source tree for synthetic coordinate formulas."""
        frontend_src = Path("frontend/src")
        for tsx_file in frontend_src.rglob("*.tsx"):
            content = tsx_file.read_text(encoding="utf-8")
            self.assertNotIn("interpLon", content, f"interpLon found in {tsx_file}")
            self.assertNotIn("interpLat", content, f"interpLat found in {tsx_file}")
            self.assertNotIn("92.0 - 68.0", content, f"Synthetic coordinate envelope found in {tsx_file}")


class TestBug031AuthRefresh(unittest.TestCase):
    """BUG-031: Verify frontend 401 interceptor, refresh flow, retry logic, and loop prevention."""

    def setUp(self):
        self.client_path = Path("frontend/src/api/client.ts")
        self.assertTrue(self.client_path.exists())
        self.client_content = self.client_path.read_text(encoding="utf-8")

    def test_bug_031_frontend_refresh_interceptor_implementation(self):
        """Verify client.ts implements 401 interception, token refresh call, and single retry."""
        self.assertIn("response.status === 401", self.client_content)
        self.assertIn("/auth/refresh", self.client_content)
        self.assertIn("_retry", self.client_content)
        self.assertIn("aerion_access_token", self.client_content)
        self.assertIn("aerion:unauthorized", self.client_content)

    def test_bug_031_infinite_loop_protection(self):
        """Verify client.ts excludes auth endpoints and retried requests from infinite refresh loops."""
        self.assertIn("isRetry", self.client_content)
        self.assertIn("isAuthEndpoint", self.client_content)
        self.assertIn("/auth/login", self.client_content)
        self.assertIn("/auth/refresh", self.client_content)


class TestBug031And033AsyncIntegrations(unittest.IsolatedAsyncioTestCase):
    """Isolated Async Database integration tests for BUG-031 and BUG-033."""

    async def asyncSetUp(self):
        await close_db_connections()

    async def asyncTearDown(self):
        await close_db_connections()

    async def test_bug_031_backend_token_refresh(self):
        """BUG-031: Test backend refresh_user_token issues fresh active JWT for authenticated session."""
        unique_suffix = int(datetime.now(timezone.utc).timestamp()) + 701
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        email = f"operator_refresh_{unique_suffix}@aerion.mil"

        factory = get_session_factory()
        async with factory() as session:
            org = Organization(id=org_id, name="Refresh Unit", slug=f"refresh-unit-{unique_suffix}")
            user = User(
                id=user_id,
                email=email,
                hashed_password=hash_password("OperationalSecret123!"),
                display_name="Major Vance",
                role="operator",
                organization_id=org_id,
                is_active=True,
                auth_provider="local",
            )
            session.add_all([org, user])
            await session.commit()

            # Refresh token issuance
            token_resp = await AuthService.refresh_user_token(session, str(user_id))
            self.assertIsNotNone(token_resp.access_token)
            self.assertEqual(token_resp.user.email, email)

            # Validate decoded claims
            claims = decode_access_token(token_resp.access_token)
            self.assertEqual(claims["sub"], str(user_id))
            self.assertEqual(claims["email"], email)

    async def test_bug_033_end_to_end_password_reset_lifecycle(self):
        """BUG-033: Complete end-to-end forgot-password, reset, old password rejection, and new password login."""
        unique_suffix = int(datetime.now(timezone.utc).timestamp()) + 702
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        email = f"reset_e2e_{unique_suffix}@aerion.mil"
        old_pw = "OriginalPasscode123!"
        new_pw = "RotatedPasscode456!"

        factory = get_session_factory()
        async with factory() as session:
            # 1. Provision user
            org = Organization(id=org_id, name="Reset Squadron", slug=f"reset-sq-{unique_suffix}")
            user = User(
                id=user_id,
                email=email,
                hashed_password=hash_password(old_pw),
                display_name="Lt Commander Data",
                role="operator",
                organization_id=org_id,
                is_active=True,
                auth_provider="local",
            )
            session.add_all([org, user])
            await session.commit()

            # 2. Verify initial login succeeds with old password
            login_req = UserLoginRequest(email=email, password=old_pw)
            initial_token = await AuthService.login_user(session, login_req)
            self.assertIsNotNone(initial_token.access_token)

            # 3. Request password reset (Forgot Password)
            forgot_resp = await AuthService.initiate_password_reset(session, email)
            self.assertIn("message", forgot_resp)
            self.assertIn(forgot_resp["delivery_status"], ["EMAIL_SENT", "EMAIL_DELIVERY_NOT_CONFIGURED"])
            reset_token = forgot_resp.get("reset_token")
            self.assertIsNotNone(reset_token, "Reset token must be legitimately provided in staging/test")

            # 4. Complete password reset with new password
            reset_result = await AuthService.complete_password_reset(session, reset_token, new_pw)
            self.assertTrue(reset_result.get("success"))
            await session.commit()

            # 5. Verify OLD password is now REJECTED
            with self.assertRaises(AuthenticationError):
                await AuthService.login_user(session, UserLoginRequest(email=email, password=old_pw))

            # 6. Verify NEW password SUCCEEDS
            new_login_resp = await AuthService.login_user(session, UserLoginRequest(email=email, password=new_pw))
            self.assertIsNotNone(new_login_resp.access_token)
            self.assertEqual(new_login_resp.user.email, email)

            # 7. Verify claims on new session token
            new_claims = decode_access_token(new_login_resp.access_token)
            self.assertEqual(new_claims["sub"], str(user_id))

            # 8. Security test: REUSING the token must be REJECTED
            with self.assertRaises(ValidationError) as ctx:
                await AuthService.complete_password_reset(session, reset_token, "YetAnotherPassword789!")
            self.assertIn("already been used", str(ctx.exception).lower())

            # 9. Security test: INVALID/UNKNOWN token must be REJECTED
            with self.assertRaises(ValidationError):
                await AuthService.complete_password_reset(session, "completely_fake_token_1234567890", "TestPass123!")

            # 10. Security test: EXPIRED token must be REJECTED
            expired_token = "synthetic_expired_token_for_test"
            AuthService._reset_tokens[expired_token] = {
                "email": email,
                "expires_at": datetime.now(timezone.utc) - timedelta(minutes=5),
                "used": False,
            }
            with self.assertRaises(ValidationError) as exp_ctx:
                await AuthService.complete_password_reset(session, expired_token, "TestPass123!")
            self.assertIn("expired", str(exp_ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
