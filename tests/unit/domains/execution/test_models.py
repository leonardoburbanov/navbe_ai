"""Tests for execution models."""

from datetime import UTC, datetime

from navbe.domains.execution.models import NodeTrace, RunState, RunStatus


def test_run_status_enum_values() -> None:
    """StrEnum values compare equal to their strings."""
    assert RunStatus.PENDING == "pending"
    assert RunStatus.COMPLETED == "completed"


def test_node_trace_latency_optional_before_finish() -> None:
    """NodeTrace validates with only started_at set."""
    trace = NodeTrace(node_id="n1", input={"x": 1}, started_at=datetime.now(UTC))
    assert trace.finished_at is None
    assert trace.latency_ms is None


def test_run_state_defaults() -> None:
    """RunState defaults node_outputs to {} and current_node to None."""
    now = datetime.now(UTC)
    state = RunState(
        run_id="r1",
        flow_id="f1",
        status=RunStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    assert state.node_outputs == {}
    assert state.current_node is None
