"""Tests for execution Protocol fakes."""

from datetime import UTC, datetime
from typing import Any

from navbe.domains.execution.interfaces import ExecutionEngine, RunRepository
from navbe.domains.execution.models import NodeTrace, RunState, RunStatus
from navbe.domains.flows.models import FlowSpec


class FakeRunRepository:
    """In-memory run repository."""

    def __init__(self) -> None:
        self.states: dict[str, RunState] = {}
        self.traces: dict[str, list[NodeTrace]] = {}

    async def save_trace(self, run_id: str, trace: NodeTrace) -> None:
        self.traces.setdefault(run_id, []).append(trace)

    async def save_state(self, run_id: str, state: RunState) -> None:
        self.states[run_id] = state

    async def get_state(self, run_id: str) -> RunState:
        return self.states[run_id]

    async def list_runs(self, flow_id: str) -> list[RunState]:
        runs = [state for state in self.states.values() if state.flow_id == flow_id]
        runs.sort(key=lambda state: state.updated_at, reverse=True)
        return runs


class FakeExecutionEngine:
    """In-memory execution engine."""

    def __init__(self) -> None:
        self.runs: list[tuple[FlowSpec, str, Any]] = []
        self.states: dict[str, RunState] = {}

    async def run(self, flow_spec: FlowSpec, run_id: str, initial_input: Any) -> RunState:
        self.runs.append((flow_spec, run_id, initial_input))
        now = datetime.now(UTC)
        state = RunState(
            run_id=run_id,
            flow_id=flow_spec.flow_id,
            status=RunStatus.COMPLETED,
            created_at=now,
            updated_at=now,
        )
        self.states[run_id] = state
        return state

    async def get_status(self, run_id: str) -> RunState:
        return self.states[run_id]

    async def resume(self, run_id: str, decision: dict) -> RunState:
        return self.states[run_id]

    async def list_runs(self, flow_id: str) -> list[RunState]:
        runs = [state for state in self.states.values() if state.flow_id == flow_id]
        runs.sort(key=lambda state: state.updated_at, reverse=True)
        return runs


def test_fake_engine_and_repository_satisfy_protocols() -> None:
    """Runtime-checkable Protocols accept structural fakes."""
    assert isinstance(FakeExecutionEngine(), ExecutionEngine)
    assert isinstance(FakeRunRepository(), RunRepository)
