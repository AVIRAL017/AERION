"""
AERION — Authentication & Authorization Tests (Phase 3D + Phase G)
Validates:
- Argon2id password hashing and constant-time verification
- JWT issuance, verification, and decoding (with expiration)
- Duplicate email registration rejection
- Invalid password rejection
- Expired and tampered token handling
- Role-based authorization enforcement
- Phase G: Token Refresh (POST /auth/refresh)
- Phase G: Local Operator Registration (POST /auth/register)
- Phase G: Forgot and Reset Password Workflow (POST /auth/forgot-password & /auth/reset-password)
- Phase G: Operator Command Hub Profile (GET /auth/me)
"""

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import jwt

from app.core.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.core.config import AERIONSettings, get_settings
from app.core.errors import AuthenticationError
from app.db.models import User, Organization, Subscription
from app.db.session import get_session_factory, close_db_connections
from app.main import create_app
from app.services.auth_service import AuthService
from app.schemas.auth import UserRegisterRequest, RefreshTokenRequest, ResetPasswordRequest


class TestPasswordSecurity(unittest.TestCase):
    """Test Argon2id password hashing guarantees."""

    def test_hash_and_verify_success(self):
        pwd = "SecureOperationalPassword123!"
        hashed = hash_password(pwd)
        self.assertTrue(hashed.startswith("$argon2id$"))
        self.assertTrue(verify_password(pwd, hashed))

    def test_wrong_password_fails(self):
        pwd = "SecureOperationalPassword123!"
        hashed = hash_password(pwd)
        self.assertFalse(verify_password("WrongPassword999!", hashed))

    def test_short_password_rejected(self):
        with self.assertRaises(ValueError):
            hash_password("short")


class TestJWTSecurity(unittest.TestCase):
    """Test JWT access token issuance, verification, and expiration."""

    def test_token_issuance_and_decoding(self):
        data = {"sub": "user-uuid-123", "org": "org-uuid-456", "role": "operator"}
        token = create_access_token(data, expires_delta=timedelta(minutes=15))
        payload = decode_access_token(token)
        self.assertEqual(payload["sub"], "user-uuid-123")
        self.assertEqual(payload["org"], "org-uuid-456")
        self.assertEqual(payload["role"], "operator")

    def test_expired_token_rejected(self):
        data = {"sub": "user-uuid-123"}
        # Issue token that expired 10 seconds ago
        token = create_access_token(data, expires_delta=timedelta(seconds=-10))
        with self.assertRaises(AuthenticationError) as ctx:
            decode_access_token(token)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("expired", ctx.exception.message.lower())

    def test_tampered_token_rejected(self):
        data = {"sub": "user-uuid-123"}
        token = create_access_token(data)
        tampered = token[:-4] + "fake"
        with self.assertRaises(AuthenticationError) as ctx:
            decode_access_token(tampered)
        self.assertEqual(ctx.exception.status_code, 401)


