"""
AERION — Transactional Notification Email Service (BUG D)
Provides non-blocking security notification emails on successful authentications.

Invariants:
1. Zero fabrication: Server timestamp, genuine email, auth provider, and real IP if present.
2. Non-blocking & Fail-Soft: Failure to deliver an email NEVER aborts or rejects a valid login.
3. Anti-Spam / Duplication: Triggered solely on genuine login (password, Google), never on /auth/refresh or failed attempts.
4. Security: Never logs credentials or secrets; safe provider abstraction (console or smtp).
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger("aerion.services.email")


class EmailService:
    """
    Transactional notification service supporting console and SMTP delivery.
    """

    def __init__(self):
        self.settings = get_settings()

    async def send_login_notification(
        self,
        recipient_email: str,
        auth_method: str = "Password",
        client_ip: Optional[str] = None,
        login_timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        Sends an asynchronous security notification email after successful authentication.
        Safe wrapper that handles delivery exceptions without disrupting the caller.
        """
        ts = login_timestamp or datetime.now(timezone.utc)
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S UTC")
        ip_display = client_ip if client_ip and client_ip != "unknown" else "Unavailable"

        subject = "AERION — New Sign-In Detected"
        body = (
            f"A new sign-in to your AERION account was detected.\n\n"
            f"Time: {ts_str}\n"
            f"Authentication method: {auth_method}\n"
            f"Account: {recipient_email}\n"
            f"IP address: {ip_display}\n\n"
            f"If you did not perform this login, please contact your security administrator immediately.\n"
        )

        provider = (self.settings.EMAIL_PROVIDER or "console").lower()

        if provider == "smtp":
            return await self._send_smtp_async(recipient_email, subject, body)
        else:
            # Console / log provider (default)
            logger.info(
                f"[NOTIFICATION EMAIL - {provider.upper()}] To: {recipient_email} | Subject: '{subject}' | "
                f"Method: {auth_method} | Time: {ts_str} | IP: {ip_display}"
            )
            return True

    async def _send_smtp_async(self, recipient_email: str, subject: str, body: str) -> bool:
        """Runs synchronous SMTP delivery in threadpool to keep event loop unblocked."""
        return await asyncio.to_thread(self._send_smtp_sync, recipient_email, subject, body)

    def _send_smtp_sync(self, recipient_email: str, subject: str, body: str) -> bool:
        """Synchronous SMTP transport."""
        host = self.settings.SMTP_HOST
        port = self.settings.SMTP_PORT
        from_addr = self.settings.SMTP_FROM

        if not host:
            logger.warning("SMTP provider configured but SMTP_HOST is not set; falling back to console log.")
            logger.info(f"[NOTIFICATION EMAIL - CONSOLE FALLBACK] To: {recipient_email} | Subject: {subject}\n{body}")
            return False

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = recipient_email
        msg.set_content(body)

        try:
            with smtplib.SMTP(host, port, timeout=10) as server:
                if self.settings.SMTP_USE_TLS:
                    server.starttls()
                if self.settings.SMTP_USER and self.settings.SMTP_PASSWORD:
                    server.login(self.settings.SMTP_USER, self.settings.SMTP_PASSWORD.get_secret_value())
                server.send_message(msg)
            logger.info(f"Successfully sent login notification email to {recipient_email} via SMTP")
            return True
        except Exception as exc:
            logger.warning(f"Failed to deliver login notification email via SMTP: {exc}")
            return False


email_service = EmailService()
