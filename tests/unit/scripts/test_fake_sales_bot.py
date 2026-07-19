"""Tests for the fake sales-bot fixture app."""

import importlib.util
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "fake_sales_bot.py"


def _load_app():
    """Load scripts/fake_sales_bot.py as a module (not a package)."""
    spec = importlib.util.spec_from_file_location("fake_sales_bot", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SESSIONS.clear()
    return module


@pytest.fixture
async def client():
    module = _load_app()
    transport = ASGITransport(app=module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, module


async def test_health_endpoint(client) -> None:
    """/health → 200 for readiness polling."""
    ac, _ = client
    response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_first_message_returns_greeting(client) -> None:
    """New session returns a greeting-shaped response."""
    ac, _ = client
    response = await ac.post("/chat", json={"message": "Hola, me interesa el CRM"})
    assert response.status_code == 200
    body = response.json()
    assert "hola" in body["response"].lower() or "crm" in body["response"].lower()
    assert body["session_id"]


async def test_price_objection_triggers_value_response(client) -> None:
    """Message with precio/caro gets a value-justification reply."""
    ac, _ = client
    first = await ac.post("/chat", json={"message": "Hola"})
    session_id = first.json()["session_id"]
    response = await ac.post(
        "/chat",
        json={"message": "Está muy caro el precio", "session_id": session_id},
    )
    text = response.json()["response"].lower()
    assert "precio" in text or "soporte" in text or "ahorra" in text


async def test_session_persists_across_calls(client) -> None:
    """Same session_id accumulates history across two calls."""
    ac, module = client
    first = await ac.post("/chat", json={"message": "Hola"})
    session_id = first.json()["session_id"]
    await ac.post(
        "/chat",
        json={"message": "Somos 5 personas", "session_id": session_id},
    )
    assert len(module.SESSIONS[session_id]) == 2
