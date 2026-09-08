"""
AERION — Authentication & Authorization Schemas (Phase 3D)
Defines registration, login, token envelopes, user profiles, and roles.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional
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
    role: UserRole = Field(default=UserRole.OPERATOR)


class UserLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=255, description="User email address")
    password: str


class UserResponse(BaseModel):
    id: str
    organization_id: str
    email: str
    role: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in_seconds: int
    user: UserResponse
