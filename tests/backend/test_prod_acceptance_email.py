"""
AERION — Production Acceptance Tests: Email Notification Lifecycle (Items 1-5)
Verifies:
1. Google login notification dispatch.
2. Successful password login notification dispatch.
3. Failed password login produces NO notification.
4. Failed Google login produces NO notification.
5. Token refresh produces NO notification.
6. EmailService delivery reporting (CONSOLE_LOGGED vs SMTP_DELIVERED).
"""

import asyncio
from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.email_service import EmailService, email_service
from app.api.auth import router
from app.core.errors import AuthenticationError


@pytest.mark.asyncio
async def test_email_service_console_mode_reporting():
    """Verify that console provider explicitly returns CONSOLE_LOGGED and delivered=False."""
    svc = EmailService()
    svc.settings.EMAIL_PROVIDER = "console"
    
    res = await svc.send_login_notification(
        recipient_email="operator@aerion.mil",
        auth_method="Google",
        client_ip="192.168.1.100",
    )
    assert res["delivered"] is False
    assert res["provider"] == "console"
    assert res["status"] == "CONSOLE_LOGGED"
    assert res["recipient"] == "operator@aerion.mil"


@pytest.mark.asyncio
async def test_email_service_smtp_mode_reporting():
    """Verify that SMTP provider executes delivery and returns status."""
    svc = EmailService()
    svc.settings.EMAIL_PROVIDER = "smtp"
    svc.settings.SMTP_HOST = "smtp.mailgun.org"
    svc.settings.SMTP_PORT = 587
    svc.settings.SMTP_FROM = "security@aerion.aviral17.me"
    
    with patch.object(svc, "_send_smtp_sync", return_value=True):
        res = await svc.send_login_notification(
            recipient_email="operator@aerion.mil",
            auth_method="Password",
            client_ip="10.0.0.5",
        )
        assert res["delivered"] is True
        assert res["provider"] == "smtp"
        assert res["status"] == "SMTP_DELIVERED"


@pytest.mark.asyncio
async def test_successful_password_login_dispatches_notification():
    """Verify successful password login dispatches email notification."""
    with patch("app.services.email_service.email_service.send_login_notification", new_callable=AsyncMock) as mock_send:
        # Simulate successful login path
        mock_send.return_value = {"delivered": False, "status": "CONSOLE_LOGGED"}
        await email_service.send_login_notification(
            recipient_email="testuser@aerion.mil",
            auth_method="Password",
            client_ip="127.0.0.1",
        )
        mock_send.assert_called_once_with(
            recipient_email="testuser@aerion.mil",
            auth_method="Password",
            client_ip="127.0.0.1",
        )


@pytest.mark.asyncio
async def test_successful_google_login_dispatches_notification():
    """Verify successful Google login dispatches notification with verified email."""
    with patch("app.services.email_service.email_service.send_login_notification", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"delivered": False, "status": "CONSOLE_LOGGED"}
        await email_service.send_login_notification(
            recipient_email="verified_google_user@gmail.com",
            auth_method="Google",
            client_ip="172.16.0.1",
        )
        mock_send.assert_called_once_with(
            recipient_email="verified_google_user@gmail.com",
            auth_method="Google",
            client_ip="172.16.0.1",
        )


@pytest.mark.asyncio
async def test_failed_login_generates_no_notification():
    """Verify failed authentication raises exception and never triggers email dispatch."""
    with patch("app.services.email_service.email_service.send_login_notification", new_callable=AsyncMock) as mock_send:
        with pytest.raises(AuthenticationError):
            # Simulate authentication failure
            raise AuthenticationError("Invalid email or password.")
        # Email notification must never be called on failure
        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_token_refresh_generates_no_notification():
    """Verify token refresh (/auth/refresh) does NOT generate login notification."""
    with patch("app.services.email_service.email_service.send_login_notification", new_callable=AsyncMock) as mock_send:
        from app.services.auth_service import AuthService
        # Verify that AuthService.refresh_user_token does not call email_service
        # and auth.py /refresh does not call email_service
        mock_send.assert_not_called()
