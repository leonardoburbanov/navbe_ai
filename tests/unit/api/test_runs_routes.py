"""Tests for /api/v1/runs routes with dependency overrides."""

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from navbe.api.v1.routes import runs as runs_routes
from navbe.core.exceptions import NotFoundError
from navbe.dependencies import get_run_service
from navbe.domains.execution.models import RunDetail, RunState, RunStatus, StepExecution


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
        self.detail_result = RunDetail(
            state=self.state,
            steps=[
                StepExecution(
                    node_id="n1",
                    step_type="set_var",
                    status="completed",
                    latency_ms=1.0,
                )
            ],
            diagram="flowchart TD\n  n1",
        )

    async def start(self, flow_id: str, initial_input: Any = None) -> str:
        if self.start_error is not None:
            raise self.start_error
        return "r1"

    async def status(self, run_id: str) -> RunState:
        return self.state

    async def detail(self, run_id: str) -> RunDetail:
        return self.detail_result

    async def list_runs(self, flow_id: str | None = None) -> list[RunState]:
        return [self.state]

    async def resume(self, run_id: str, decision: dict) -> RunState:
        self.state.status = (
            RunStatus.COMPLETED if decision.get("approved") else RunStatus.FAILED
        )
        self.detail_result = RunDetail(
            state=self.state,
            steps=self.detail_result.steps,
            diagram=self.detail_result.diagram,
        )
        return self.state

    async def cancel(self, run_id: str) -> RunState:
        self.state.status = RunStatus.CANCELLED
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


async def test_list_runs_returns_runs(client: AsyncClient) -> None:
    """GET /runs returns a runs array."""
    response = await client.get("/api/v1/runs")
    assert response.status_code == 200
    body = response.json()
    assert body["runs"][0]["run_id"] == "r1"


async def test_get_run_status_returns_enriched_detail(
    client: AsyncClient,
    fake_run_service: FakeRunService,
) -> None:
    """GET /runs/{id} returns state plus steps and Mermaid diagram."""
    response = await client.get("/api/v1/runs/r1")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "r1"
    assert body["steps"][0]["node_id"] == "n1"
    assert "flowchart" in body["diagram"]


async def test_resume_run_returns_enriched_detail(client: AsyncClient) -> None:
    """POST /runs/{id}/resume returns steps + diagram."""
    response = await client.post(
        "/api/v1/runs/r1/resume",
        json={"approved": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == RunStatus.COMPLETED
    assert "diagram" in body
    assert "steps" in body
