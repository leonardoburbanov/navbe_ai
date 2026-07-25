"""Tests for single-flight and cancel on RunService."""

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from navbe.core.exceptions import ExecutionError
from navbe.domains.execution.models import RunState, RunStatus
from navbe.domains.execution.service import RunService
from navbe.domains.flows.models import FlowSpec
from tests.unit.domains.execution.test_interfaces import FakeExecutionEngine
from tests.unit.domains.execution.test_service import (
    FakeConnectorService,
    FakeFlowService,
    _await_background,
    _flow,
)


class HangingEngine(FakeExecutionEngine):
    """Engine whose run() blocks until cancelled."""

    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()

    async def run(self, flow_spec: FlowSpec, run_id: str, initial_input: Any) -> RunState:
        now = datetime.now(UTC)
        state = RunState(
            run_id=run_id,
            flow_id=flow_spec.flow_id,
            status=RunStatus.RUNNING,
            created_at=now,
            updated_at=now,
        )
        self.states[run_id] = state
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled = state.model_copy(
                update={
                    "status": RunStatus.CANCELLED,
                    "error": "cancelled",
                    "updated_at": datetime.now(UTC),
                }
            )
            self.states[run_id] = cancelled
            raise
        return state


async def test_start_rejects_when_flow_busy() -> None:
    """Manual start raises when an active run already exists."""
    engine = FakeExecutionEngine()
    now = datetime.now(UTC)
    engine.states["active"] = RunState(
        run_id="active",
        flow_id="svc_flow",
        status=RunStatus.RUNNING,
        created_at=now,
        updated_at=now,
    )
    service = RunService(engine, FakeFlowService(_flow()), FakeConnectorService())
    with pytest.raises(ExecutionError, match="already has an active run"):
        await service.start("svc_flow")


async def test_start_skip_if_busy_returns_none() -> None:
    """Scheduler path returns None instead of raising when busy."""
    engine = FakeExecutionEngine()
    now = datetime.now(UTC)
    engine.states["active"] = RunState(
        run_id="active",
        flow_id="svc_flow",
        status=RunStatus.RUNNING,
        created_at=now,
        updated_at=now,
    )
    service = RunService(engine, FakeFlowService(_flow()), FakeConnectorService())
    result = await service.start("svc_flow", skip_if_busy=True)
    assert result is None


async def test_cancel_active_run() -> None:
    """cancel() stops a hanging run and marks it cancelled."""
    engine = HangingEngine()
    service = RunService(engine, FakeFlowService(_flow()), FakeConnectorService())
    run_id = await service.start("svc_flow")
    assert run_id is not None
    await engine.started.wait()
    state = await service.cancel(run_id)
    assert state.status == RunStatus.CANCELLED
    await _await_background(service)
