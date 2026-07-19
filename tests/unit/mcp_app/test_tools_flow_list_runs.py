"""Tests for flow.list_runs tool."""

from datetime import UTC, datetime, timedelta

from fastmcp import Client

from navbe.domains.execution.models import RunState, RunStatus
from tests.unit.mcp_app.conftest import FakeRunService, make_server


async def test_flow_list_runs_returns_runs_sorted() -> None:
    """Runs are returned most-recent-first by updated_at."""
    run_service = FakeRunService()
    now = datetime.now(UTC)
    older = RunState(
        run_id="old",
        flow_id="f1",
        status=RunStatus.COMPLETED,
        created_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=2),
    )
    newer = RunState(
        run_id="new",
        flow_id="f1",
        status=RunStatus.COMPLETED,
        created_at=now,
        updated_at=now,
    )
    run_service.runs_by_flow["f1"] = [older, newer]
    server = make_server(run_service=run_service)
    async with Client(server) as client:
        result = await client.call_tool("flow.list_runs", {"flow_id": "f1"})
    ids = [run["run_id"] for run in result.data["runs"]]
    assert ids == ["new", "old"]
