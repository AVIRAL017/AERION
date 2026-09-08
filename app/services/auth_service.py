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

        if user is None or not verify_password(req.password, user.hashed_password):
            # Generic error message to prevent enumeration
            raise AuthenticationError("Invalid email or password.")

        if not user.is_active:
            raise PermissionDeniedError("User account is deactivated.")

        user_resp = UserResponse(
            id=str(user.id),
            organization_id=str(user.organization_id),
            email=user.email,
            role=user.role,
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
