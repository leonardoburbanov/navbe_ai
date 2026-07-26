"""Tests for Google Calendar connector."""

import pytest
from pytest_httpserver import HTTPServer

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.implementations import google_calendar as gc_mod
from navbe.domains.connectors.implementations.google_calendar import GoogleCalendarConnector


async def test_create_event(httpserver: HTTPServer, monkeypatch: pytest.MonkeyPatch) -> None:
    """create refreshes token then POSTs an event."""
    base = httpserver.url_for("/").rstrip("/")
    monkeypatch.setattr(gc_mod, "_TOKEN_URL", f"{base}/token")
    monkeypatch.setattr(gc_mod, "_CALENDAR_BASE", f"{base}/calendar/v3")
    httpserver.expect_request("/token", method="POST").respond_with_json(
        {"access_token": "ya29.test"}
    )
    httpserver.expect_request(
        "/calendar/v3/calendars/primary/events",
        method="POST",
    ).respond_with_json({"id": "evt1"})

    connector = GoogleCalendarConnector(
        {
            "client_id": "cid",
            "client_secret": "sec",
            "refresh_token": "rt",
        }
    )
    result = await connector.execute(
        "create",
        {"event": {"summary": "Meet"}},
    )
    assert result == {"id": "evt1"}


async def test_delete_requires_event_id() -> None:
    """delete without event_id raises."""
    connector = GoogleCalendarConnector(
        {"client_id": "c", "client_secret": "s", "refresh_token": "r"}
    )
    with pytest.raises(ExecutionError):
        await connector.execute("delete", {})
