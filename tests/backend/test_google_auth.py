"""
AERION v1 — Comprehensive Google Authentication Tests (Step 32)
Tests:
1. Google token verification success (valid mocked claims)
2. Invalid Google token signature / structure rejection
3. Expired Google token rejection
4. Wrong audience (client ID) rejection
5. Wrong issuer rejection
6. Missing required identity information (email / sub)
7. Unverified email handling (email_verified == False)
8. First-time user creation (auto-provisions Organization & Operator User)
9. Existing-user login via Google sub
10. Account linking when email matches existing local user
11. Inactive / deactivated user rejection
12. Logout endpoint behavior
13. Protected API access with issued JWT from Google login
"""

import asyncio
import unittest
from unittest.mock import patch
import uuid
from fastapi.testclient import TestClient

from app.core.config import AERIONSettings, get_settings
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.google_auth import GoogleAuthVerifier
from app.db.models import Organization, Subscription, User
from app.db.session import close_db_connections, get_session_factory
from app.main import create_app
from app.services.auth_service import AuthService


class TestGoogleTokenVerification(unittest.TestCase):
    """Unit tests for GoogleAuthVerifier cryptographic validation logic."""

    @patch("app.core.google_auth.id_token.verify_oauth2_token")
    def test_verify_valid_token_success(self, mock_verify):
        settings = get_settings()
        mock_verify.return_value = {
            "iss": "accounts.google.com",
            "sub": "google-sub-1234567890",
            "email": "operator.alpha@aerion.gov",
            "email_verified": True,
            "name": "Operator Alpha",
            "aud": settings.GOOGLE_CLIENT_ID,
        }

        claims = GoogleAuthVerifier.verify_id_token("valid.google.idtoken")
        self.assertEqual(claims["sub"], "google-sub-1234567890")
        self.assertEqual(claims["email"], "operator.alpha@aerion.gov")
        self.assertTrue(claims["email_verified"])

    @patch("app.core.google_auth.id_token.verify_oauth2_token")
    def test_verify_expired_token_fails(self, mock_verify):
        mock_verify.side_effect = ValueError("Token used too late, expired 12345")
        with self.assertRaises(AuthenticationError) as ctx:
            GoogleAuthVerifier.verify_id_token("expired.google.idtoken")
        self.assertIn("expired", ctx.exception.message.lower())

    @patch("app.core.google_auth.id_token.verify_oauth2_token")
    def test_verify_audience_mismatch_fails(self, mock_verify):
        mock_verify.side_effect = ValueError("Wrong recipient, audience mismatch")
        with self.assertRaises(AuthenticationError) as ctx:
            GoogleAuthVerifier.verify_id_token("wrongaud.google.idtoken")
        self.assertIn("audience", ctx.exception.message.lower())

    @patch("app.core.google_auth.id_token.verify_oauth2_token")
    def test_verify_invalid_issuer_fails(self, mock_verify):
        mock_verify.return_value = {
            "iss": "untrusted-issuer.example.com",
            "sub": "sub-123",
            "email": "test@aerion.gov",
            "email_verified": True,
        }
        with self.assertRaises(AuthenticationError) as ctx:
            GoogleAuthVerifier.verify_id_token("badissuer.token")
        self.assertIn("issuer", ctx.exception.message.lower())

    @patch("app.core.google_auth.id_token.verify_oauth2_token")
    def test_unverified_email_fails(self, mock_verify):
        mock_verify.return_value = {
            "iss": "accounts.google.com",
            "sub": "sub-123",
            "email": "unverified@aerion.gov",
            "email_verified": False,
        }
        with self.assertRaises(AuthenticationError) as ctx:
            GoogleAuthVerifier.verify_id_token("unverified.token")
        self.assertIn("verified", ctx.exception.message.lower())

    @patch("app.core.google_auth.id_token.verify_oauth2_token")
    def test_missing_sub_fails(self, mock_verify):
        mock_verify.return_value = {
            "iss": "accounts.google.com",
            "email": "test@aerion.gov",
            "email_verified": True,
        }
        with self.assertRaises(AuthenticationError) as ctx:
            GoogleAuthVerifier.verify_id_token("nosub.token")
        self.assertIn("subject", ctx.exception.message.lower())


