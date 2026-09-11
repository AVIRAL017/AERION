"""
AERION — Google OAuth ID Token Verification Engine (Step 32)
Cryptographically verifies Google ID tokens using Google's public key infrastructure.
Enforces fail-closed security invariants:
1. Valid cryptographic signature verified against Google's public keys.
2. Issuer must be 'accounts.google.com' or 'https://accounts.google.com'.
3. Audience must strictly match AERION's configured Google Client ID.
4. Token must not be expired.
5. Email must be present and verified ('email_verified' == True).
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from google.auth.transport import requests
from google.oauth2 import id_token

from app.core.config import get_settings
from app.core.errors import AuthenticationError

logger = logging.getLogger("aerion.security.google_auth")

# Reusable transport request session for public key retrieval
_transport_request = requests.Request()


class GoogleAuthVerifier:
    """Verifies Google ID tokens and returns verified claims payload."""

    @staticmethod
    def verify_id_token(token_str: str, client_id_override: str | None = None) -> Dict[str, Any]:
        """
        Cryptographically verifies a Google ID token.
        Raises AuthenticationError on any invalid, expired, wrong-audience, or unverified token.
        """
        if not token_str or not token_str.strip():
            raise AuthenticationError("Google ID token is required.")

        settings = get_settings()
        expected_client_id = client_id_override or settings.GOOGLE_CLIENT_ID

        if not expected_client_id:
            raise AuthenticationError("Google authentication is not configured on this server.")

        try:
            # Cryptographically verify token signature, expiry, and audience using Google's certs
            idinfo: Dict[str, Any] = id_token.verify_oauth2_token(
                token_str,
                _transport_request,
                expected_client_id,
            )
        except ValueError as exc:
            # Capture specific verification failures without leaking internal details
            err_msg = str(exc)
            logger.warning(f"Google ID token verification failed: {err_msg}")
            if "expired" in err_msg.lower():
                raise AuthenticationError("Google ID token has expired. Please sign in again.")
            if "audience" in err_msg.lower():
                raise AuthenticationError("Google ID token audience mismatch.")
            if "issuer" in err_msg.lower():
                raise AuthenticationError("Google ID token issuer mismatch.")
            raise AuthenticationError(f"Invalid Google ID token: {err_msg}")
        except Exception as exc:
            logger.error(f"Unexpected error during Google ID token verification: {exc}")
            raise AuthenticationError("Failed to verify Google ID token.")

        # Invariant checks
        issuer = idinfo.get("iss")
        if issuer not in ("accounts.google.com", "https://accounts.google.com"):
            raise AuthenticationError("Invalid Google ID token issuer.")

        sub = idinfo.get("sub")
        if not sub:
            raise AuthenticationError("Google ID token missing subject ('sub') claim.")

        email = idinfo.get("email")
        if not email:
            raise AuthenticationError("Google ID token missing email claim.")

        email_verified = idinfo.get("email_verified")
        if not email_verified:
            raise AuthenticationError("Google account email address is not verified.")

        return idinfo
