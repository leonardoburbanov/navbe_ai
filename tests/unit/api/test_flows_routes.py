"""Tests for /api/v1/flows routes with dependency overrides."""

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from navbe.api.v1.routes import flows as flows_routes
from navbe.core.exceptions import NotFoundError, ValidationError
from navbe.dependencies import get_flow_service
from navbe.domains.flows.models import FlowMetadata, FlowSpec


class FakeFlowService:
    """Minimal flow service for route tests."""

    def __init__(self) -> None:
        self.spec = FlowSpec.model_validate(
            {
                "flow_id": "demo",
                "entry_node": "n1",
                "nodes": [
                    {
                        "id": "n1",
                        "step_type": "set_var",
                        "config": {"var_name": "x", "value_from": "x"},
                    }
                ],
                "edges": [],
            }
        )
        self.create_error: Exception | None = None
        self.get_error: Exception | None = None

    async def create(self, spec: dict[str, Any]) -> FlowMetadata:
        if self.create_error is not None:
            raise self.create_error
        now = datetime.now(UTC)
        return FlowMetadata(
            flow_id=spec.get("flow_id", "demo"),
            name="",
            created_at=now,
            updated_at=now,
            version=1,
            path="/tmp/demo/flow.json",
        )

    async def get(self, flow_id: str) -> FlowSpec:
        if self.get_error is not None:
            raise self.get_error
        return self.spec

    async def list(self) -> list[FlowMetadata]:
        now = datetime.now(UTC)
        return [
            FlowMetadata(
                flow_id="demo",
                name="",
                created_at=now,
                updated_at=now,
                version=1,
                path="/tmp/demo/flow.json",
            )
        ]


@pytest.fixture
def fake_flow_service() -> FakeFlowService:
    return FakeFlowService()


@pytest.fixture
async def client(fake_flow_service: FakeFlowService):
    app = FastAPI()
    app.include_router(flows_routes.router, prefix="/api/v1/flows")
    app.dependency_overrides[get_flow_service] = lambda: fake_flow_service
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_post_creates_flow_returns_201_or_200_with_metadata(
    client: AsyncClient,
) -> None:
    """POST /flows returns 201 with metadata."""
    response = await client.post(
        "/api/v1/flows",
        json={
            "flow_id": "demo",
            "entry_node": "n1",
            "nodes": [{"id": "n1", "step_type": "set_var", "config": {}}],
            "edges": [],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["flow_id"] == "demo"
    assert body["version"] == 1
    assert "path" in body


async def test_post_invalid_spec_returns_422(
    client: AsyncClient,
    fake_flow_service: FakeFlowService,
) -> None:
    """ValidationError maps to HTTP 422 with structured detail."""
    fake_flow_service.create_error = ValidationError(
        "bad",
        details={"issues": [{"code": "orphan_node"}]},
    )
    response = await client.post("/api/v1/flows", json={"flow_id": "x"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "validation_error"
    assert detail["details"]["issues"][0]["code"] == "orphan_node"


async def test_get_existing_flow_returns_spec(
    client: AsyncClient,
    fake_flow_service: FakeFlowService,
) -> None:
    """GET /flows/{id} returns FlowSpec.model_dump(by_alias=True)."""
    response = await client.get("/api/v1/flows/demo")
    assert response.status_code == 200
    assert response.json() == fake_flow_service.spec.model_dump(by_alias=True)


async def test_get_missing_flow_returns_404(
    client: AsyncClient,
    fake_flow_service: FakeFlowService,
) -> None:
    """NotFoundError maps to HTTP 404."""
    fake_flow_service.get_error = NotFoundError(
        "missing",
        details={"flow_id": "ghost"},
    )
    response = await client.get("/api/v1/flows/ghost")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_found"


async def test_list_flows_returns_array(client: AsyncClient) -> None:
    """GET /flows returns a list of metadata dicts."""
    response = await client.get("/api/v1/flows")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["flow_id"] == "demo"
