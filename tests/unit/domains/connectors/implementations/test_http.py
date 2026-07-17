"""Tests for HTTP connector."""

import pytest
from pytest_httpserver import HTTPServer

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.implementations.http import HTTPConnector


async def test_connection_success(httpserver: HTTPServer) -> None:
    """test_connection returns True against a running local server."""
    httpserver.expect_request("/").respond_with_data("", status=200)
    connector = HTTPConnector({"base_url": httpserver.url_for("/")})

    assert await connector.test_connection() is True


async def test_connection_failure_unreachable_host() -> None:
    """Unreachable hosts return False instead of raising."""
    connector = HTTPConnector({"base_url": "http://127.0.0.1:1"})

    assert await connector.test_connection() is False


async def test_execute_get_returns_json(httpserver: HTTPServer) -> None:
    """GET against a configured route returns parsed JSON."""
    httpserver.expect_request("/items").respond_with_json({"items": [1]})
    connector = HTTPConnector({"base_url": httpserver.url_for("/")})

    result = await connector.execute("get", {"path": "/items"})

    assert result == {"items": [1]}


async def test_execute_post_sends_correct_body(httpserver: HTTPServer) -> None:
    """POST sends the JSON body expected by the server."""
    httpserver.expect_request("/items", method="POST", json={"name": "navbe"}).respond_with_json(
        {"ok": True}
    )
    connector = HTTPConnector({"base_url": httpserver.url_for("/")})

    result = await connector.execute("post", {"path": "/items", "body": {"name": "navbe"}})

    assert result == {"ok": True}


async def test_execute_put_and_delete(httpserver: HTTPServer) -> None:
    """PUT and DELETE hit their respective routes."""
    httpserver.expect_request("/items/1", method="PUT", json={"name": "updated"}).respond_with_json(
        {"updated": True}
    )
    httpserver.expect_request("/items/1", method="DELETE").respond_with_json({"deleted": True})
    connector = HTTPConnector({"base_url": httpserver.url_for("/")})

    put_result = await connector.execute(
        "put",
        {"path": "/items/1", "body": {"name": "updated"}},
    )
    delete_result = await connector.execute("delete", {"path": "/items/1"})

    assert put_result == {"updated": True}
    assert delete_result == {"deleted": True}


async def test_execute_http_error_status_raises_execution_error(httpserver: HTTPServer) -> None:
    """Server 5xx responses become ExecutionError, not httpx.HTTPStatusError."""
    httpserver.expect_request("/boom").respond_with_data("fail", status=500)
    connector = HTTPConnector({"base_url": httpserver.url_for("/")})

    with pytest.raises(ExecutionError):
        await connector.execute("get", {"path": "/boom"})


async def test_execute_unsupported_action_raises() -> None:
    """Unsupported actions raise before any network call."""
    connector = HTTPConnector({"base_url": "http://example.com"})

    with pytest.raises(ExecutionError) as exc_info:
        await connector.execute("patch", {})

    assert exc_info.value.details["action"] == "patch"
