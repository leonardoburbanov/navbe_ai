"""Tests for flow_list, flow_get, and flow_update tools."""

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from navbe.core.exceptions import NotFoundError, ValidationError
from navbe.mcp_app.errors import parse_tool_error
from tests.unit.mcp_app.conftest import FakeFlowService, make_server


async def test_flow_list_returns_saved_metadata() -> None:
    """flow_list returns metadata for flows created via the fake."""
    flow_service = FakeFlowService()
    await flow_service.create({"flow_id": "demo", "name": "Demo"})
    server = make_server(flow_service=flow_service)
    async with Client(server) as client:
        result = await client.call_tool("flow_list", {})
    assert len(result.data["flows"]) == 1
    assert result.data["flows"][0]["flow_id"] == "demo"


async def test_flow_get_returns_spec() -> None:
    """flow_get returns FlowSpec.model_dump(by_alias=True)."""
    flow_service = FakeFlowService()
    await flow_service.create({"flow_id": "demo", "name": "Demo"})
    server = make_server(flow_service=flow_service)
    async with Client(server) as client:
        result = await client.call_tool("flow_get", {"flow_id": "demo"})
    assert result.data["flow_id"] == "demo"
    assert result.data["entry_node"] == "n1"


async def test_flow_get_missing_returns_structured_error() -> None:
    """NotFoundError from flow_get becomes ToolError JSON."""
    flow_service = FakeFlowService()
    flow_service.get_error = NotFoundError("missing", details={"flow_id": "ghost"})
    server = make_server(flow_service=flow_service)
    async with Client(server) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool("flow_get", {"flow_id": "ghost"})
    payload = parse_tool_error(exc_info.value)
    assert payload["code"] == "not_found"


async def test_flow_update_success_bumps_version() -> None:
    """flow_update returns bumped version from FlowService.update."""
    flow_service = FakeFlowService()
    await flow_service.create({"flow_id": "demo", "name": "Demo"})
    server = make_server(flow_service=flow_service)
    spec = {"flow_id": "demo", "name": "Renamed", "entry_node": "n1", "nodes": [], "edges": []}
    async with Client(server) as client:
        result = await client.call_tool("flow_update", {"spec": spec})
    assert result.data == {
        "flow_id": "demo",
        "version": 2,
        "path": "/tmp/f1/flow.json",
    }
    assert flow_service.updated == [spec]


async def test_flow_update_missing_returns_structured_error() -> None:
    """Missing flow on update surfaces not_found ToolError."""
    flow_service = FakeFlowService()
    flow_service.update_error = NotFoundError("missing", details={"flow_id": "ghost"})
    server = make_server(flow_service=flow_service)
    async with Client(server) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool("flow_update", {"spec": {"flow_id": "ghost"}})
    assert parse_tool_error(exc_info.value)["code"] == "not_found"


async def test_flow_update_invalid_returns_structured_error() -> None:
    """ValidationError details survive as ToolError JSON."""
    flow_service = FakeFlowService()
    await flow_service.create({"flow_id": "demo"})
    flow_service.update_error = ValidationError(
        "FlowSpec failed graph validation",
        details={"issues": [{"code": "orphan_node"}]},
    )
    server = make_server(flow_service=flow_service)
    async with Client(server) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool("flow_update", {"spec": {"flow_id": "demo"}})
    payload = parse_tool_error(exc_info.value)
    assert payload["code"] == "validation_error"
    assert payload["details"]["issues"][0]["code"] == "orphan_node"
