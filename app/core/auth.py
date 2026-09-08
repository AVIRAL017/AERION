"""
AERION — Password Hashing & JWT Security Primitives (Phase 3D)
Implements:
- Argon2id password hashing and verification
- JWT issuance, verification, and decoding (with expiration checks)
- Fail-closed security invariants
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHash
import jwt

from app.core.config import get_settings
from app.core.errors import AuthenticationError

logger = logging.getLogger("aerion.security.auth")

# Configure Argon2id password hasher with RFC-recommended parameters
_ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    return _ph.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash. Never throws."""
    try:
        return _ph.verify(hashed_password, password)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False
    except Exception as exc:
        logger.warning(f"Unexpected error verifying password: {type(exc).__name__}")
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Issues a cryptographically signed JWT access token."""
    settings = get_settings()
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": now})
    secret = settings.JWT_SECRET_KEY.get_secret_value()
    encoded = jwt.encode(to_encode, secret, algorithm=settings.JWT_ALGORITHM)
    return encoded


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decodes and validates a JWT access token. Fails closed on expired/tampered tokens."""
    settings = get_settings()
    secret = settings.JWT_SECRET_KEY.get_secret_value()
    try:
        payload = jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired. Please authenticate again.")
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid authentication credentials.")
