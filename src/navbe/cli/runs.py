"""navbe runs — inspect run history and watch live status."""

from __future__ import annotations

import time

import click
from rich.live import Live
from rich.text import Text

from navbe.cli.errors import handle_navbe_errors, run_async
from navbe.cli.format import build_runs_table, console, print_run_state, print_runs_table
from navbe.dependencies import get_run_service
from navbe.domains.execution.models import RunState, RunStatus

_TERMINAL = {RunStatus.COMPLETED, RunStatus.FAILED}
_ACTIVE = {RunStatus.PENDING, RunStatus.RUNNING, RunStatus.PAUSED}


@handle_navbe_errors
def _status(run_id: str) -> None:
    state = run_async(get_run_service().status(run_id))
    print_run_state(state)


@click.group("runs")
def runs_group() -> None:
    """Inspect flow run history and live status."""


@runs_group.command("list")
@click.argument("flow_id", required=False, default=None)
@handle_navbe_errors
def runs_list(flow_id: str | None) -> None:
    """List all runs, or only those for FLOW_ID (most recent first)."""
    runs = run_async(get_run_service().list_runs(flow_id))
    print_runs_table(runs)


@runs_group.command("status")
@click.argument("run_id")
@handle_navbe_errors
def runs_status(run_id: str) -> None:
    """Show current status for one run."""
    _status(run_id)


@runs_group.command("watch")
@click.argument("run_id", required=False, default=None)
@click.option(
    "--interval",
    default=1.0,
    show_default=True,
    type=float,
    help="Poll interval in seconds.",
)
@handle_navbe_errors
def runs_watch(run_id: str | None, interval: float) -> None:
    """Live status for one run, or all runs until none are active.

    Without RUN_ID, polls every run and redraws a table until no
    pending/running/paused runs remain (or Ctrl+C).

    ponytail: poll-based — upgrade: watch state.json on disk.
    """
    if run_id is None:
        _watch_all(interval)
    else:
        _watch_one(run_id, interval)


def _render_one(state: RunState) -> str:
    """Plain-text block for a single run Live panel."""
    lines = [
        f"run_id  {state.run_id}",
        f"flow_id {state.flow_id}",
        f"status  {state.status}",
    ]
    if state.current_node:
        lines.append(f"node    {state.current_node}")
    if state.error:
        lines.append(f"error   {state.error}")
    lines.append(f"updated {state.updated_at.isoformat(timespec='seconds')}")
    return "\n".join(lines)


def _watch_one(run_id: str, interval: float) -> None:
    """Poll one run until completed, failed, or Ctrl+C."""
    service = get_run_service()

    def render() -> str:
        return _render_one(run_async(service.status(run_id)))

    try:
        with Live(render(), console=console, refresh_per_second=4) as live:
            while True:
                state = run_async(service.status(run_id))
                live.update(render())
                if state.status in _TERMINAL:
                    break
                time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped watching.[/dim]")


def _watch_all(interval: float) -> None:
    """Poll all runs until none are active, or Ctrl+C."""
    service = get_run_service()

    def render():
        runs = run_async(service.list_runs(None))
        if not runs:
            return Text.from_markup("[dim]No runs found.[/dim]")
        return build_runs_table(runs, title="Runs (live)")

    try:
        with Live(render(), console=console, refresh_per_second=4) as live:
            while True:
                runs = run_async(service.list_runs(None))
                live.update(render())
                if not any(run.status in _ACTIVE for run in runs):
                    break
                time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped watching.[/dim]")
