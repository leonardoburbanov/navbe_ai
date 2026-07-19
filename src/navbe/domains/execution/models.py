"""Pydantic models for workflow runs and node traces."""

from datetime import datetime
from enum import StrEnum
from typing import Any

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
