"""Tests for flow.create tool."""

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from navbe.core.exceptions import ValidationError
from navbe.mcp_app.errors import parse_tool_error
from tests.unit.mcp_app.conftest import FakeFlowService, make_server


async def test_flow_create_success_returns_flow_id() -> None:
    """Valid spec returns flow_id/version/path from FlowService.create."""
    flow_service = FakeFlowService()
    server = make_server(flow_service=flow_service)
    spec = {
        "flow_id": "demo",
        "entry_node": "n1",
        "nodes": [{"id": "n1", "step_type": "set_var", "config": {}}],
        "edges": [],
    }
    async with Client(server) as client:
        result = await client.call_tool("flow.create", {"spec": spec})
    assert result.data == {
        "flow_id": "demo",
        "version": 1,
        "path": "/tmp/f1/flow.json",
    }
    assert flow_service.created == [spec]


async def test_flow_create_invalid_spec_returns_structured_error() -> None:
    """ValidationError details (issues) survive as ToolError JSON."""
    flow_service = FakeFlowService()
    flow_service.create_error = ValidationError(
        "FlowSpec failed graph validation",
        details={"issues": [{"code": "orphan_node", "node_id": "x"}]},
    )
    server = make_server(flow_service=flow_service)
    async with Client(server) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool("flow.create", {"spec": {"flow_id": "bad"}})
    payload = parse_tool_error(exc_info.value)
    assert payload["code"] == "validation_error"
    assert payload["details"]["issues"][0]["code"] == "orphan_node"
