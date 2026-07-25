"""Pydantic models for workflow runs and node traces."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel


class RunStatus(StrEnum):
    """Lifecycle status for a flow run."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class NodeTrace(BaseModel):
    """Per-node execution trace entry."""

    node_id: str
    input: Any
    output: Any = None
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    latency_ms: float | None = None


class RunState(BaseModel):
    """Persisted snapshot of a flow run."""

    run_id: str
    flow_id: str
    status: RunStatus
    node_outputs: dict[str, Any] = {}
    current_node: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class StepExecution(BaseModel):
    """Agent/CLI-facing summary of one executed (or paused) node."""

    node_id: str
    step_type: str
    status: Literal["completed", "failed", "paused"]
    latency_ms: float | None = None
    error: str | None = None


class RunDetail(BaseModel):
    """Run state plus step timeline and Mermaid diagram."""

    state: RunState
    steps: list[StepExecution]
    diagram: str
