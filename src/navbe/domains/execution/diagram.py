"""Mermaid diagrams and step summaries for run UX."""

from __future__ import annotations

import re

from navbe.domains.execution.models import (
    NodeTrace,
    RunStatus,
    StepExecution,
)
from navbe.domains.flows.models import FlowSpec

_SAFE_ID = re.compile(r"[^a-zA-Z0-9_]")


def _mermaid_id(node_id: str) -> str:
    """Sanitize a node id for Mermaid node identifiers."""
    safe = _SAFE_ID.sub("_", node_id)
    if not safe or safe[0].isdigit():
        return f"n_{safe}"
    return safe


def _escape_label(text: str) -> str:
    """Escape characters that break Mermaid node labels."""
    return text.replace('"', "'").replace("\n", " ")


def build_step_executions(
    flow: FlowSpec,
    traces: list[NodeTrace],
    *,
    status: RunStatus,
    current_node: str | None = None,
) -> list[StepExecution]:
    """Map traces (+ paused current node) to StepExecution list."""
    step_types = {node.id: node.step_type for node in flow.nodes}
    steps: list[StepExecution] = []
    seen: set[str] = set()
    for trace in traces:
        seen.add(trace.node_id)
        steps.append(
            StepExecution(
                node_id=trace.node_id,
                step_type=step_types.get(trace.node_id, "unknown"),
                status="failed" if trace.error else "completed",
                latency_ms=trace.latency_ms,
                error=trace.error,
            )
        )
    if (
        status == RunStatus.PAUSED
        and current_node
        and current_node not in seen
    ):
        steps.append(
            StepExecution(
                node_id=current_node,
                step_type=step_types.get(current_node, "unknown"),
                status="paused",
                latency_ms=None,
                error=None,
            )
        )
    return steps


def render_run_mermaid(
    flow: FlowSpec,
    traces: list[NodeTrace],
    status: RunStatus,
    *,
    current_node: str | None = None,
) -> str:
    """Render a flowchart TD Mermaid diagram for a run.

    Executed nodes are styled completed / failed; paused current node is
    highlighted; nodes never reached stay dim (skipped).
    """
    failed = {t.node_id for t in traces if t.error}
    completed = {t.node_id for t in traces if not t.error}
    lines = ["flowchart TD"]
    for node in flow.nodes:
        mid = _mermaid_id(node.id)
        label = _escape_label(f"{node.id}<br/>{node.step_type}")
        if node.id in failed:
            lines.append(f'  {mid}["{label}"]:::failed')
        elif node.id == current_node and status == RunStatus.PAUSED:
            lines.append(f'  {mid}["{label}"]:::paused')
        elif node.id in completed:
            lines.append(f'  {mid}["{label}"]:::ok')
        else:
            lines.append(f'  {mid}["{label}"]:::skip')

    for edge in flow.edges:
        if edge.to is None:
            continue
        src = _mermaid_id(edge.from_)
        dst = _mermaid_id(edge.to)
        if edge.condition:
            cond = _escape_label(edge.condition)
            lines.append(f'  {src} -->|"{cond}"| {dst}')
        else:
            lines.append(f"  {src} --> {dst}")

    lines.extend(
        [
            "  classDef ok fill:#d4edda,stroke:#28a745,color:#155724",
            "  classDef failed fill:#f8d7da,stroke:#dc3545,color:#721c24",
            "  classDef paused fill:#fff3cd,stroke:#ffc107,color:#856404",
            "  classDef skip fill:#f0f0f0,stroke:#adb5bd,color:#6c757d",
        ]
    )
    return "\n".join(lines) + "\n"
