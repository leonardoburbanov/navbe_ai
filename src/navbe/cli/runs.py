"""navbe runs — inspect run history and watch live status."""

from __future__ import annotations

import click

from navbe.cli.actions import list_runs, show_run_status, watch_runs
from navbe.cli.errors import handle_navbe_errors


@click.group("runs")
def runs_group() -> None:
    """Inspect flow run history and live status."""


@runs_group.command("list")
@click.argument("flow_id", required=False, default=None)
@handle_navbe_errors
def runs_list(flow_id: str | None) -> None:
    """List all runs, or only those for FLOW_ID (most recent first)."""
    list_runs(flow_id)


@runs_group.command("status")
@click.argument("run_id")
@handle_navbe_errors
def runs_status(run_id: str) -> None:
    """Show current status for one run."""
    show_run_status(run_id)


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
    watch_runs(run_id, interval=interval)
