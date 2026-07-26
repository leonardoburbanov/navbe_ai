"""Tests for Supabase PostgREST connector."""

from pytest_httpserver import HTTPServer

from navbe.domains.connectors.implementations.supabase import SupabaseConnector


async def test_create_and_read(httpserver: HTTPServer) -> None:
    """create POSTs and read GETs /rest/v1/{table}."""
    httpserver.expect_request("/rest/v1/todos", method="POST").respond_with_json([{"id": 1}])
    httpserver.expect_request("/rest/v1/todos", method="GET").respond_with_json([{"id": 1}])
    connector = SupabaseConnector(
        {"url": httpserver.url_for("/").rstrip("/"), "service_role_key": "srk"}
    )

    created = await connector.execute("create", {"table": "todos", "row": {"title": "x"}})
    assert created == [{"id": 1}]
    rows = await connector.execute("read", {"table": "todos", "filters": {"id": 1}})
    assert rows == [{"id": 1}]
