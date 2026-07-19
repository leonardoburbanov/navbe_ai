"""Tests for /api/v1/runs routes with dependency overrides."""

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from navbe.api.v1.routes import runs as runs_routes
from navbe.core.exceptions import NotFoundError
from navbe.dependencies import get_run_service
from navbe.domains.execution.models import RunState, RunStatus


class FakeRunService:
    """Minimal run service for route tests."""

    def __init__(self) -> None:
        self.start_error: Exception | None = None
        now = datetime.now(UTC)
        self.state = RunState(
            run_id="r1",
            flow_id="f1",
            status=RunStatus.COMPLETED,
            created_at=now,
            updated_at=now,
        )

    async def start(self, flow_id: str, initial_input: Any = None) -> str:
        if self.start_error is not None:
            raise self.start_error
        return "r1"

    async def status(self, run_id: str) -> RunState:
        return self.state

    async def resume(self, run_id: str, decision: dict) -> RunState:
        self.state.status = (
            RunStatus.COMPLETED if decision.get("approved") else RunStatus.FAILED
        )
        return self.state


@pytest.fixture
def fake_run_service() -> FakeRunService:
    return FakeRunService()


@pytest.fixture
async def client(fake_run_service: FakeRunService):
    app = FastAPI()
    app.include_router(runs_routes.router, prefix="/api/v1/runs")
    app.dependency_overrides[get_run_service] = lambda: fake_run_service
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_start_run_returns_run_id(client: AsyncClient) -> None:
    """POST /runs returns {"run_id": ...}."""
    response = await client.post(
        "/api/v1/runs",
        json={"flow_id": "f1", "initial_input": {"x": 1}},
    )
    assert response.status_code == 200
    assert response.json() == {"run_id": "r1"}


async def test_start_run_unknown_flow_returns_404(
    client: AsyncClient,
    fake_run_service: FakeRunService,
) -> None:
    """NotFoundError from start maps to 404."""
    fake_run_service.start_error = NotFoundError(
        "missing",
        details={"flow_id": "nope"},
    )
    response = await client.post("/api/v1/runs", json={"flow_id": "nope"})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_found"


async def test_get_run_status_returns_state(
    client: AsyncClient,
    fake_run_service: FakeRunService,
) -> None:
    """GET /runs/{id} returns RunState JSON."""
    response = await client.get("/api/v1/runs/r1")
    assert response.status_code == 200
    assert response.json() == fake_run_service.state.model_dump(mode="json")


async def test_resume_run_returns_updated_state(client: AsyncClient) -> None:
    """POST /runs/{id}/resume returns updated state."""
    response = await client.post(
        "/api/v1/runs/r1/resume",
        json={"approved": True},
    )
    assert response.status_code == 200
    assert response.json()["status"] == RunStatus.COMPLETED
