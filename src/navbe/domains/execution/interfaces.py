"""Execution engine and run repository contracts."""

from typing import Any, Protocol, runtime_checkable

from navbe.domains.execution.models import NodeTrace, RunState
from navbe.domains.flows.models import FlowSpec


@runtime_checkable
class ExecutionEngine(Protocol):
    """Port for compiling/running flow graphs."""

    async def run(self, flow_spec: FlowSpec, run_id: str, initial_input: Any) -> RunState:
        """Execute a flow to completion, pause, or failure."""
        ...

    async def get_status(self, run_id: str) -> RunState:
        """Return the latest persisted run state."""
        ...

    async def resume(self, run_id: str, decision: dict) -> RunState:
        """Resume a paused (HITL) run with a decision payload."""
        ...

    async def list_runs(self, flow_id: str | None = None) -> list[RunState]:
        """List runs for a flow, or all runs when ``flow_id`` is None."""
        ...


@runtime_checkable
class RunRepository(Protocol):
    """Persistence port for run state and traces."""

    async def save_trace(self, run_id: str, trace: NodeTrace) -> None:
        """Append a node trace line."""
        ...

    async def save_state(self, run_id: str, state: RunState) -> None:
        """Persist latest run state and regenerate transcript."""
        ...

    async def get_state(self, run_id: str) -> RunState:
        """Load run state by id."""
        ...

    async def list_runs(self, flow_id: str | None = None) -> list[RunState]:
        """List runs for a flow, or all runs when ``flow_id`` is None."""
        ...
