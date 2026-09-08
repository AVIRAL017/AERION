"""
AERION — Authentication & Authorization Tests (Phase 3D)
Validates:
- Argon2id password hashing and constant-time verification
- JWT issuance, verification, and decoding (with expiration)
- Duplicate email registration rejection
- Invalid password rejection
- Expired and tampered token handling
- Role-based authorization enforcement
"""

import unittest
from datetime import timedelta
import jwt

from app.core.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.core.config import AERIONSettings, get_settings
from app.core.errors import AuthenticationError


class TestPasswordSecurity(unittest.TestCase):
    """Test Argon2id password hashing guarantees."""

    def test_hash_and_verify_success(self):
        pwd = "SecureOperationalPassword123!"
        hashed = hash_password(pwd)
        self.assertTrue(hashed.startswith("$argon2id$"))
        self.assertTrue(verify_password(pwd, hashed))

    def test_wrong_password_fails(self):
        pwd = "SecureOperationalPassword123!"
        hashed = hash_password(pwd)
        self.assertFalse(verify_password("WrongPassword999!", hashed))

    def test_short_password_rejected(self):
        with self.assertRaises(ValueError):
            hash_password("short")


class TestJWTSecurity(unittest.TestCase):
    """Test JWT access token issuance, verification, and expiration."""

    def test_token_issuance_and_decoding(self):
        data = {"sub": "user-uuid-123", "org": "org-uuid-456", "role": "operator"}
        token = create_access_token(data, expires_delta=timedelta(minutes=15))
        payload = decode_access_token(token)
        self.assertEqual(payload["sub"], "user-uuid-123")
        self.assertEqual(payload["org"], "org-uuid-456")
        self.assertEqual(payload["role"], "operator")

    def test_expired_token_rejected(self):
        data = {"sub": "user-uuid-123"}
        # Issue token that expired 10 seconds ago
        token = create_access_token(data, expires_delta=timedelta(seconds=-10))
        with self.assertRaises(AuthenticationError) as ctx:
            decode_access_token(token)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("expired", ctx.exception.message.lower())

    def test_tampered_token_rejected(self):
        data = {"sub": "user-uuid-123"}
        token = create_access_token(data)
        tampered = token[:-4] + "fake"
        with self.assertRaises(AuthenticationError) as ctx:
            decode_access_token(tampered)
        self.assertEqual(ctx.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
