"""
AERION — Authentication Endpoints (Phase 3D)
Handles user registration, login, and profile retrieval under /api/v1/auth.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.models import User
from app.db.session import get_async_session
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    GoogleLoginRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.schemas.common import MetaBlock, ResponseEnvelope, utc_now_iso
from app.services.auth_service import AuthService
from app.services.email_service import email_service
import asyncio

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _extract_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req-unknown")


@router.post(
    "/register",
    response_model=ResponseEnvelope[TokenResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user and organization",
)
async def register(
    req: UserRegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> ResponseEnvelope[TokenResponse]:
    settings = get_settings()
    _, token_resp = await AuthService.register_user(session, req)
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=token_resp, meta=meta)


@router.post(
    "/login",
    response_model=ResponseEnvelope[TokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Authenticate user credentials and issue JWT access token",
)
async def login(
    req: UserLoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> ResponseEnvelope[TokenResponse]:
    settings = get_settings()
    token_resp = await AuthService.login_user(session, req)
    
    # Asynchronous non-blocking login notification email (BUG D)
    client_ip = request.client.host if request.client else None
    asyncio.create_task(
        email_service.send_login_notification(
            recipient_email=req.username,
            auth_method="Password",
            client_ip=client_ip,
        )
    )

    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=token_resp, meta=meta)


@router.post(
    "/refresh",
    response_model=ResponseEnvelope[TokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Renew active JWT access token without requiring re-authentication",
)
async def refresh_token(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ResponseEnvelope[TokenResponse]:
    settings = get_settings()
    token_resp = await AuthService.refresh_user_token(session, str(current_user.id))
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=token_resp, meta=meta)


@router.post(
    "/forgot-password",
    response_model=ResponseEnvelope[ForgotPasswordResponse],
    status_code=status.HTTP_200_OK,
    summary="Request a password reset link or token for local account",
)
async def forgot_password(
    req: ForgotPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> ResponseEnvelope[ForgotPasswordResponse]:
    settings = get_settings()
    res = await AuthService.initiate_password_reset(session, req.email)
    data = ForgotPasswordResponse(
        message=res["message"],
        delivery_status=res["delivery_status"],
        reset_token=res.get("reset_token"),
    )
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=data, meta=meta)


@router.post(
    "/reset-password",
    response_model=ResponseEnvelope[dict],
    status_code=status.HTTP_200_OK,
    summary="Complete password reset using cryptographic single-use token",
)
async def reset_password(
    req: ResetPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> ResponseEnvelope[dict]:
    settings = get_settings()
    res = await AuthService.complete_password_reset(session, req.token, req.new_password)
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=res, meta=meta)


@router.post(
    "/google",
    response_model=ResponseEnvelope[TokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Authenticate via Google OAuth ID Token and issue JWT access token",
)
async def google_login(
    req: GoogleLoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> ResponseEnvelope[TokenResponse]:
    settings = get_settings()
    token_resp = await AuthService.login_with_google(session, req.id_token)
    
    # Asynchronous non-blocking login notification email (BUG D)
    client_ip = request.client.host if request.client else None
    user_email = token_resp.user.email if token_resp.user else "Unknown"
    asyncio.create_task(
        email_service.send_login_notification(
            recipient_email=user_email,
            auth_method="Google",
            client_ip=client_ip,
        )
    )

    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=token_resp, meta=meta)


@router.post(
    "/logout",
    response_model=ResponseEnvelope[dict],
    status_code=status.HTTP_200_OK,
    summary="Invalidate client session / record session termination",
)
async def logout(
    request: Request,
) -> ResponseEnvelope[dict]:
    settings = get_settings()
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data={"message": "Logged out successfully."}, meta=meta)


@router.get(
    "/me",
    response_model=ResponseEnvelope[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve profile of currently authenticated user",
)
async def get_me(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> ResponseEnvelope[UserResponse]:
    settings = get_settings()
    user_resp = UserResponse(
        id=str(current_user.id),
        organization_id=str(current_user.organization_id),
        email=current_user.email,
        role=current_user.role,
        auth_provider=current_user.auth_provider,
        display_name=current_user.display_name,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=user_resp, meta=meta)