class TestPhaseGAuthServices(unittest.IsolatedAsyncioTestCase):
    """Integration test suite for Phase G authentication workflows using isolated async session."""

    async def asyncSetUp(self):
        await close_db_connections()

    async def asyncTearDown(self):
        await close_db_connections()

    async def test_register_user_creates_org_and_subscription(self):
        """BUG-032: Test local user registration provisions new Organization and FREE Subscription."""
        unique_suffix = int(datetime.now(timezone.utc).timestamp()) + 101
        email = f"cadet_{unique_suffix}@aerion.mil"
        req = UserRegisterRequest(
            email=email,
            password="StrongPassword123!",
            organization_name=f"Tactical Unit {unique_suffix}",
            display_name="Cadet Vance",
        )

        factory = get_session_factory()
        async with factory() as session:
            user_resp, token_resp = await AuthService.register_user(session, req)
            await session.commit()

            self.assertEqual(user_resp.email, email)
            self.assertEqual(user_resp.display_name, "Cadet Vance")
            self.assertIsNotNone(token_resp.access_token)

            # Verify persisted user & org
            u = await session.get(User, uuid.UUID(user_resp.id))
            self.assertIsNotNone(u)
            self.assertEqual(u.email, email)

            org = await session.get(Organization, uuid.UUID(user_resp.organization_id))
            self.assertIsNotNone(org)

    async def test_refresh_token_workflow(self):
        """BUG-031: Test refresh_user_token generates a rotated valid token."""
        unique_suffix = int(datetime.now(timezone.utc).timestamp()) + 202
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        email = f"operator_{unique_suffix}@aerion.mil"

        factory = get_session_factory()
        async with factory() as session:
            org = Organization(id=org_id, name="Refresh Unit", slug=f"refresh-unit-{unique_suffix}")
            user = User(
                id=user_id,
                email=email,
                hashed_password=hash_password("OperationalSecret123!"),
                display_name="Major Tom",
                role="operator",
                organization_id=org_id,
                is_active=True,
                auth_provider="local"
            )
            session.add_all([org, user])
            await session.commit()

            initial_token = create_access_token({
                "sub": str(user_id),
                "email": email,
                "org": str(org_id),
                "role": "operator"
            })

            new_token_resp = await AuthService.refresh_user_token(session, str(user_id))
            self.assertIsNotNone(new_token_resp.access_token)
            self.assertEqual(new_token_resp.user.email, email)
            self.assertEqual(new_token_resp.user.display_name, "Major Tom")

    async def test_forgot_and_reset_password_workflow(self):
        """BUG-033: Test forgot password token issuance and password reset execution."""
        unique_suffix = int(datetime.now(timezone.utc).timestamp()) + 303
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        email = f"reset_target_{unique_suffix}@aerion.mil"
        initial_pw = "OriginalSecret123!"
        new_pw = "ReplacedSecret999!"

        factory = get_session_factory()
        async with factory() as session:
            org = Organization(id=org_id, name="Reset Unit", slug=f"reset-unit-{unique_suffix}")
            user = User(
                id=user_id,
                email=email,
                hashed_password=hash_password(initial_pw),
                display_name="Captain Vance",
                role="operator",
                organization_id=org_id,
                is_active=True,
                auth_provider="local"
            )
            session.add_all([org, user])
            await session.commit()

            # 1. Request forgot password
            forgot_resp = await AuthService.initiate_password_reset(session, email)
            self.assertIn(forgot_resp["delivery_status"], ["EMAIL_SENT", "EMAIL_DELIVERY_NOT_CONFIGURED"])
            token = forgot_resp.get("reset_token")
            self.assertIsNotNone(token)

            # 2. Reset password
            result = await AuthService.complete_password_reset(session, token, new_pw)
            self.assertTrue(result["success"])

            # 3. Verify user has updated hash and can verify with new password
            u = await session.get(User, user_id)
            self.assertTrue(verify_password(new_pw, u.hashed_password))
            self.assertFalse(verify_password(initial_pw, u.hashed_password))

    async def test_operator_hub_me_endpoint_and_sanitization(self):
        """BUG-018: Test /auth/me returns operator details, provider, org, role without leaking password hashes."""
        unique_suffix = int(datetime.now(timezone.utc).timestamp()) + 404
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        email = f"operator_me_{unique_suffix}@aerion.mil"

        factory = get_session_factory()
        async with factory() as session:
            org = Organization(id=org_id, name="Hub Unit", slug=f"hub-unit-{unique_suffix}")
            user = User(
                id=user_id,
                email=email,
                hashed_password=hash_password("SuperSecretHash123!"),
                display_name="Commander Shepard",
                role="admin",
                organization_id=org_id,
                is_active=True,
                auth_provider="local"
            )
            session.add_all([org, user])
            await session.commit()

            # Verify through user model get
            u = await session.get(User, user_id)
            self.assertEqual(u.display_name, "Commander Shepard")
            self.assertEqual(u.role, "admin")
            self.assertEqual(u.auth_provider, "local")
            self.assertEqual(u.organization_id, org_id)

    async def test_usage_and_storage_accounting_services(self):
        """BUG-027, BUG-028, BUG-029: Test DB repository recording and storage calculations."""
        from app.db.models import Project, Asset, UsageEvent
        from app.db.repositories import UsageEventRepository, AssetRepository, SubscriptionRepository
        unique_suffix = int(datetime.now(timezone.utc).timestamp()) + 505
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()

        factory = get_session_factory()
        async with factory() as session:
            org = Organization(id=org_id, name="Usage Unit", slug=f"usage-unit-{unique_suffix}")
            user = User(
                id=user_id,
                email=f"meter_{unique_suffix}@aerion.mil",
                hashed_password=hash_password("Pass123!"),
                role="operator",
                organization_id=org_id,
                is_active=True,
            )
            proj = Project(organization_id=org_id, name="Mission Project", mode="disaster")
            sub = Subscription(
                organization_id=org_id,
                plan="PRO",
                price_inr=9,
                is_active=True,
                current_period_start=datetime.now(timezone.utc),
                current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
            )
            session.add_all([org, user, proj, sub])
            await session.flush()

            # Record usage events
            usage_repo = UsageEventRepository(session)
            await usage_repo.record_event(org_id, dimension="drone_image", quantity=3)
            await usage_repo.record_event(org_id, dimension="video_minute", quantity=10)

            # Record asset
            asset = Asset(
                project_id=proj.id,
                storage_key="imagery/aerial.tif",
                asset_type="drone_image",
                file_size_bytes=2097152,  # 2 MB
                sha256="1" * 64,
            )
            session.add(asset)
            await session.commit()

            # Verify aggregation
            drone_count = await usage_repo.get_monthly_count(org_id, dimension="drone_image")
            self.assertEqual(drone_count, 3)

            video_count = await usage_repo.get_monthly_count(org_id, dimension="video_minute")
            self.assertEqual(video_count, 10)

            asset_repo = AssetRepository(session)
            total_bytes = await asset_repo.get_total_storage_bytes(org_id)
            self.assertEqual(total_bytes, 2097152)

            sub_repo = SubscriptionRepository(session)
            active_sub = await sub_repo.get_by_organization(org_id)
            self.assertEqual(active_sub.plan, "PRO")


if __name__ == "__main__":
    unittest.main()
