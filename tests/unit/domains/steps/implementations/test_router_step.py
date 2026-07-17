"""Tests for router step."""

import pytest

from navbe.core.exceptions import ExecutionError, ValidationError
from navbe.domains.steps.implementations.router_step import RouterStep
from navbe.domains.steps.interfaces import StepContext


async def test_condition_resolves_to_defined_route() -> None:
    """Condition result maps to a declared next node."""
    step = RouterStep(
        {
            "condition": "node_outputs['eval']['route']",
            "routes": {"approve": "node_approve", "reject": "node_reject"},
        }
    )
    ctx = StepContext(
        node_id="router",
        input_data=None,
        flow_vars={"node_outputs": {"eval": {"route": "approve"}}},
    )

    assert await step.run(ctx) == {"route": "approve", "next_node": "node_approve"}


async def test_condition_result_not_in_routes_raises() -> None:
    """An undeclared route result raises ExecutionError."""
    step = RouterStep({"condition": "'maybe'", "routes": {"yes": "n1"}})

    with pytest.raises(ExecutionError):
        await step.run(StepContext(node_id="router", input_data=None))


async def test_condition_cannot_execute_arbitrary_code() -> None:
    """simpleeval blocks arbitrary function calls like imports."""
    step = RouterStep(
        {
            "condition": "__import__('os').system('ls')",
            "routes": {"0": "n1"},
        }
    )

    with pytest.raises((ExecutionError, ValidationError)):
        await step.run(StepContext(node_id="router", input_data=None))


async def test_malformed_condition_syntax_raises_validation_error() -> None:
    """Unparseable expressions raise ValidationError."""
    step = RouterStep({"condition": "[[[", "routes": {"yes": "n1"}})

    with pytest.raises(ValidationError):
        await step.run(StepContext(node_id="router", input_data=None))
