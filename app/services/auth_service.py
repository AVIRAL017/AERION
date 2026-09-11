"""
AERION — Authentication & Authorization Service (Phase 3D)
Handles user registration, credential verification, JWT issuance,
and tenant boundaries.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password, verify_password, create_access_token
from app.core.config import get_settings
from app.core.errors import AuthenticationError, PermissionDeniedError, ValidationError
from app.db.models import Organization, User, Subscription
from app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    UserRole,
)

logger = logging.getLogger("aerion.services.auth")


class AuthService:
    """Service mediating user identity and access tokens."""

    @staticmethod
    async def register_user(
        session: AsyncSession,
        req: UserRegisterRequest,
    ) -> Tuple[UserResponse, TokenResponse]:
        # Check duplicate email
        stmt = select(User).where(User.email == req.email)
        res = await session.execute(stmt)
        if res.scalar_one_or_none() is not None:
            raise ValidationError(
                message=f"User with email '{req.email}' already exists.",
                details=[{"field": "email", "issue": "duplicate_entry", "provided": req.email}],
            )

        # Create Organization
        slug = req.organization_name.lower().replace(" ", "-") + f"-{str(uuid.uuid4())[:8]}"
        org = Organization(name=req.organization_name, slug=slug)
        session.add(org)
        await session.flush()

        # Create Default Subscription (FREE plan)
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        sub = Subscription(
            organization_id=org.id,
            plan="FREE",
            price_inr=0,
            is_active=True,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        session.add(sub)

        # Hash password and create User
        hashed_pwd = hash_password(req.password)
        user = User(
            organization_id=org.id,
            email=req.email,
            hashed_password=hashed_pwd,
            role=req.role.value,
            is_active=True,
        )
        session.add(user)
        await session.flush()

        user_resp = UserResponse(
            id=str(user.id),
            organization_id=str(org.id),
            email=user.email,
            role=user.role,
            auth_provider=user.auth_provider,
            display_name=user.display_name,
            is_active=user.is_active,
            created_at=user.created_at,
        )

        settings = get_settings()
        token = create_access_token({
            "sub": str(user.id),
            "org": str(org.id),
            "role": user.role,
            "email": user.email,
        })

        token_resp = TokenResponse(
            access_token=token,
            token_type="Bearer",
            expires_in_seconds=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_resp,
        )
        return user_resp, token_resp

    @staticmethod
    async def login_user(
        session: AsyncSession,
        req: UserLoginRequest,
    ) -> TokenResponse:
        stmt = select(User).where(User.email == req.email)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()

        if user is None or not user.hashed_password or not verify_password(req.password, user.hashed_password):
            # Generic error message to prevent enumeration
            raise AuthenticationError("Invalid email or password.")

        if not user.is_active:
            raise PermissionDeniedError("User account is deactivated.")

        user_resp = UserResponse(
            id=str(user.id),
            organization_id=str(user.organization_id),
            email=user.email,
            role=user.role,
            auth_provider=user.auth_provider,
            display_name=user.display_name,
            is_active=user.is_active,
            created_at=user.created_at,
        )

        settings = get_settings()
        token = create_access_token({
            "sub": str(user.id),
            "org": str(user.organization_id),
            "role": user.role,
            "email": user.email,
        })

        return TokenResponse(
            access_token=token,
            token_type="Bearer",
            expires_in_seconds=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_resp,
        )

    @staticmethod
    async def login_with_google(
        session: AsyncSession,
        id_token_str: str,
    ) -> TokenResponse:
        """
        Verifies Google ID token and performs secure login or account provisioning:
        1. Cryptographically verifies token signature, audience, expiration, and verified email.
        2. Queries by immutable Google subject ID ('provider_sub').
        3. If not found by 'provider_sub', checks by verified email. Links Google account if found.
        4. If account does not exist, automatically provisions a new Organization and Operator User.
        5. Fails closed if account is deactivated.
        6. Issues standard signed AERION JWT access token.
        """
        from app.core.google_auth import GoogleAuthVerifier
        from datetime import datetime, timedelta, timezone

        # 1. Cryptographic token verification
        idinfo = GoogleAuthVerifier.verify_id_token(id_token_str)
        google_sub = str(idinfo["sub"])
        google_email = str(idinfo["email"]).lower().strip()
        google_name = idinfo.get("name") or google_email.split("@")[0]

        # 2. Lookup by immutable Google Subject ID
        stmt_sub = select(User).where(User.provider_sub == google_sub)
        res_sub = await session.execute(stmt_sub)
        user = res_sub.scalar_one_or_none()

        if user is None:
            # 3. Lookup by email to link existing account
            stmt_email = select(User).where(User.email == google_email)
            res_email = await session.execute(stmt_email)
            existing_email_user = res_email.scalar_one_or_none()

            if existing_email_user is not None:
                user = existing_email_user
                user.provider_sub = google_sub
                if not user.display_name:
                    user.display_name = google_name
                await session.flush()
                logger.info(f"Linked Google identity (sub={google_sub}) to existing user email {google_email}")
            else:
                # 4. First-time Google user: provision Organization + Free subscription + User
                org_name = f"{google_name}'s Operations"
                slug = f"org-{uuid.uuid4().hex[:8]}"
                org = Organization(name=org_name, slug=slug)
                session.add(org)
                await session.flush()

                now = datetime.now(timezone.utc)
                sub = Subscription(
                    organization_id=org.id,
                    plan="FREE",
                    price_inr=0,
                    is_active=True,
                    current_period_start=now,
                    current_period_end=now + timedelta(days=30),
                )
                session.add(sub)

                user = User(
                    organization_id=org.id,
                    email=google_email,
                    hashed_password=None,
                    auth_provider="google",
                    provider_sub=google_sub,
                    display_name=google_name,
                    role="operator",
                    is_active=True,
                )
                session.add(user)
                await session.flush()
                logger.info(f"Provisioned new AERION user via Google Sign-In (email={google_email}, sub={google_sub})")

        # 5. Active state verification
        if not user.is_active:
            raise PermissionDeniedError("User account is deactivated.")

        user_resp = UserResponse(
            id=str(user.id),
            organization_id=str(user.organization_id),
            email=user.email,
            role=user.role,
            auth_provider=user.auth_provider,
            display_name=user.display_name,
            is_active=user.is_active,
            created_at=user.created_at,
        )

        # 6. Standard AERION JWT issuance
        settings = get_settings()
        token = create_access_token({
            "sub": str(user.id),
            "org": str(user.organization_id),
            "role": user.role,
            "email": user.email,
        })

        return TokenResponse(
            access_token=token,
            token_type="Bearer",
            expires_in_seconds=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_resp,
        )

