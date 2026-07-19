"""Tests for RunService."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from navbe.core.exceptions import NotFoundError
from navbe.domains.execution.models import RunState, RunStatus
from navbe.domains.execution.service import RunService
from navbe.domains.flows.models import FlowSpec
from tests.unit.domains.execution.test_interfaces import FakeExecutionEngine


class FakeFlowService:
    """Minimal flow service fake."""

    def __init__(self, flow: FlowSpec | None = None, error: Exception | None = None) -> None:
        self.flow = flow
        self.error = error

    async def get(self, flow_id: str) -> FlowSpec:
        if self.error is not None:
            raise self.error
        assert self.flow is not None
        return self.flow


class FakeConnectorService:
    """Minimal connector service fake."""

    async def resolve(self, name: str, instance_config: dict[str, Any]) -> Any:
        return object()


def _flow() -> FlowSpec:
    return FlowSpec.model_validate(
        {
            "flow_id": "svc_flow",
            "entry_node": "n1",
            "nodes": [
                {
                    "id": "n1",
                    "step_type": "set_var",
                    "config": {"var_name": "x", "value_from": "x"},
                }
            ],
            "edges": [],
        }
    )


async def test_start_fetches_flow_and_triggers_engine_run() -> None:
    """start() loads the flow and calls engine.run."""
    engine = FakeExecutionEngine()
    engine.run = AsyncMock(wraps=engine.run)
    flow = _flow()
    service = RunService(engine, FakeFlowService(flow), FakeConnectorService())
    run_id = await service.start("svc_flow", {"x": 1})
    engine.run.assert_awaited_once()
    assert engine.run.await_args.args[0].flow_id == "svc_flow"
    assert engine.run.await_args.args[1] == run_id


async def test_start_returns_a_run_id() -> None:
    """start() returns a non-empty UUID-shaped string."""
    service = RunService(FakeExecutionEngine(), FakeFlowService(_flow()), FakeConnectorService())
    run_id = await service.start("svc_flow")
    assert isinstance(run_id, str)
    assert len(run_id) >= 8
    assert "-" in run_id


async def test_status_delegates_to_engine() -> None:
    """status() forwards to engine.get_status."""
    engine = FakeExecutionEngine()
    now = datetime.now(UTC)
    engine.states["r1"] = RunState(
        run_id="r1",
        flow_id="svc_flow",
        status=RunStatus.COMPLETED,
        created_at=now,
        updated_at=now,
    )
    engine.get_status = AsyncMock(wraps=engine.get_status)
    service = RunService(engine, FakeFlowService(_flow()), FakeConnectorService())
    state = await service.status("r1")
    engine.get_status.assert_awaited_once_with("r1")
    assert state.status == RunStatus.COMPLETED


async def test_resume_delegates_to_engine() -> None:
    """resume() forwards to engine.resume."""
    engine = FakeExecutionEngine()
    now = datetime.now(UTC)
    engine.states["r1"] = RunState(
        run_id="r1",
        flow_id="svc_flow",
        status=RunStatus.PAUSED,
        created_at=now,
        updated_at=now,
    )
    engine.resume = AsyncMock(wraps=engine.resume)
    service = RunService(engine, FakeFlowService(_flow()), FakeConnectorService())
    await service.resume("r1", {"approved": True})
    engine.resume.assert_awaited_once_with("r1", {"approved": True})


async def test_start_unknown_flow_propagates_not_found() -> None:
    """NotFoundError from flow_service.get bubbles unchanged."""
    service = RunService(
        FakeExecutionEngine(),
        FakeFlowService(error=NotFoundError("missing", details={"flow_id": "nope"})),
        FakeConnectorService(),
    )
    with pytest.raises(NotFoundError):
        await service.start("nope")
