"""Contract: ``navbe serve`` exposes /health (daemon + MCP mount live together)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from navbe.main import create_app


def test_health_endpoint() -> None:
    """Liveness probe used by bootstrap / status."""
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
