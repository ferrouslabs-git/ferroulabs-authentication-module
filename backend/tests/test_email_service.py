"""Unit tests for the email service (SES invitation delivery)."""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.auth_usermanagement.services.email_service import (
    EmailSendResult,
    send_invitation_email,
    _get_invitation_email_html,
    _get_invitation_email_text,
)


# ── Helpers ──────────────────────────────────────────────────────


def _run(coro):
    """Run an async function synchronously for test convenience."""
    return asyncio.run(coro)


_SES_SETTINGS = SimpleNamespace(
    ses_region="eu-west-1",
    ses_sender_email="noreply@example.com",
    frontend_url="https://app.example.com",
)

_NO_SES_SETTINGS = SimpleNamespace(
    ses_region=None,
    ses_sender_email=None,
    frontend_url="https://app.example.com",
)


# ── HTML/Text template tests ────────────────────────────────────


class TestEmailTemplates:
    def test_html_contains_invite_url(self):
        html = _get_invitation_email_html("https://app.test/invite/abc", "Acme Corp")
        assert "https://app.test/invite/abc" in html
        assert "Acme Corp" in html

    def test_text_contains_invite_url(self):
        text = _get_invitation_email_text("https://app.test/invite/abc", "Acme Corp")
        assert "https://app.test/invite/abc" in text
        assert "Acme Corp" in text

    def test_html_escaping_tenant_name(self):
        html = _get_invitation_email_html("https://x.io/invite/t", "O'Reilly & Sons")
        assert "O'Reilly & Sons" in html


# ── send_invitation_email tests ─────────────────────────────────


class TestSendInvitationEmail:
    @patch("app.auth_usermanagement.services.email_service.get_settings")
    @patch("app.auth_usermanagement.services.email_service.boto3")
    def test_success(self, mock_boto3, mock_settings):
        mock_settings.return_value = _SES_SETTINGS
        mock_ses = MagicMock()
        mock_boto3.client.return_value = mock_ses
        mock_ses.send_email.return_value = {"MessageId": "msg-123"}

        result = _run(send_invitation_email("bob@example.com", "https://app.test/invite/x", "TestCo"))

        assert result.sent is True
        assert result.provider == "ses"
        assert result.message_id == "msg-123"
        mock_ses.send_email.assert_called_once()

    @patch("app.auth_usermanagement.services.email_service.get_settings")
    def test_missing_ses_config_returns_not_sent(self, mock_settings):
        mock_settings.return_value = _NO_SES_SETTINGS

        result = _run(send_invitation_email("bob@example.com", "https://app.test/invite/x", "TestCo"))

        assert result.sent is False
        assert "not configured" in result.detail.lower() or "missing" in result.detail.lower()

    @patch("app.auth_usermanagement.services.email_service.get_settings")
    @patch("app.auth_usermanagement.services.email_service.boto3")
    def test_client_error_returns_not_sent(self, mock_boto3, mock_settings):
        mock_settings.return_value = _SES_SETTINGS
        mock_ses = MagicMock()
        mock_boto3.client.return_value = mock_ses
        mock_ses.send_email.side_effect = ClientError(
            {"Error": {"Code": "MessageRejected", "Message": "Email address not verified."}},
            "SendEmail",
        )

        result = _run(send_invitation_email("bob@example.com", "https://app.test/invite/x", "TestCo"))

        assert result.sent is False
        assert "MessageRejected" in result.detail

    @patch("app.auth_usermanagement.services.email_service.get_settings")
    @patch("app.auth_usermanagement.services.email_service.boto3")
    def test_unexpected_error_returns_not_sent(self, mock_boto3, mock_settings):
        mock_settings.return_value = _SES_SETTINGS
        mock_ses = MagicMock()
        mock_boto3.client.return_value = mock_ses
        mock_ses.send_email.side_effect = RuntimeError("network blip")

        result = _run(send_invitation_email("bob@example.com", "https://app.test/invite/x", "TestCo"))

        assert result.sent is False
        assert "network blip" in result.detail


# ── EmailSendResult dataclass tests ─────────────────────────────


class TestEmailSendResult:
    def test_defaults(self):
        r = EmailSendResult(sent=True, provider="ses", detail="ok")
        assert r.message_id is None

    def test_with_message_id(self):
        r = EmailSendResult(sent=True, provider="ses", detail="ok", message_id="m-1")
        assert r.message_id == "m-1"