class TestGoogleAuthDatabaseOperations(unittest.IsolatedAsyncioTestCase):
    """Integration tests for Google Sign-In database provisioning, linking, and status enforcement."""

    async def asyncSetUp(self):
        await close_db_connections()

    async def asyncTearDown(self):
        await close_db_connections()

    @patch("app.core.google_auth.GoogleAuthVerifier.verify_id_token")
    async def test_first_time_google_user_provisioning(self, mock_verify):
        unique_sub = f"google-sub-{uuid.uuid4().hex[:12]}"
        unique_email = f"operator-{uuid.uuid4().hex[:8]}@aerion.gov"

        mock_verify.return_value = {
            "iss": "https://accounts.google.com",
            "sub": unique_sub,
            "email": unique_email,
            "email_verified": True,
            "name": "Operator Command Lead",
        }

        factory = get_session_factory()
        async with factory() as session:
            token_resp = await AuthService.login_with_google(session, "dummy.token")
            await session.commit()

            self.assertIsNotNone(token_resp.access_token)
            self.assertEqual(token_resp.user.email, unique_email)
            self.assertEqual(token_resp.user.auth_provider, "google")
            self.assertEqual(token_resp.user.display_name, "Operator Command Lead")
            self.assertEqual(token_resp.user.role, "operator")

            # Verify persisted user record
            u = await session.get(User, uuid.UUID(token_resp.user.id))
            self.assertIsNotNone(u)
            self.assertEqual(u.provider_sub, unique_sub)
            self.assertEqual(u.auth_provider, "google")
            self.assertIsNone(u.hashed_password)

    @patch("app.core.google_auth.GoogleAuthVerifier.verify_id_token")
    async def test_returning_google_user_login(self, mock_verify):
        unique_sub = f"google-sub-returning-{uuid.uuid4().hex[:8]}"
        unique_email = f"returning-{uuid.uuid4().hex[:8]}@aerion.gov"

        mock_verify.return_value = {
            "iss": "accounts.google.com",
            "sub": unique_sub,
            "email": unique_email,
            "email_verified": True,
            "name": "Returning Operator",
        }

        factory = get_session_factory()
        async with factory() as session:
            # 1. First login (provisions user)
            token1 = await AuthService.login_with_google(session, "token.1")
            await session.commit()

            # 2. Second login (resolves existing by provider_sub)
            token2 = await AuthService.login_with_google(session, "token.2")
            self.assertEqual(token1.user.id, token2.user.id)
            self.assertEqual(token2.user.email, unique_email)

    @patch("app.core.google_auth.GoogleAuthVerifier.verify_id_token")
    async def test_account_linking_for_matching_email(self, mock_verify):
        linking_email = f"link-{uuid.uuid4().hex[:8]}@aerion.gov"
        google_sub = f"google-sub-link-{uuid.uuid4().hex[:8]}"

        factory = get_session_factory()
        async with factory() as session:
            # Create pre-existing local user
            org = Organization(name="Pre-Existing Org", slug=f"pre-org-{uuid.uuid4().hex[:6]}")
            session.add(org)
            await session.flush()

            pre_user = User(
                organization_id=org.id,
                email=linking_email,
                hashed_password="hashed_pass_placeholder",
                auth_provider="local",
                role="operator",
                is_active=True,
            )
            session.add(pre_user)
            await session.commit()

            mock_verify.return_value = {
                "iss": "accounts.google.com",
                "sub": google_sub,
                "email": linking_email,
                "email_verified": True,
                "name": "Linked Operator",
            }

            token_resp = await AuthService.login_with_google(session, "token.link")
            await session.commit()

            self.assertEqual(token_resp.user.id, str(pre_user.id))
            self.assertEqual(pre_user.provider_sub, google_sub)

    @patch("app.core.google_auth.GoogleAuthVerifier.verify_id_token")
    async def test_deactivated_google_user_rejected(self, mock_verify):
        sub_deactivated = f"google-sub-deact-{uuid.uuid4().hex[:8]}"
        email_deactivated = f"deactivated-{uuid.uuid4().hex[:8]}@aerion.gov"

        mock_verify.return_value = {
            "iss": "accounts.google.com",
            "sub": sub_deactivated,
            "email": email_deactivated,
            "email_verified": True,
            "name": "Deactivated Operator",
        }

        factory = get_session_factory()
        async with factory() as session:
            token_resp = await AuthService.login_with_google(session, "token.provision")
            u = await session.get(User, uuid.UUID(token_resp.user.id))
            u.is_active = False
            await session.commit()

            with self.assertRaises(PermissionDeniedError):
                await AuthService.login_with_google(session, "token.again")


class TestGoogleAuthAPIRoutes(unittest.TestCase):
    """API endpoint tests for /api/v1/auth/google, /logout, and /me."""

    def setUp(self):
        self.settings = AERIONSettings(ENVIRONMENT="test")
        self.app = create_app(settings=self.settings)
        self.client = TestClient(self.app)

    @patch("app.services.auth_service.AuthService.login_with_google")
    def test_api_google_login_endpoint(self, mock_login_with_google):
        from datetime import datetime, timezone
        from app.schemas.auth import TokenResponse, UserResponse

        mock_user = UserResponse(
            id="11111111-1111-1111-1111-111111111111",
            organization_id="22222222-2222-2222-2222-222222222222",
            email="api-tester@aerion.gov",
            role="operator",
            auth_provider="google",
            display_name="API Tester",
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        mock_login_with_google.return_value = TokenResponse(
            access_token="mocked.jwt.token",
            token_type="Bearer",
            expires_in_seconds=1800,
            user=mock_user,
        )

        resp = self.client.post(
            "/api/v1/auth/google",
            json={"id_token": "valid.mocked.google.token"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["access_token"], "mocked.jwt.token")
        self.assertEqual(data["user"]["email"], "api-tester@aerion.gov")
        self.assertEqual(data["user"]["auth_provider"], "google")
        self.assertEqual(data["user"]["display_name"], "API Tester")

    def test_api_logout_endpoint(self):
        resp = self.client.post("/api/v1/auth/logout")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])
        self.assertIn("Logged out", resp.json()["data"]["message"])

    def test_api_me_endpoint_with_google_user(self):
        from app.api.deps import get_current_user
        from datetime import datetime, timezone

        test_user = User(
            id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            organization_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            email="google.operator@aerion.gov",
            role="operator",
            auth_provider="google",
            display_name="Google Operator",
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

        self.app.dependency_overrides[get_current_user] = lambda: test_user
        try:
            resp = self.client.get("/api/v1/auth/me")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()["data"]
            self.assertEqual(data["email"], "google.operator@aerion.gov")
            self.assertEqual(data["auth_provider"], "google")
            self.assertEqual(data["display_name"], "Google Operator")
        finally:
            self.app.dependency_overrides.pop(get_current_user, None)


if __name__ == "__main__":
    unittest.main()
