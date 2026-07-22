"""navbe runs — inspect run history and watch live status."""

from __future__ import annotations

from typing import Annotated

import typer

from navbe.cli.actions import list_runs, show_run_status, watch_runs
from navbe.cli.errors import handle_navbe_errors

app = typer.Typer(help="Inspect flow run history and live status.")


@app.command("list")
@handle_navbe_errors
def runs_list(
    flow_id: Annotated[
        str | None,
        typer.Argument(help="Optional flow id to filter runs."),
    ] = None,
) -> None:
    """List all runs, or only those for FLOW_ID (most recent first)."""
    list_runs(flow_id)


@app.command("status")
@handle_navbe_errors
def runs_status(
    run_id: Annotated[str, typer.Argument(help="Run id to inspect.")],
) -> None:
    """Show current status for one run."""
    show_run_status(run_id)


@app.command("watch")
@handle_navbe_errors
def runs_watch(
    run_id: Annotated[
        str | None,
        typer.Argument(help="Optional run id; omit to watch all runs."),
    ] = None,
    interval: Annotated[
        float,
        typer.Option("--interval", help="Poll interval in seconds."),
    ] = 1.0,
) -> None:
    """Live status for one run, or all runs until none are active.

    Without RUN_ID, polls every run and redraws a table until no
    pending/running/paused runs remain (or Ctrl+C).

    ponytail: poll-based — upgrade: watch state.json on disk.
    """
    watch_runs(run_id, interval=interval)
