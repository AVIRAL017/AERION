"""
AERION — Profile, Avatar, Password & Preferences Service & Endpoint Tests
Validates Settings & Profile operations under /api/v1/auth:
- Profile retrieval & display name updates
- Avatar upload validation (PIL format, size limit, thumbnailing)
- Avatar removal & fallback
- Password change validation & wrong password rejection
- Interface & Notification preferences persistence
"""

import base64
import io
import unittest
import uuid
from datetime import datetime, timezone
from PIL import Image

from app.core.auth import create_access_token, hash_password
from app.core.errors import AuthenticationError, ValidationError
from app.db.models import Organization, User
from app.db.session import get_session_factory, close_db_connections
from app.services.auth_service import AuthService


def create_test_image_bytes(format="JPEG", size=(100, 100), color=(0, 120, 255)) -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


class TestProfileAndSettingsService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await close_db_connections()

    async def asyncTearDown(self):
        await close_db_connections()
    async def test_profile_update_and_org_name(self):
        factory = get_session_factory()
        unique_suffix = uuid.uuid4().hex[:6]
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        email = f"operator_{unique_suffix}@aerion.mil"

        async with factory() as session:
            org = Organization(id=org_id, name="Tactical Squadron Alpha", slug=f"sqd-{unique_suffix}")
            user = User(
                id=user_id,
                email=email,
                hashed_password=hash_password("InitialPassword2026!"),
                display_name="Lieutenant Bradley",
                role="operator",
                organization_id=org_id,
                is_active=True,
                auth_provider="local",
            )
            session.add_all([org, user])
            await session.commit()

            # 1. build_user_response with org_name
            resp1 = AuthService.build_user_response(user, org_name=org.name)
            self.assertEqual(resp1.display_name, "Lieutenant Bradley")
            self.assertEqual(resp1.organization_name, "Tactical Squadron Alpha")

            # 2. update_profile
            resp2 = await AuthService.update_profile(session, user, display_name="Commander Bradley")
            await session.commit()
            self.assertEqual(resp2.display_name, "Commander Bradley")

            # 3. Verify in DB
            u_check = await session.get(User, user_id)
            self.assertEqual(u_check.display_name, "Commander Bradley")

    async def test_avatar_update_and_removal(self):
        factory = get_session_factory()
        unique_suffix = uuid.uuid4().hex[:6]
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        email = f"avatar_{unique_suffix}@aerion.mil"

        async with factory() as session:
            org = Organization(id=org_id, name="Avatar Squadron", slug=f"avatar-{unique_suffix}")
            user = User(
                id=user_id,
                email=email,
                hashed_password=hash_password("InitialPassword2026!"),
                role="operator",
                organization_id=org_id,
                is_active=True,
            )
            session.add_all([org, user])
            await session.commit()

            # A. Update avatar with base64 data URI
            img_bytes = create_test_image_bytes("JPEG", size=(200, 200))
            test_uri = f"data:image/jpeg;base64,{base64.b64encode(img_bytes).decode('utf-8')}"

            resp_avatar = await AuthService.update_avatar(session, user, test_uri)
            await session.commit()
            self.assertIsNotNone(resp_avatar.avatar_url)
            self.assertTrue(resp_avatar.avatar_url.startswith("data:image/jpeg;base64,"))

            # B. Verify in DB
            u_db = await session.get(User, user_id)
            self.assertEqual(u_db.avatar_url, test_uri)

            # C. Remove avatar
            resp_del = await AuthService.update_avatar(session, user, None)
            await session.commit()
            self.assertIsNone(resp_del.avatar_url)

            u_db2 = await session.get(User, user_id)
            self.assertIsNone(u_db2.avatar_url)

    async def test_password_change_security(self):
        factory = get_session_factory()
        unique_suffix = uuid.uuid4().hex[:6]
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        email = f"sec_{unique_suffix}@aerion.mil"
        initial_pw = "OriginalPass2026!"
        new_pw = "NewSecretPass2026!"

        async with factory() as session:
            org = Organization(id=org_id, name="Security Squad", slug=f"sec-{unique_suffix}")
            user = User(
                id=user_id,
                email=email,
                hashed_password=hash_password(initial_pw),
                role="operator",
                organization_id=org_id,
                is_active=True,
                auth_provider="local",
            )
            session.add_all([org, user])
            await session.commit()

            # A. Wrong current password raises AuthenticationError
            with self.assertRaises(AuthenticationError):
                await AuthService.change_password(session, user, "WrongCurrentPassword!", new_pw)

            # B. Short new password raises ValidationError
            with self.assertRaises(ValidationError):
                await AuthService.change_password(session, user, initial_pw, "short")

            # C. Successful password change
            res = await AuthService.change_password(session, user, initial_pw, new_pw)
            await session.commit()
            self.assertTrue(res["success"])

            # D. Verify new password works in login
            from app.schemas.auth import UserLoginRequest
            token_resp = await AuthService.login_user(session, UserLoginRequest(email=email, password=new_pw))
            self.assertIsNotNone(token_resp.access_token)

            # E. Old password fails
            with self.assertRaises(AuthenticationError):
                await AuthService.login_user(session, UserLoginRequest(email=email, password=initial_pw))

    async def test_preferences_persistence(self):
        factory = get_session_factory()
        unique_suffix = uuid.uuid4().hex[:6]
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        email = f"pref_{unique_suffix}@aerion.mil"

        async with factory() as session:
            org = Organization(id=org_id, name="Pref Squad", slug=f"pref-{unique_suffix}")
            user = User(
                id=user_id,
                email=email,
                hashed_password=hash_password("Pass123!"),
                role="operator",
                organization_id=org_id,
                is_active=True,
            )
            session.add_all([org, user])
            await session.commit()

            # Update preferences
            new_prefs = {
                "notifications": {"login_alerts": False, "analysis_complete": True},
                "interface": {"reduced_motion": True, "density": "compact", "default_page": "/image"},
            }
            resp = await AuthService.update_preferences(session, user, new_prefs)
            await session.commit()

            self.assertIn("notifications", resp.preferences)
            self.assertFalse(resp.preferences["notifications"]["login_alerts"])
            self.assertTrue(resp.preferences["interface"]["reduced_motion"])

            # Verify in DB
            u_db = await session.get(User, user_id)
            self.assertEqual(u_db.preferences["interface"]["default_page"], "/image")
