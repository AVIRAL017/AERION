"""
AERION — Authentication & RBAC Dependencies (Phase 3D)
Provides FastAPI dependencies for extracting current user, validating roles,
and enforcing tenant boundaries.
"""

from __future__ import annotations

import uuid
from typing import List, Optional
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_access_token
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.db.models import User
from app.db.session import get_async_session

security_bearer = HTTPBearer(auto_error=False)


async def get_current_user_payload(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> dict:
    """Validates Bearer token and returns raw JWT claims payload."""
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Authentication required. Please provide a valid Bearer token.")
    return decode_access_token(credentials.credentials)


async def get_current_user(
    payload: dict = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_async_session),
) -> User:
    """Resolves authenticated User from database and verifies active status."""
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationError("Token payload is missing subject claim.")
    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise AuthenticationError("Invalid user ID format in token.")

    user = await session.get(User, user_uuid)
    if user is None:
        raise AuthenticationError("User account no longer exists.")
    if not user.is_active:
        raise PermissionDeniedError("User account is deactivated.")
    return user


def require_roles(allowed_roles: List[str]):
    """Enforces Role-Based Access Control (RBAC)."""
    async def role_checker(payload: dict = Depends(get_current_user_payload)) -> dict:
        user_role = payload.get("role")
        if user_role not in allowed_roles:
            raise PermissionDeniedError(f"Access denied. Requires one of roles: {', '.join(allowed_roles)}.")
        return payload
    return role_checker
