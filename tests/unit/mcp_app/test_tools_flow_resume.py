"""Tests for flow_resume tool."""

from datetime import UTC, datetime

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from navbe.core.exceptions import ExecutionError
from navbe.domains.execution.models import RunState, RunStatus
from navbe.mcp_app.errors import parse_tool_error
from tests.unit.mcp_app.conftest import FakeRunService, make_server


async def test_flow_resume_approved_continues() -> None:
    """approved=True is passed through and returns COMPLETED."""
    run_service = FakeRunService()
    now = datetime.now(UTC)
    run_service.states["r1"] = RunState(
        run_id="r1",
        flow_id="f1",
        status=RunStatus.PAUSED,
        current_node="gate",
        created_at=now,
        updated_at=now,
    )
    server = make_server(run_service=run_service)
    async with Client(server) as client:
        result = await client.call_tool(
            "flow_resume",
            {"run_id": "r1", "decision": {"approved": True}},
        )
    assert run_service.last_decision == {"approved": True}
    assert result.data["status"] == RunStatus.COMPLETED


async def test_flow_resume_rejected_returns_failed_state() -> None:
    """approved=False yields FAILED with an approval error message."""
    run_service = FakeRunService()
    now = datetime.now(UTC)
    run_service.states["r1"] = RunState(
        run_id="r1",
        flow_id="f1",
        status=RunStatus.PAUSED,
        created_at=now,
        updated_at=now,
    )
    server = make_server(run_service=run_service)
    async with Client(server) as client:
        result = await client.call_tool(
            "flow_resume",
            {"run_id": "r1", "decision": {"approved": False}},
        )
    assert result.data["status"] == RunStatus.FAILED
    assert "not approved" in (result.data.get("error") or "")


async def test_flow_resume_run_not_paused_returns_structured_error() -> None:
    """Resuming a non-paused run surfaces ExecutionError as ToolError."""
    run_service = FakeRunService()
    run_service.resume_error = ExecutionError(
        "Run 'r1' is not paused (status=completed)",
        details={"run_id": "r1", "status": "completed"},
    )
    server = make_server(run_service=run_service)
    async with Client(server) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool(
                "flow_resume",
                {"run_id": "r1", "decision": {"approved": True}},
            )
    payload = parse_tool_error(exc_info.value)
    assert payload["code"] == "execution_error"
    assert "not paused" in payload["message"]
