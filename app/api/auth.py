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
from app.core.errors import ValidationError
from app.schemas.auth import (
    AvatarUploadRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    GoogleLoginRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    TokenResponse,
    UpdatePreferencesRequest,
    UpdateProfileRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.schemas.common import MetaBlock, ResponseEnvelope, utc_now_iso
from app.services.auth_service import AuthService
from app.services.email_service import email_service
import asyncio
import base64
import io
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import selectinload

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
            recipient_email=req.email,
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
    session: AsyncSession = Depends(get_async_session),
) -> ResponseEnvelope[UserResponse]:
    settings = get_settings()
    stmt = select(User).options(selectinload(User.organization)).where(User.id == current_user.id)
    res = await session.execute(stmt)
    user_loaded = res.scalar_one_or_none() or current_user
    user_resp = AuthService.build_user_response(user_loaded)
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=user_resp, meta=meta)


@router.patch(
    "/profile",
    response_model=ResponseEnvelope[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Update authenticated user profile information",
)
async def update_profile(
    req: UpdateProfileRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ResponseEnvelope[UserResponse]:
    settings = get_settings()
    user_resp = await AuthService.update_profile(session, current_user, req.display_name)
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=user_resp, meta=meta)


@router.post(
    "/avatar",
    response_model=ResponseEnvelope[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Upload and set profile avatar image",
)
async def upload_avatar(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ResponseEnvelope[UserResponse]:
    settings = get_settings()
    content_type = request.headers.get("content-type", "")
    raw_bytes: bytes = b""

    if "multipart/form-data" in content_type:
        form = await request.form()
        uploaded_file = form.get("file") or form.get("avatar")
        if not uploaded_file or not hasattr(uploaded_file, "read"):
            raise ValidationError("No image file provided in multipart upload.")
        raw_bytes = await uploaded_file.read()
    else:
        # JSON payload with avatar_base64
        try:
            body = await request.json()
        except Exception:
            raise ValidationError("Invalid JSON request body.")
        b64_str = body.get("avatar_base64")
        if not b64_str:
            raise ValidationError("Missing 'avatar_base64' in payload.")
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        try:
            raw_bytes = base64.b64decode(b64_str)
        except Exception:
            raise ValidationError("Malformed base64 image data.")

    # Size check (2MB max)
    if len(raw_bytes) > 2 * 1024 * 1024:
        raise ValidationError("Avatar image exceeds 2MB limit.")
    if len(raw_bytes) < 16:
        raise ValidationError("Image file is empty or too small.")

    # Verification with PIL
    try:
        test_img = Image.open(io.BytesIO(raw_bytes))
        test_img.verify()
    except Exception:
        raise ValidationError("Corrupted or unsupported image file. Must be a valid JPEG, PNG, or WebP image.")

    # Re-open for transformation
    proc_img = Image.open(io.BytesIO(raw_bytes))
    if proc_img.format not in ("JPEG", "PNG", "WEBP", "MPO"):
        raise ValidationError(f"Unsupported image format ({proc_img.format}). Only JPEG, PNG, and WebP are allowed.")

    # Square crop & thumbnail to 256x256
    proc_img = proc_img.convert("RGB")
    w, h = proc_img.size
    min_dim = min(w, h)
    left = (w - min_dim) // 2
    top = (h - min_dim) // 2
    cropped = proc_img.crop((left, top, left + min_dim, top + min_dim))
    cropped = cropped.resize((256, 256), Image.Resampling.LANCZOS)

    out_buf = io.BytesIO()
    cropped.save(out_buf, format="JPEG", quality=85, optimize=True)
    data_uri = f"data:image/jpeg;base64,{base64.b64encode(out_buf.getvalue()).decode('utf-8')}"

    user_resp = await AuthService.update_avatar(session, current_user, data_uri)
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=user_resp, meta=meta)


@router.delete(
    "/avatar",
    response_model=ResponseEnvelope[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Remove avatar image and revert to default initials avatar",
)
async def delete_avatar(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ResponseEnvelope[UserResponse]:
    settings = get_settings()
    user_resp = await AuthService.update_avatar(session, current_user, None)
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=user_resp, meta=meta)


@router.patch(
    "/password",
    response_model=ResponseEnvelope[dict],
    status_code=status.HTTP_200_OK,
    summary="Change password for authenticated local account",
)
async def change_password(
    req: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ResponseEnvelope[dict]:
    settings = get_settings()
    res = await AuthService.change_password(session, current_user, req.current_password, req.new_password)
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=res, meta=meta)


@router.get(
    "/preferences",
    response_model=ResponseEnvelope[dict],
    status_code=status.HTTP_200_OK,
    summary="Retrieve user interface and notification preferences",
)
async def get_preferences(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> ResponseEnvelope[dict]:
    settings = get_settings()
    default_prefs = {
        "notifications": {
            "login_alerts": True,
            "analysis_complete": True,
            "failure_alerts": True,
            "report_ready": True,
        },
        "interface": {
            "reduced_motion": False,
            "density": "comfortable",
            "animations": True,
            "default_page": "/border",
        }
    }
    current_prefs = dict(default_prefs)
    if current_user.preferences:
        current_prefs.update(current_user.preferences)
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=current_prefs, meta=meta)


@router.patch(
    "/preferences",
    response_model=ResponseEnvelope[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Update user interface and notification preferences",
)
async def update_preferences(
    req: UpdatePreferencesRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ResponseEnvelope[UserResponse]:
    settings = get_settings()
    user_resp = await AuthService.update_preferences(session, current_user, req.preferences)
    meta = MetaBlock(
        timestamp=utc_now_iso(),
        request_id=_extract_request_id(request),
        version=settings.API_VERSION,
    )
    return ResponseEnvelope(success=True, data=user_resp, meta=meta)



