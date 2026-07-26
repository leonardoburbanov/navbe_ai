"""Tests for Resend send_email connector."""

import pytest
from pytest_httpserver import HTTPServer

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.implementations.resend import ResendConnector


async def test_send_email_posts_emails(
    httpserver: HTTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """send_email POSTs /emails with required fields."""
    monkeypatch.setattr(
        "navbe.domains.connectors.implementations.resend._RESEND_BASE_URL",
        httpserver.url_for("/").rstrip("/"),
    )
    httpserver.expect_request("/emails", method="POST").respond_with_json({"id": "msg_1"})
    connector = ResendConnector({"api_key": "re_test"})

    result = await connector.execute(
        "send_email",
        {
            "from": "a@example.com",
            "to": "b@example.com",
            "subject": "Hi",
            "text": "Hello",
        },
    )

    assert result == {"id": "msg_1"}


async def test_send_email_via_http_request_body(
    httpserver: HTTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nested body from http_request is unwrapped."""
    monkeypatch.setattr(
        "navbe.domains.connectors.implementations.resend._RESEND_BASE_URL",
        httpserver.url_for("/").rstrip("/"),
    )
    httpserver.expect_request("/emails", method="POST").respond_with_json({"id": "msg_2"})
    connector = ResendConnector({"api_key": "re_test"})

    result = await connector.execute(
        "send_email",
        {
            "path": "",
            "body": {
                "from": "a@example.com",
                "to": "b@example.com",
                "subject": "Hi",
                "html": "<p>Hi</p>",
            },
            "params": {},
        },
    )

    assert result == {"id": "msg_2"}


async def test_send_email_requires_body_content() -> None:
    """Missing html/text raises ExecutionError."""
    connector = ResendConnector({"api_key": "re_test"})

    with pytest.raises(ExecutionError):
        await connector.execute(
            "send_email",
            {"from": "a@example.com", "to": "b@example.com", "subject": "Hi"},
        )


async def test_unsupported_action() -> None:
    """HTTP verb actions are no longer supported."""
    connector = ResendConnector({"api_key": "re_test"})

    with pytest.raises(ExecutionError) as exc_info:
        await connector.execute("post", {"path": "/emails"})

    assert exc_info.value.details["action"] == "post"
