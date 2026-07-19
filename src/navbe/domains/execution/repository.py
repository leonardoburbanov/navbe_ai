"""Filesystem persistence for run state, traces, and transcripts."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import aiofiles

from navbe.core.exceptions import NotFoundError
from navbe.domains.execution.models import NodeTrace, RunState


def render_transcript(flow_id: str, run_id: str, traces: list[NodeTrace]) -> str:
    """Render a human-readable markdown transcript for a run."""
    lines = [
        "# Run transcript",
        "",
        f"- flow_id: `{flow_id}`",
        f"- run_id: `{run_id}`",
        "",
    ]
    for trace in traces:
        lines.append(f"## Node `{trace.node_id}`")
        lines.append("")
        lines.append(f"**Input:** {_brief(trace.input)}")
        lines.append("")
        if trace.error:
            lines.append(f"**Error:** {trace.error}")
        else:
            lines.append(f"**Output:** {_brief(trace.output)}")
        if trace.latency_ms is not None:
            lines.append("")
            lines.append(f"_latency: {trace.latency_ms:.1f} ms_")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _brief(value: Any, limit: int = 240) -> str:
    """Short printable summary for transcript sections."""
    if value is None:
        return "_(none)_"
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, default=str, ensure_ascii=True)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


class FileSystemRunRepository:
    """Store runs under ``runs_dir_for(flow_id) / run_id /``."""

    def __init__(self, runs_dir_for: Callable[[str], Path]) -> None:
        """Create a repository with a flow-scoped runs directory factory."""
        self._runs_dir_for = runs_dir_for
        self._index_dir = runs_dir_for("__run_index__")
        self._index_dir.mkdir(parents=True, exist_ok=True)

    def _run_dir(self, flow_id: str, run_id: str) -> Path:
        """Return the directory for one run."""
        return self._runs_dir_for(flow_id) / run_id

    def _index_path(self, run_id: str) -> Path:
        """Return the index file that maps run_id -> flow_id."""
        return self._index_dir / f"{run_id}.json"

    async def _resolve_flow_id(self, run_id: str) -> str:
        """Lookup flow_id for a run_id via the index."""
        path = self._index_path(run_id)
        if not path.exists():
            raise NotFoundError(
                f"Run '{run_id}' not found",
                details={"run_id": run_id},
            )
        async with aiofiles.open(path, encoding="utf-8") as handle:
            payload = json.loads(await handle.read())
        return str(payload["flow_id"])

    async def _remember_run(self, flow_id: str, run_id: str) -> None:
        """Persist run_id -> flow_id for later get_state lookups."""
        path = self._index_path(run_id)
        async with aiofiles.open(path, "w", encoding="utf-8") as handle:
            await handle.write(json.dumps({"flow_id": flow_id, "run_id": run_id}))

    async def _read_traces(self, run_dir: Path) -> list[NodeTrace]:
        """Load all traces from trace.jsonl if present."""
        path = run_dir / "trace.jsonl"
        if not path.exists():
            return []
        async with aiofiles.open(path, encoding="utf-8") as handle:
            lines = await handle.readlines()
        return [NodeTrace.model_validate_json(line) for line in lines if line.strip()]

    async def save_trace(self, run_id: str, trace: NodeTrace) -> None:
        """Append one JSONL trace line for ``run_id``."""
        flow_id = await self._resolve_flow_id(run_id)
        run_dir = self._run_dir(flow_id, run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "trace.jsonl"
        async with aiofiles.open(path, "a", encoding="utf-8") as handle:
            await handle.write(trace.model_dump_json() + "\n")

    async def save_state(self, run_id: str, state: RunState) -> None:
        """Write state.json and regenerate transcript.md."""
        await self._remember_run(state.flow_id, run_id)
        run_dir = self._run_dir(state.flow_id, run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        state_path = run_dir / "state.json"
        async with aiofiles.open(state_path, "w", encoding="utf-8") as handle:
            await handle.write(state.model_dump_json(indent=2))

        traces = await self._read_traces(run_dir)
        transcript = render_transcript(state.flow_id, run_id, traces)
        async with aiofiles.open(run_dir / "transcript.md", "w", encoding="utf-8") as handle:
            await handle.write(transcript)

    async def get_state(self, run_id: str) -> RunState:
        """Load the latest state.json for a run."""
        flow_id = await self._resolve_flow_id(run_id)
        path = self._run_dir(flow_id, run_id) / "state.json"
        if not path.exists():
            raise NotFoundError(
                f"Run '{run_id}' not found",
                details={"run_id": run_id},
            )
        async with aiofiles.open(path, encoding="utf-8") as handle:
            return RunState.model_validate_json(await handle.read())

    async def list_runs(self, flow_id: str) -> list[RunState]:
        """List all runs under a flow's runs directory, most recent first."""
        root = self._runs_dir_for(flow_id)
        if not root.exists():
            return []
        states: list[RunState] = []
        for child in sorted(root.iterdir()):
            state_path = child / "state.json"
            if child.is_dir() and state_path.exists():
                async with aiofiles.open(state_path, encoding="utf-8") as handle:
                    states.append(RunState.model_validate_json(await handle.read()))
        states.sort(key=lambda state: state.updated_at, reverse=True)
        return states
