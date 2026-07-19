"""Tests for flow_run tool."""

import asyncio
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from navbe.core.exceptions import NotFoundError
from navbe.domains.execution.service import RunService
from navbe.domains.flows.models import FlowSpec
from navbe.mcp_app.errors import parse_tool_error
from navbe.mcp_app.server import create_mcp_server
from tests.unit.domains.execution.test_interfaces import FakeExecutionEngine
from tests.unit.domains.execution.test_service import FakeConnectorService, FakeFlowService
from tests.unit.mcp_app.conftest import FakeCatalogService, FakeRunService, make_server


async def test_flow_run_returns_run_id_without_blocking() -> None:
    """flow_run returns before a slow engine.run finishes."""
    release = asyncio.Event()
    entered = asyncio.Event()

    class SlowEngine(FakeExecutionEngine):
        async def run(self, flow_spec: FlowSpec, run_id: str, initial_input: Any):
            entered.set()
            await release.wait()
            return await super().run(flow_spec, run_id, initial_input)

    flow = FlowSpec.model_validate(
        {
            "flow_id": "slow",
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
    run_service = RunService(SlowEngine(), FakeFlowService(flow), FakeConnectorService())
    server = create_mcp_server(
        FakeFlowService(flow),  # type: ignore[arg-type]
        run_service,
        FakeCatalogService(),  # type: ignore[arg-type]
    )
    async with Client(server) as client:
        result = await client.call_tool("flow_run", {"flow_id": "slow", "initial_input": {}})
    assert result.data["status"] == "started"
    assert result.data["run_id"]
    await asyncio.wait_for(entered.wait(), timeout=1.0)
    assert not release.is_set()
    release.set()
    if run_service._background_tasks:
        await asyncio.gather(*list(run_service._background_tasks))


async def test_flow_run_unknown_flow_returns_structured_error() -> None:
    """NotFoundError from start surfaces as structured ToolError."""
    run_service = FakeRunService()
    run_service.start_error = NotFoundError("missing", details={"flow_id": "nope"})
    server = make_server(run_service=run_service)
    async with Client(server) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool("flow_run", {"flow_id": "nope"})
    payload = parse_tool_error(exc_info.value)
    assert payload["code"] == "not_found"
