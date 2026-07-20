"""Outbound webhook automation tests."""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from callbot_platform.automation.service import AutomationError, AutomationService
from callbot_platform.automation.webhooks import (
    WebhookError,
    deliver_webhook,
    normalize_webhook_config,
    validate_webhook_url,
)
from callbot_platform.db.models import Tenant


def _public_addrinfo(host: str = "hooks.example.com"):
    return [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("93.184.216.34", 443),
        )
    ]


def test_rejects_http_and_private_hosts() -> None:
    with pytest.raises(WebhookError):
        validate_webhook_url("http://example.com/hook")
    with pytest.raises(WebhookError):
        validate_webhook_url("https://localhost/hook")
    with patch(
        "callbot_platform.automation.webhooks.socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))],
    ):
        with pytest.raises(WebhookError) as exc:
            validate_webhook_url("https://evil.internal/hook")
        assert exc.value.code == "invalid_webhook_url"


def test_normalize_and_deliver_signed_webhook() -> None:
    with patch(
        "callbot_platform.automation.webhooks.socket.getaddrinfo",
        side_effect=lambda *a, **k: _public_addrinfo(),
    ):
        cfg = normalize_webhook_config(
            {
                "url": "https://hooks.example.com/callbot",
                "secret": "s3cret",
                "timeout_sec": 3,
            }
        )
        assert cfg["url"].startswith("https://")
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_response
        with patch(
            "callbot_platform.automation.webhooks.httpx.Client",
            return_value=mock_client,
        ):
            result = deliver_webhook(
                url=cfg["url"],
                payload={"call_id": "abc"},
                secret=cfg["secret"],
                timeout_sec=cfg["timeout_sec"],
                event="call.ended",
                tenant_id=str(uuid4()),
                rule_id=str(uuid4()),
            )
        assert result["status_code"] == 204
        args, kwargs = mock_client.post.call_args
        assert args[0] == cfg["url"]
        assert kwargs["headers"]["X-Callbot-Signature"].startswith("sha256=")


def test_automation_post_webhook_action(session: Session, tenant: Tenant) -> None:
    service = AutomationService(session)
    with patch(
        "callbot_platform.automation.webhooks.socket.getaddrinfo",
        side_effect=lambda *a, **k: _public_addrinfo(),
    ):
        rule = service.create_rule(
            tenant.id,
            name="Webhook on end",
            trigger_key="call.ended",
            action_key="post_webhook",
            config={"url": "https://hooks.example.com/callbot", "secret": "abc"},
        )
        assert rule["config"]["secret"] == "***"
        with patch(
            "callbot_platform.automation.service.deliver_webhook",
            return_value={"status_code": 200},
        ) as deliver:
            results = service.dispatch(
                tenant.id,
                "call.ended",
                payload={"call_id": str(uuid4())},
            )
        assert len(results) == 1
        assert results[0]["ok"] is True
        deliver.assert_called_once()

    with pytest.raises(AutomationError):
        service.create_rule(
            tenant.id,
            name="Bad webhook",
            trigger_key="call.ended",
            action_key="post_webhook",
            config={"url": "http://example.com/nope"},
        )
