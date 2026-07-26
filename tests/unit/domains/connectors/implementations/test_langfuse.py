"""Tests for Langfuse connector."""

import pytest
from pytest_httpserver import HTTPServer

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.implementations.langfuse import LangfuseConnector


def _connector(httpserver: HTTPServer) -> LangfuseConnector:
    return LangfuseConnector(
        {
            "host": httpserver.url_for("/").rstrip("/"),
            "public_key": "pk",
            "secret_key": "sk",
        }
    )


async def test_read_traces(httpserver: HTTPServer) -> None:
    """read GETs /api/public/traces."""
    httpserver.expect_request("/api/public/traces", method="GET").respond_with_json({"data": []})
    result = await _connector(httpserver).execute("read", {})
    assert result == {"data": []}


async def test_create_ingestion(httpserver: HTTPServer) -> None:
    """create POSTs /api/public/ingestion."""
    httpserver.expect_request("/api/public/ingestion", method="POST").respond_with_json(
        {"ok": True}
    )
    result = await _connector(httpserver).execute("create", {"batch": [{"type": "trace-create"}]})
    assert result == {"ok": True}


async def test_update_unsupported(httpserver: HTTPServer) -> None:
    """update raises ExecutionError."""
    with pytest.raises(ExecutionError):
        await _connector(httpserver).execute("update", {})
