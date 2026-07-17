"""Tests for HTTP request step."""

from typing import Any

import pytest

from navbe.core.exceptions import ExecutionError, ValidationError
from navbe.domains.steps.implementations.http_request import HTTPRequestStep, resolve_templates
from navbe.domains.steps.interfaces import StepContext


class FakeConnector:
    """Connector fake that records execute calls."""

    def __init__(self) -> None:
        """Create an empty call log."""
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, method: str, request: dict[str, Any]) -> Any:
        """Record and echo request details."""
        self.calls.append((method, request))
        return {"ok": True, "request": request}


def test_resolve_templates_simple() -> None:
    """Resolve a simple flow_vars placeholder in a string."""
    assert resolve_templates("session={{flow_vars.session_id}}", {"session_id": "abc"}) == (
        "session=abc"
    )


def test_resolve_templates_nested_dict() -> None:
    """Resolve placeholders inside nested dictionaries."""
    value = {"body": {"id": "{{flow_vars.session_id}}"}}
    assert resolve_templates(value, {"session_id": "abc"}) == {"body": {"id": "abc"}}


def test_resolve_templates_node_outputs() -> None:
    """Resolve node_outputs placeholders from flow vars."""
    flow_vars = {"node_outputs": {"turn_2": {"response": "hi"}}}
    assert resolve_templates("{{node_outputs.turn_2.response}}", flow_vars) == "hi"


def test_resolve_templates_missing_key_raises() -> None:
    """Missing placeholders raise Navbe ValidationError."""
    with pytest.raises(ValidationError):
        resolve_templates("{{flow_vars.missing}}", {})


async def test_run_calls_connector_execute_with_resolved_body() -> None:
    """Step calls connector with resolved path/body/params."""
    connector = FakeConnector()
    step = HTTPRequestStep(
        {
            "connector": "api",
            "method": "post",
            "path": "/sessions/{{flow_vars.session_id}}",
            "body_template": {"message": "{{node_outputs.turn_2.response}}"},
            "params": {"page": "{{flow_vars.page}}"},
        }
    )
    ctx = StepContext(
        node_id="n1",
        input_data=None,
        flow_vars={
            "connectors": {"api": connector},
            "session_id": "abc",
            "page": 2,
            "node_outputs": {"turn_2": {"response": "hi"}},
        },
    )

    await step.run(ctx)

    assert connector.calls == [
        (
            "post",
            {"path": "/sessions/abc", "body": {"message": "hi"}, "params": {"page": 2}},
        )
    ]


async def test_run_missing_connector_in_flow_vars_raises() -> None:
    """Missing connector raises ExecutionError with clear details."""
    step = HTTPRequestStep({"connector": "api", "method": "get"})
    ctx = StepContext(node_id="n1", input_data=None, flow_vars={})

    with pytest.raises(ExecutionError) as exc_info:
        await step.run(ctx)

    assert "api" in exc_info.value.message
    assert exc_info.value.details == {"connector": "api"}
