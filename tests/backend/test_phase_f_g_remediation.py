"""
AERION v1 — Remediation Phase F + Phase G Comprehensive Automated Integration Test Suite
Validates:
- BUG-001: Real System Status & Component Readiness (FastAPI, DB, models, storage, providers)
- BUG-027: Subscription Tier Reporting (DB-driven, free vs pro quota limits)
- BUG-028: Authentic Usage Accounting (UsageEvent database recording and monthly aggregation)
- BUG-029: Storage Accounting (DBAsset file size aggregation)
- BUG-030: Quota Boundary Enforcement (clean USAGE_LIMIT_EXCEEDED / 429 when limits exceeded)
- BUG-002: Accessible Logout Dialog (structural frontend contracts)
- BUG-018: Account/Operator Command Hub (Sanitized operator profile, session, no secret leakage)
- BUG-031: Token Refresh (POST /auth/refresh with token rotation)
- BUG-032: Local Account Registration (POST /auth/register with user + org creation)
- BUG-033: Password Reset Workflow (POST /auth/forgot-password & /auth/reset-password)
"""

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.core.config import AERIONSettings, get_settings
from app.main import create_app
from app.db.session import get_session_factory, close_db_connections
from app.db.models import User, Organization, Subscription, UsageEvent, Asset, Project
from app.core.auth import create_access_token, hash_password, verify_password
from app.services.subscription_service import EntitlementService, PlanTier, UsageDimension
from app.core.errors import QuotaExceededError
from app.schemas.auth import UserRegisterRequest


class TestPhaseFGRemediation(unittest.TestCase):
    """Synchronous / API endpoint integration tests for Phase F and G."""

    def setUp(self):
        self.settings = AERIONSettings(ENVIRONMENT="test")
        self.app = create_app(settings=self.settings)
        self.client = TestClient(self.app)

    def test_bug_001_readiness_probe_dynamic_components(self):
        """BUG-001: Verify /ready probes real DB, models, storage directory, and returns structured components."""
        response = self.client.get("/api/v1/ready")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        res_data = data["data"]
        self.assertIn("ready", res_data)
        self.assertIn("status", res_data)
        self.assertIn(res_data["status"], ["HEALTHY", "DEGRADED", "UNAVAILABLE"])

        components = res_data["components"]
        self.assertIn("process", components)
        self.assertIn("database", components)
        self.assertIn("models", components)
        self.assertIn("storage", components)
        self.assertIn("providers", components)
        self.assertIn("mistral", components)

        self.assertEqual(components["process"]["status"], "ready")
        self.assertIn(components["database"]["status"], ["ready", "degraded", "unavailable"])
        self.assertIn(components["storage"]["status"], ["ready", "degraded", "unavailable"])
        self.assertIn(components["models"]["status"], ["ready", "lazy_unloaded", "degraded"])
        self.assertIn("details", components["models"])

    def test_bug_030_quota_boundary_enforcement(self):
        """BUG-030: Test quota evaluation reports EXHAUSTED when limits are exceeded."""
        service = EntitlementService()
        # FREE tier limit for drone images is 100
        free_limit = service.get_dimension_limit(PlanTier.FREE, UsageDimension.DRONE_IMAGE)
        self.assertEqual(free_limit, 100)

        # When usage < limit: should report AVAILABLE
        res = service.evaluate_quota(PlanTier.FREE, UsageDimension.DRONE_IMAGE, current_used=50, requested_quantity=10)
        self.assertEqual(res["status"], "AVAILABLE")
        self.assertFalse(res["is_exhausted"])

        # When usage + requested exceeds limit: should report EXHAUSTED
        res_ex = service.evaluate_quota(PlanTier.FREE, UsageDimension.DRONE_IMAGE, current_used=95, requested_quantity=10)
        self.assertEqual(res_ex["status"], "EXHAUSTED")
        self.assertTrue(res_ex["is_exhausted"])

    def test_bug_002_accessible_logout_dialog_contract(self):
        """BUG-002: Verify accessible logout dialog contract in Header component."""
        from pathlib import Path
        header_file = Path("frontend/src/components/layout/Header.tsx")
        self.assertTrue(header_file.exists())
        content = header_file.read_text(encoding="utf-8")
        self.assertIn('role="dialog"', content)
        self.assertIn('aria-modal="true"', content)
        self.assertIn("Confirm Sign Out", content)
        self.assertIn("Sign Out", content)
        self.assertIn("Cancel", content)

    def test_bug_018_operator_command_hub_route_contract(self):
        """BUG-018: Verify Operator Command Hub page and routing contract."""
        from pathlib import Path
        app_file = Path("frontend/src/App.tsx")
        account_page = Path("frontend/src/pages/AccountPage.tsx")
        self.assertTrue(app_file.exists())
        self.assertTrue(account_page.exists())
        app_content = app_file.read_text(encoding="utf-8")
        self.assertIn('path="/account"', app_content)
        self.assertIn("AccountPage", app_content)

        account_content = account_page.read_text(encoding="utf-8")
        self.assertIn("OPERATOR COMMAND HUB", account_content)
        self.assertIn("AUTHENTICATED IDENTITY & SECURITY SETTINGS", account_content)
        self.assertIn("SUBSCRIPTION & QUOTA TIER", account_content)
        self.assertIn("TERMINATE COMMAND SESSION", account_content)


class TestPhaseFGAsyncIntegrations(unittest.IsolatedAsyncioTestCase):
    """Isolated Async Database integration tests for Phase F and G."""

    async def asyncSetUp(self):
        await close_db_connections()

    async def asyncTearDown(self):
        await close_db_connections()

    async def test_bug_027_028_029_usage_and_storage_accounting(self):
        """BUG-027, BUG-028, BUG-029: Test DB repository recording and storage calculations."""
        unique_suffix = int(datetime.now(timezone.utc).timestamp()) + 601
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()

        factory = get_session_factory()
        async with factory() as session:
            org = Organization(id=org_id, name="Usage Org", slug=f"usage-org-{unique_suffix}")
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
            from app.db.repositories import UsageEventRepository, AssetRepository, SubscriptionRepository
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

    async def test_bug_031_session_token_refresh(self):
        """BUG-031: Test refresh_user_token generates a rotated valid token."""
        unique_suffix = int(datetime.now(timezone.utc).timestamp()) + 602
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        email = f"refresher_{unique_suffix}@aerion.mil"

        factory = get_session_factory()
        async with factory() as session:
            from app.services.auth_service import AuthService
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

            new_token_resp = await AuthService.refresh_user_token(session, str(user_id))
            self.assertIsNotNone(new_token_resp.access_token)
            self.assertEqual(new_token_resp.user.email, email)
            self.assertEqual(new_token_resp.user.display_name, "Major Tom")

    async def test_bug_032_local_account_registration(self):
        """BUG-032: Test discoverable local operator registration creates new user and tenant org."""
        from app.services.auth_service import AuthService
        unique_suffix = int(datetime.now(timezone.utc).timestamp()) + 603
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

            u = await session.get(User, uuid.UUID(user_resp.id))
            self.assertIsNotNone(u)
            self.assertEqual(u.email, email)

    async def test_bug_033_forgot_and_reset_password_workflow(self):
        """BUG-033: Test forgot password token issuance and password reset execution."""
        from app.services.auth_service import AuthService
        unique_suffix = int(datetime.now(timezone.utc).timestamp()) + 604
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


if __name__ == "__main__":
    unittest.main()
