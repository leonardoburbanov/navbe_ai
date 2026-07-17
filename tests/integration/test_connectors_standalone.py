"""Standalone connector tests without Flow or execution engine."""

from pytest_httpserver import HTTPServer

from navbe.domains.connectors.implementations.http import HTTPConnector


async def test_http_connector_full_cycle(httpserver: HTTPServer) -> None:
    """Prove HTTP connector works end-to-end against a local server."""
    httpserver.expect_request("/").respond_with_data("", status=200)
    httpserver.expect_request("/ping").respond_with_json({"status": "ok"})

    connector = HTTPConnector({"base_url": httpserver.url_for("/"), "timeout": 5})
    assert await connector.test_connection() is True

    result = await connector.execute("get", {"path": "/ping"})
    assert result == {"status": "ok"}
