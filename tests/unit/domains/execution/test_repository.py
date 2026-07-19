"""Tests for FileSystemRunRepository."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from navbe.core.exceptions import NotFoundError
from navbe.domains.execution.models import NodeTrace, RunState, RunStatus
from navbe.domains.execution.repository import FileSystemRunRepository, render_transcript


@pytest.fixture
def repo(tmp_path: Path) -> FileSystemRunRepository:
    """Repository rooted at tmp_path/runs/{flow_id}."""
    return FileSystemRunRepository(runs_dir_for=lambda flow_id: tmp_path / "runs" / flow_id)


async def test_save_trace_appends_to_jsonl(repo: FileSystemRunRepository, tmp_path: Path) -> None:
    """Two save_trace calls produce two JSONL lines."""
    now = datetime.now(UTC)
    run_id = "run-1"
    await repo.save_state(
        run_id,
        RunState(
            run_id=run_id,
            flow_id="flow_a",
            status=RunStatus.RUNNING,
            created_at=now,
            updated_at=now,
        ),
    )
    await repo.save_trace(
        run_id,
        NodeTrace(node_id="n1", input=1, output=2, started_at=now, finished_at=now),
    )
    await repo.save_trace(
        run_id,
        NodeTrace(node_id="n2", input=2, output=3, started_at=now, finished_at=now),
    )
    path = tmp_path / "runs" / "flow_a" / run_id / "trace.jsonl"
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert NodeTrace.model_validate_json(lines[0]).node_id == "n1"
    assert NodeTrace.model_validate_json(lines[1]).node_id == "n2"


async def test_save_state_writes_state_json(repo: FileSystemRunRepository) -> None:
    """state.json round-trips via RunState.model_validate_json."""
    now = datetime.now(UTC)
    state = RunState(
        run_id="run-2",
        flow_id="flow_a",
        status=RunStatus.COMPLETED,
        node_outputs={"n1": {"ok": True}},
        created_at=now,
        updated_at=now,
    )
    await repo.save_state("run-2", state)
    loaded = await repo.get_state("run-2")
    assert loaded.status == RunStatus.COMPLETED
    assert loaded.node_outputs == {"n1": {"ok": True}}


async def test_save_state_regenerates_transcript(
    repo: FileSystemRunRepository,
    tmp_path: Path,
) -> None:
    """transcript.md exists and mentions each node id."""
    now = datetime.now(UTC)
    run_id = "run-3"
    await repo.save_state(
        run_id,
        RunState(
            run_id=run_id,
            flow_id="flow_a",
            status=RunStatus.RUNNING,
            created_at=now,
            updated_at=now,
        ),
    )
    await repo.save_trace(
        run_id,
        NodeTrace(node_id="alpha", input="in", output="out", started_at=now, finished_at=now),
    )
    await repo.save_state(
        run_id,
        RunState(
            run_id=run_id,
            flow_id="flow_a",
            status=RunStatus.COMPLETED,
            created_at=now,
            updated_at=now,
        ),
    )
    transcript = (tmp_path / "runs" / "flow_a" / run_id / "transcript.md").read_text(
        encoding="utf-8"
    )
    assert "alpha" in transcript


async def test_get_state_missing_run_raises_not_found(repo: FileSystemRunRepository) -> None:
    """Missing runs raise NotFoundError."""
    with pytest.raises(NotFoundError) as exc_info:
        await repo.get_state("missing")
    assert exc_info.value.details["run_id"] == "missing"


async def test_list_runs_filters_by_flow_id(repo: FileSystemRunRepository) -> None:
    """list_runs only returns runs for the requested flow."""
    now = datetime.now(UTC)
    await repo.save_state(
        "r1",
        RunState(
            run_id="r1",
            flow_id="flow_a",
            status=RunStatus.COMPLETED,
            created_at=now,
            updated_at=now,
        ),
    )
    await repo.save_state(
        "r2",
        RunState(
            run_id="r2",
            flow_id="flow_b",
            status=RunStatus.COMPLETED,
            created_at=now,
            updated_at=now,
        ),
    )
    listed = await repo.list_runs("flow_a")
    assert [item.run_id for item in listed] == ["r1"]


def test_render_transcript_human_readable() -> None:
    """Transcript contains node ids and brief input/output text."""
    now = datetime.now(UTC)
    text = render_transcript(
        "flow_a",
        "run-9",
        [
            NodeTrace(node_id="n1", input={"a": 1}, output={"b": 2}, started_at=now),
            NodeTrace(node_id="n2", input="hello", output="world", started_at=now),
        ],
    )
    assert "## Node `n1`" in text
    assert "## Node `n2`" in text
    assert "hello" in text
    assert "world" in text
    assert text.index("n1") < text.index("n2")
