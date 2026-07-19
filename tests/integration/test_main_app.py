"""Integration tests for create_app() wiring (REST + MCP mount)."""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from navbe.dependencies import clear_dependency_caches
from navbe.main import create_app


@pytest.fixture(autouse=True)
def _reset_caches(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Point settings at tmp paths and reset DI caches per test."""
    monkeypatch.setenv("NAVBE_DB_PATH", str(tmp_path / "navbe.db"))
    monkeypatch.setenv("NAVBE_FLOWS_DIR", str(tmp_path / "flows"))
    clear_dependency_caches()
    yield
    clear_dependency_caches()


def test_app_starts_without_error() -> None:
    """create_app() constructs with real wired dependencies."""
    app = create_app()
    assert app.title == "Navbe"


async def test_health_endpoint() -> None:
    """GET /health → 200 {"status": "ok"}."""
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_mcp_mounted_and_responds_to_initialize() -> None:
    """MCP client handshake succeeds through the mounted /mcp path."""
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            follow_redirects=True,
        ) as client:
            response = await client.post(
                "/mcp/",
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "navbe-test", "version": "0"},
                    },
                },
            )
    assert response.status_code == 200
    # Streamable HTTP returns SSE; parse the data line.
    payload = None
    for line in response.text.splitlines():
        if line.startswith("data: "):
            payload = json.loads(line.removeprefix("data: "))
            break
    assert payload is not None
    assert payload["result"]["serverInfo"]["name"]
