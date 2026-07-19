"""Tests for flow.validate tool."""

import copy
import json
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

import navbe.domains.steps.implementations  # noqa: F401
from navbe.domains.flows.service import FlowService
from navbe.domains.flows.validator import ValidationIssue, ValidationResult
from navbe.mcp_app.errors import parse_tool_error
from tests.unit.mcp_app.conftest import FakeFlowService, make_server

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def _demo() -> dict:
    return copy.deepcopy(
        json.loads((FIXTURES / "sales_bot_objection_test.json").read_text(encoding="utf-8"))
    )


async def test_flow_validate_valid_spec_returns_valid_true() -> None:
    """Demo FlowSpec validates as valid=True."""
    flow_service = FakeFlowService()
    flow_service.validate_result = ValidationResult(valid=True, issues=[])
    # Use a real FlowService.validate path via wrapping
    real = FlowService(repository=None)  # type: ignore[arg-type]
    flow_service.validate = real.validate  # type: ignore[method-assign]
    server = make_server(flow_service=flow_service)
    async with Client(server) as client:
        result = await client.call_tool("flow.validate", {"spec": _demo()})
    assert result.data["valid"] is True
    assert result.data["issues"] == []


async def test_flow_validate_graph_issue_returns_valid_false() -> None:
    """Orphan node produces valid=False with issue detail."""
    flow_service = FakeFlowService()
    flow_service.validate_result = ValidationResult(
        valid=False,
        issues=[
            ValidationIssue(
                code="orphan_node",
                message="node 'orphan' is unreachable from entry_node",
                node_id="orphan",
            )
        ],
    )
    server = make_server(flow_service=flow_service)
    spec = {
        "flow_id": "x",
        "entry_node": "n1",
        "nodes": [
            {
                "id": "n1",
                "step_type": "set_var",
                "config": {"var_name": "a", "value_from": "a"},
            },
            {
                "id": "orphan",
                "step_type": "set_var",
                "config": {"var_name": "b", "value_from": "b"},
            },
        ],
        "edges": [],
    }
    async with Client(server) as client:
        result = await client.call_tool("flow.validate", {"spec": spec})
    assert result.data["valid"] is False
    assert result.data["issues"][0]["code"] == "orphan_node"
    assert result.data["issues"][0]["node_id"] == "orphan"


async def test_flow_validate_malformed_pydantic_shape_returns_structured_error() -> None:
    """Missing entry_node becomes structured ToolError, not a raw pydantic traceback."""
    server = make_server()
    async with Client(server) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool(
                "flow.validate",
                {
                    "spec": {
                        "flow_id": "broken",
                        "nodes": [{"id": "n1", "step_type": "set_var", "config": {}}],
                        "edges": [],
                    }
                },
            )
    payload = parse_tool_error(exc_info.value)
    assert payload["code"] == "validation_error"
    assert "errors" in payload["details"]
