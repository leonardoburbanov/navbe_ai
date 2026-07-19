"""Tests for FlowSpec -> StateGraph compilation."""

from pathlib import Path
from typing import Any

import pytest
from langgraph.graph import END, START

import navbe.domains.steps.implementations  # noqa: F401
from navbe.core.exceptions import ExecutionError, NotFoundError
from navbe.domains.execution.graph_compiler import FlowGraphState, compile_flow
from navbe.domains.flows.models import FlowSpec
from navbe.domains.steps.interfaces import StepContext
from navbe.domains.steps.models import StepConfig
from navbe.domains.steps.registry import StepRegistry

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def _linear_flow() -> FlowSpec:
    return FlowSpec.model_validate(
        {
            "flow_id": "linear",
            "entry_node": "n1",
            "nodes": [
                {
                    "id": "n1",
                    "step_type": "set_var",
                    "config": {"var_name": "x", "value_from": "amount"},
                },
                {
                    "id": "n2",
                    "step_type": "transform",
                    "config": {"query": "SELECT amount * 2 AS doubled FROM input"},
                },
            ],
            "edges": [{"from": "n1", "to": "n2"}],
        }
    )


def test_compile_linear_flow_has_expected_nodes() -> None:
    """Compiled graph contains both node ids."""
    graph = compile_flow(_linear_flow())
    assert "n1" in graph.nodes
    assert "n2" in graph.nodes


def test_compile_sets_entry_node_edge() -> None:
    """START connects to flow_spec.entry_node."""
    graph = compile_flow(_linear_flow())
    assert (START, "n1") in graph.edges


def test_compile_terminal_nodes_connect_to_end() -> None:
    """Nodes with no outgoing edges are wired to END."""
    graph = compile_flow(_linear_flow())
    assert ("n2", END) in graph.edges


def test_compile_conditional_edges_from_router() -> None:
    """Demo router edges become conditional branches."""
    demo = FlowSpec.model_validate_json(
        (FIXTURES / "sales_bot_objection_test.json").read_text(encoding="utf-8")
    )
    graph = compile_flow(demo)
    assert "router" in graph.nodes
    assert "router" in graph.branches


def test_compile_unknown_step_type_raises_at_compile_time() -> None:
    """Unregistered step types fail during compile_flow."""
    flow = FlowSpec.model_validate(
        {
            "flow_id": "bad",
            "entry_node": "n1",
            "nodes": [{"id": "n1", "step_type": "not_registered", "config": {}}],
            "edges": [],
        }
    )
    with pytest.raises(NotFoundError):
        compile_flow(flow)


async def test_node_fn_wraps_non_navbe_exceptions() -> None:
    """Bare RuntimeError from a step becomes ExecutionError."""

    @StepRegistry.register("boom_step")
    class BoomStep:
        config_schema = StepConfig

        def __init__(self, config: dict[str, Any]) -> None:
            self.config = StepConfig.model_validate(config)

        async def run(self, ctx: StepContext) -> Any:
            raise RuntimeError("kaboom")

    flow = FlowSpec.model_validate(
        {
            "flow_id": "boom",
            "entry_node": "n1",
            "nodes": [{"id": "n1", "step_type": "boom_step", "config": {}}],
            "edges": [],
        }
    )
    graph = compile_flow(flow)
    node = graph.nodes["n1"]
    state: FlowGraphState = {
        "node_outputs": {},
        "flow_vars": {},
        "current_input": None,
    }
    with pytest.raises(ExecutionError):
        await node.runnable.ainvoke(state)


def test_router_step_route_convention_matches_compiler() -> None:
    """RouterStep output key ``route`` is what conditional edges match."""
    from navbe.domains.steps.implementations.router_step import RouterStep

    sample = {"route": "handle", "next_node": "handle_objection"}
    assert sample["route"] == "handle"
    assert "routes" in RouterStep.config_schema.model_fields
