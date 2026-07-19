"""Structural validation for FlowSpec graphs."""

from pydantic import BaseModel

from navbe.core.exceptions import NotFoundError
from navbe.domains.flows.models import EdgeSpec, FlowSpec
from navbe.domains.steps.registry import StepRegistry

# Handled structurally by execution/graph_compiler — not via StepRegistry.
RESERVED_STEP_TYPES = {"approval"}


class ValidationIssue(BaseModel):
    """One graph-validation problem."""

    code: str
    message: str
    node_id: str | None = None
    edge_index: int | None = None


class ValidationResult(BaseModel):
    """Aggregate result of graph validation."""

    valid: bool
    issues: list[ValidationIssue] = []


def _bfs_reachable(entry: str, edges: list[EdgeSpec]) -> set[str]:
    """Return node ids reachable from ``entry`` following edge ``to`` targets."""
    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        if edge.to is not None:
            adjacency.setdefault(edge.from_, []).append(edge.to)

    reachable = {entry}
    queue = [entry]
    while queue:
        current = queue.pop(0)
        for nxt in adjacency.get(current, []):
            if nxt not in reachable:
                reachable.add(nxt)
                queue.append(nxt)
    return reachable


def validate_graph(flow_spec: FlowSpec) -> ValidationResult:
    """Validate entry, step types, edges, reachability, and connector refs."""
    issues: list[ValidationIssue] = []
    node_ids = {node.id for node in flow_spec.nodes}

    if flow_spec.entry_node not in node_ids:
        issues.append(
            ValidationIssue(
                code="missing_entry_node",
                message=f"entry_node '{flow_spec.entry_node}' not found among nodes",
            )
        )

    for node in flow_spec.nodes:
        if node.step_type in RESERVED_STEP_TYPES:
            continue
        try:
            StepRegistry.get(node.step_type)
        except NotFoundError:
            issues.append(
                ValidationIssue(
                    code="unknown_step_type",
                    message=f"step_type '{node.step_type}' is not registered",
                    node_id=node.id,
                )
            )

    for i, edge in enumerate(flow_spec.edges):
        if edge.from_ not in node_ids:
            issues.append(
                ValidationIssue(
                    code="edge_from_not_found",
                    message=f"edge[{i}].from '{edge.from_}' not found",
                    edge_index=i,
                )
            )
        if edge.to is not None and edge.to not in node_ids:
            issues.append(
                ValidationIssue(
                    code="edge_to_not_found",
                    message=f"edge[{i}].to '{edge.to}' not found",
                    edge_index=i,
                )
            )

    reachable = _bfs_reachable(flow_spec.entry_node, flow_spec.edges)
    for node in flow_spec.nodes:
        if node.id not in reachable:
            issues.append(
                ValidationIssue(
                    code="orphan_node",
                    message=f"node '{node.id}' is unreachable from entry_node",
                    node_id=node.id,
                )
            )

    for node in flow_spec.nodes:
        connector_name = node.config.get("connector")
        if connector_name and connector_name not in flow_spec.connectors:
            issues.append(
                ValidationIssue(
                    code="unknown_connector_reference",
                    message=(
                        f"node '{node.id}' references undeclared "
                        f"connector '{connector_name}'"
                    ),
                    node_id=node.id,
                )
            )

    return ValidationResult(valid=len(issues) == 0, issues=issues)
