"""Tests for LangGraphEngine."""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

import navbe.domains.steps.implementations  # noqa: F401
from navbe.core.exceptions import ExecutionError
from navbe.domains.execution.engine import LangGraphEngine
from navbe.domains.execution.models import RunStatus
from navbe.domains.flows.models import FlowSpec
from navbe.domains.steps.interfaces import StepContext
from navbe.domains.steps.models import StepConfig
from navbe.domains.steps.registry import StepRegistry
from tests.unit.domains.execution.test_interfaces import FakeRunRepository


def _set_var_flow() -> FlowSpec:
    return FlowSpec.model_validate(
        {
            "flow_id": "one_node",
            "entry_node": "n1",
            "nodes": [
                {
                    "id": "n1",
                    "step_type": "set_var",
                    "config": {"var_name": "amount", "value_from": "amount"},
                },
                {
                    "id": "n2",
                    "step_type": "set_var",
                    "config": {"var_name": "echo", "value_from": "var_name"},
                },
            ],
            "edges": [{"from": "n1", "to": "n2"}],
        }
    )


@pytest.fixture
def engine(tmp_path: Path) -> LangGraphEngine:
    """Engine with temp checkpoint DB and fake repository."""
    return LangGraphEngine(
        run_repository=FakeRunRepository(),
        checkpoint_db_path=str(tmp_path / "checkpoints.db"),
        resolve_connectors=AsyncMock(return_value={}),
    )


async def test_run_simple_two_node_flow_completes(engine: LangGraphEngine) -> None:
    """set_var -> set_var completes with both node_outputs."""
    state = await engine.run(_set_var_flow(), "run-simple", {"amount": 21})
    assert state.status == RunStatus.COMPLETED
    assert "n1" in state.node_outputs
    assert "n2" in state.node_outputs


async def test_run_persists_final_state_via_repository(tmp_path: Path) -> None:
    """repository.save_state is called with COMPLETED."""
    repo = FakeRunRepository()
    repo.save_state = AsyncMock(wraps=repo.save_state)
    engine = LangGraphEngine(
        run_repository=repo,
        checkpoint_db_path=str(tmp_path / "cp.db"),
        resolve_connectors=AsyncMock(return_value={}),
    )
    flow = FlowSpec.model_validate(
        {
            "flow_id": "persist",
            "entry_node": "n1",
            "nodes": [
                {
                    "id": "n1",
                    "step_type": "set_var",
                    "config": {"var_name": "a", "value_from": "a"},
                }
            ],
            "edges": [],
        }
    )
    await engine.run(flow, "run-persist", {"a": 1})
    repo.save_state.assert_awaited()
    saved_state = repo.save_state.await_args.args[1]
    assert saved_state.status == RunStatus.COMPLETED


async def test_run_step_failure_produces_failed_status(tmp_path: Path) -> None:
    """Step ExecutionError becomes FAILED RunState."""

    @StepRegistry.register("fail_step")
    class FailStep:
        config_schema = StepConfig

        def __init__(self, config: dict[str, Any]) -> None:
            self.config = StepConfig.model_validate(config)

        async def run(self, ctx: StepContext) -> Any:
            raise ExecutionError("intentional failure", details={"node_id": ctx.node_id})

    flow = FlowSpec.model_validate(
        {
            "flow_id": "fail",
            "entry_node": "n1",
            "nodes": [{"id": "n1", "step_type": "fail_step", "config": {}}],
            "edges": [],
        }
    )
    engine = LangGraphEngine(
        run_repository=FakeRunRepository(),
        checkpoint_db_path=str(tmp_path / "fail.db"),
        resolve_connectors=AsyncMock(return_value={}),
    )
    state = await engine.run(flow, "run-fail", None)
    assert state.status == RunStatus.FAILED
    assert state.error is not None
    assert "intentional failure" in state.error


async def test_get_status_delegates_to_repository(tmp_path: Path) -> None:
    """get_status reads from the repository."""
    repo = FakeRunRepository()
    engine = LangGraphEngine(
        run_repository=repo,
        checkpoint_db_path=str(tmp_path / "st.db"),
    )
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    from navbe.domains.execution.models import RunState

    expected = RunState(
        run_id="r1",
        flow_id="f1",
        status=RunStatus.COMPLETED,
        created_at=now,
        updated_at=now,
    )
    await repo.save_state("r1", expected)
    assert await engine.get_status("r1") == expected


async def test_checkpointing_allows_state_recovery(tmp_path: Path) -> None:
    """Checkpoint DB retains a resumable thread for the run_id."""
    db_path = str(tmp_path / "ckpt.db")
    engine = LangGraphEngine(
        run_repository=FakeRunRepository(),
        checkpoint_db_path=db_path,
        resolve_connectors=AsyncMock(return_value={}),
    )
    flow = FlowSpec.model_validate(
        {
            "flow_id": "ckpt",
            "entry_node": "n1",
            "nodes": [
                {
                    "id": "n1",
                    "step_type": "set_var",
                    "config": {"var_name": "a", "value_from": "a"},
                },
                {
                    "id": "n2",
                    "step_type": "set_var",
                    "config": {"var_name": "b", "value_from": "var_name"},
                },
            ],
            "edges": [{"from": "n1", "to": "n2"}],
        }
    )
    await engine.run(flow, "thread-ckpt", {"a": 1})
    async with AsyncSqliteSaver.from_conn_string(db_path) as saver:
        config = {"configurable": {"thread_id": "thread-ckpt"}}
        tup = await saver.aget_tuple(config)
        assert tup is not None
