"""Shared serialization helpers for run detail responses (API + MCP)."""

from typing import Any

from navbe.domains.execution.models import RunDetail


def run_detail_payload(detail: RunDetail) -> dict[str, Any]:
    """Flatten RunDetail into state + steps + Mermaid diagram."""
    payload = detail.state.model_dump(mode="json")
    payload["steps"] = [step.model_dump(mode="json") for step in detail.steps]
    payload["diagram"] = detail.diagram
    return payload
