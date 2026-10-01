"""
AERION — Authentication & Authorization Schemas (Phase 3D)
Defines registration, login, token envelopes, user profiles, and roles.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    ANALYST = "analyst"


class UserRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=255, pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$", description="Valid email address")
    password: str = Field(min_length=8, description="Minimum 8 characters")
    organization_name: str = Field(min_length=2, max_length=100)
    display_name: Optional[str] = Field(default=None, max_length=100)
    role: UserRole = Field(default=UserRole.OPERATOR)


class UserLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=255, description="User email address")
    password: str


class GoogleLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_token: str = Field(min_length=10, description="Google OAuth 2.0 cryptographically signed ID token")


class UserResponse(BaseModel):
    id: str
    organization_id: str
    organization_name: Optional[str] = None
    email: str
    role: str
    auth_provider: str = "local"
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in_seconds: int
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Optional explicitly provided token; if not provided, uses the active Authorization header
    token: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=255, description="Registered user email address")


class ForgotPasswordResponse(BaseModel):
    message: str
    delivery_status: str
    # Honest development token: only provided for testing/local development without SMTP server
    reset_token: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=16, description="Cryptographic single-use reset token")
    new_password: str = Field(min_length=8, description="Minimum 8 characters")


class UpdateProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: Optional[str] = Field(default=None, max_length=100)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, description="Current password")
    new_password: str = Field(min_length=8, description="Minimum 8 characters")


class AvatarUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    avatar_base64: str = Field(description="Base64 encoded avatar image data")


class UpdatePreferencesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="User preference key-value mapping")

