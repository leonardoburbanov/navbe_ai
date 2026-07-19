"""Compile a FlowSpec into a LangGraph StateGraph."""

from typing import Any, cast

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from typing_extensions import TypedDict

from navbe.core.exceptions import ExecutionError, NavbeError, NotFoundError
from navbe.domains.flows.models import FlowSpec, NodeSpec
from navbe.domains.steps.interfaces import StepContext
from navbe.domains.steps.registry import StepRegistry

APPROVAL_STEP_TYPE = "approval"


class FlowGraphState(TypedDict):
    """LangGraph state for Navbe flow runs."""

    node_outputs: dict[str, Any]
    flow_vars: dict[str, Any]
    current_input: Any


def _apply_set_var(flow_vars: dict[str, Any], result: Any) -> dict[str, Any]:
    """Copy set_var results into flow_vars when shaped as var_name/value."""
    updated = dict(flow_vars)
    if isinstance(result, dict) and "var_name" in result and "value" in result:
        updated[str(result["var_name"])] = result["value"]
    return updated


def _make_approval_node(node: NodeSpec):
    """Build a HITL approval node that calls langgraph.interrupt."""

    async def approval_node_fn(state: FlowGraphState) -> dict[str, Any]:
        decision = interrupt(
            {
                "node_id": node.id,
                "message": node.config.get("message", "Approval required"),
            }
        )
        if not isinstance(decision, dict) or not decision.get("approved", False):
            raise ExecutionError(
                f"Run halted: node '{node.id}' was not approved",
                details={"node_id": node.id},
            )
        return {
            "node_outputs": {**state["node_outputs"], node.id: decision},
            "current_input": decision,
            "flow_vars": state["flow_vars"],
        }

    return approval_node_fn


def _make_step_node(
    node: NodeSpec,
    step_cls: type,
    *,
    llm_client: Any | None = None,
    connectors: dict[str, Any] | None = None,
):
    """Build a generic StepRegistry-backed node function."""
    # ponytail: connectors closed over (not in state) — upgrade: RunnableConfig
    # so checkpoint msgpack never sees live HTTPConnector instances.
    resolved_connectors = connectors or {}

    async def node_fn(state: FlowGraphState) -> dict[str, Any]:
        if node.step_type == "llm_call" and llm_client is not None:
            step_instance = step_cls(node.config, client=llm_client)
        else:
            step_instance = step_cls(node.config)
        ctx = StepContext(
            node_id=node.id,
            input_data=state["current_input"],
            flow_vars={
                **state["flow_vars"],
                "connectors": resolved_connectors,
                "node_outputs": state["node_outputs"],
            },
        )
        try:
            result = await step_instance.run(ctx)
        except NavbeError:
            raise
        except Exception as exc:
            raise ExecutionError(
                f"Node '{node.id}' failed: {exc}",
                details={"node_id": node.id},
            ) from exc
        return {
            "node_outputs": {**state["node_outputs"], node.id: result},
            "current_input": result,
            "flow_vars": _apply_set_var(state["flow_vars"], result),
        }

    return node_fn


def compile_flow(
    flow_spec: FlowSpec,
    *,
    llm_client: Any | None = None,
    connectors: dict[str, Any] | None = None,
) -> Any:
    """Compile a validated FlowSpec into an uncompiled StateGraph."""
    # cast: ty does not treat TypedDict subclasses as StateLike Protocols.
    graph = StateGraph(cast(Any, FlowGraphState))

    for node in flow_spec.nodes:
        if node.step_type == APPROVAL_STEP_TYPE:
            graph.add_node(node.id, _make_approval_node(node))
            continue
        try:
            step_cls = StepRegistry.get(node.step_type)
        except NotFoundError:
            raise
        graph.add_node(
            node.id,
            _make_step_node(
                node,
                step_cls,
                llm_client=llm_client,
                connectors=connectors,
            ),
        )

    graph.add_edge(START, flow_spec.entry_node)

    direct_edges = [edge for edge in flow_spec.edges if edge.condition is None]
    conditional_by_source: dict[str, list] = {}
    for edge in flow_spec.edges:
        if edge.condition is not None:
            conditional_by_source.setdefault(edge.from_, []).append(edge)

    for edge in direct_edges:
        if edge.to is None:
            raise ExecutionError(
                f"Direct edge from '{edge.from_}' is missing 'to'",
                details={"from": edge.from_},
            )
        graph.add_edge(edge.from_, edge.to)

    for source, edges in conditional_by_source.items():

        def make_router(_edges=edges, _source=source):
            def router(state: FlowGraphState) -> str:
                """Match RouterStep's ``route`` field to edge.condition."""
                route_value = state["node_outputs"].get(_source, {}).get("route")
                for edge in _edges:
                    if edge.condition == route_value or edge.condition == "default":
                        if edge.to is None:
                            raise ExecutionError(
                                f"Conditional edge from '{_source}' is missing 'to'",
                                details={"source": _source, "condition": edge.condition},
                            )
                        return edge.to
                raise ExecutionError(
                    f"No matching conditional edge from '{_source}' for route",
                    details={"source": _source, "route": route_value},
                )

            return router

        graph.add_conditional_edges(source, make_router())

    sources = {edge.from_ for edge in flow_spec.edges}
    terminal_nodes = {node.id for node in flow_spec.nodes} - sources
    for terminal in terminal_nodes:
        graph.add_edge(terminal, END)

    return graph
