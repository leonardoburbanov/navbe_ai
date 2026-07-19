"""Tests for flow_status tool."""

from datetime import UTC, datetime

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from navbe.core.exceptions import NotFoundError
from navbe.domains.execution.models import RunState, RunStatus
from navbe.mcp_app.errors import parse_tool_error
from tests.unit.mcp_app.conftest import FakeRunService, make_server


async def test_flow_status_returns_run_state_dict() -> None:
    """Status payload matches RunState.model_dump(mode='json')."""
    run_service = FakeRunService()
    now = datetime.now(UTC)
    state = RunState(
        run_id="r1",
        flow_id="f1",
        status=RunStatus.COMPLETED,
        node_outputs={"n1": 1},
        created_at=now,
        updated_at=now,
    )
    run_service.states["r1"] = state
    server = make_server(run_service=run_service)
    async with Client(server) as client:
        result = await client.call_tool("flow_status", {"run_id": "r1"})
    assert result.data == state.model_dump(mode="json")


async def test_flow_status_unknown_run_id_returns_structured_error() -> None:
    """Unknown run_id becomes structured not_found ToolError."""
    run_service = FakeRunService()
    run_service.status_error = NotFoundError("missing", details={"run_id": "ghost"})
    server = make_server(run_service=run_service)
    async with Client(server) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool("flow_status", {"run_id": "ghost"})
    assert parse_tool_error(exc_info.value)["code"] == "not_found"
