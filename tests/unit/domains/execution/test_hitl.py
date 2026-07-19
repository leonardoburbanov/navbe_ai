"""Tests for human-in-the-loop approval pause/resume."""

from pathlib import Path
from unittest.mock import AsyncMock

import navbe.domains.steps.implementations  # noqa: F401
from navbe.domains.execution.engine import LangGraphEngine
from navbe.domains.execution.models import RunStatus
from navbe.domains.flows.models import FlowSpec
from tests.unit.domains.execution.test_interfaces import FakeRunRepository


def _approval_flow() -> FlowSpec:
    return FlowSpec.model_validate(
        {
            "flow_id": "hitl",
            "entry_node": "work",
            "nodes": [
                {
                    "id": "work",
                    "step_type": "set_var",
                    "config": {"var_name": "x", "value_from": "x"},
                },
                {
                    "id": "needs_approval",
                    "step_type": "approval",
                    "config": {"message": "Approve next step?"},
                },
                {
                    "id": "done",
                    "step_type": "set_var",
                    "config": {"var_name": "y", "value_from": "var_name"},
                },
            ],
            "edges": [
                {"from": "work", "to": "needs_approval"},
                {"from": "needs_approval", "to": "done"},
            ],
        }
    )


def _engine(tmp_path: Path) -> LangGraphEngine:
    return LangGraphEngine(
        run_repository=FakeRunRepository(),
        checkpoint_db_path=str(tmp_path / "hitl.db"),
        resolve_connectors=AsyncMock(return_value={}),
    )


async def test_flow_with_approval_node_pauses(tmp_path: Path) -> None:
    """Approval node pauses the run."""
    state = await _engine(tmp_path).run(_approval_flow(), "hitl-1", {"x": 1})
    assert state.status == RunStatus.PAUSED
    assert state.current_node == "needs_approval"


async def test_resume_with_approved_true_continues_flow(tmp_path: Path) -> None:
    """approved=True resumes through to COMPLETED."""
    engine = _engine(tmp_path)
    paused = await engine.run(_approval_flow(), "hitl-2", {"x": 1})
    assert paused.status == RunStatus.PAUSED
    final = await engine.resume("hitl-2", {"approved": True})
    assert final.status == RunStatus.COMPLETED
    assert "done" in final.node_outputs


async def test_resume_with_approved_false_halts_as_failed(tmp_path: Path) -> None:
    """approved=False fails the run."""
    engine = _engine(tmp_path)
    await engine.run(_approval_flow(), "hitl-3", {"x": 1})
    final = await engine.resume("hitl-3", {"approved": False})
    assert final.status == RunStatus.FAILED
    assert final.error is not None
    assert "not approved" in final.error


async def test_status_while_paused_reflects_paused_node(tmp_path: Path) -> None:
    """status() between pause and resume reports PAUSED + node id."""
    engine = _engine(tmp_path)
    await engine.run(_approval_flow(), "hitl-4", {"x": 1})
    status = await engine.get_status("hitl-4")
    assert status.status == RunStatus.PAUSED
    assert status.current_node == "needs_approval"
