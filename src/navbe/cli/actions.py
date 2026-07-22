"""Shared CLI actions used by Click commands and the interactive slash REPL."""

from __future__ import annotations

import time
from pathlib import Path

from rich.live import Live
from rich.text import Text

from navbe.cli.errors import run_async
from navbe.cli.format import (
    build_runs_table,
    console,
    print_flows_table,
    print_run_state,
    print_runs_table,
    print_steps_table,
    print_sync_status,
)
from navbe.cli.info import _gather_info, _print_info
from navbe.cli.onboarding import mcp_config_snippet
from navbe.dependencies import (
    get_catalog_service,
    get_flow_service,
    get_run_service,
    get_secrets_service,
    get_sync_service,
)
from navbe.domains.execution.models import RunState, RunStatus

_TERMINAL = {RunStatus.COMPLETED, RunStatus.FAILED}
_ACTIVE = {RunStatus.PENDING, RunStatus.RUNNING, RunStatus.PAUSED}


def show_info(*, as_json: bool = False) -> None:
    """Print local paths, credentials readiness, and sync state."""
    import json

    import click

    data = run_async(_gather_info())
    if as_json:
        click.echo(json.dumps(data, indent=2))
        return
    _print_info(data)
    repo = data.get("repo_root")
    if repo:
        console.print()
        console.print("[dim]MCP snippet (paste into Claude/Cursor MCP config):[/dim]")
        console.print(mcp_config_snippet(Path(repo)))


def list_flows() -> None:
    """List all persisted flows."""
    flows = run_async(get_flow_service().list())
    print_flows_table(flows)


def list_runs(flow_id: str | None = None) -> None:
    """List all runs, or only those for ``flow_id``."""
    runs = run_async(get_run_service().list_runs(flow_id))
    print_runs_table(runs)


def show_run_status(run_id: str) -> None:
    """Print one-shot status for a run."""
    state = run_async(get_run_service().status(run_id))
    print_run_state(state)


def watch_runs(run_id: str | None = None, *, interval: float = 1.0) -> None:
    """Live-watch one run, or all runs until none are active."""
    if run_id is None:
        _watch_all(interval)
    else:
        _watch_one(run_id, interval)


def list_steps() -> None:
    """List available step types from the catalog."""
    catalog = run_async(get_catalog_service().get_steps_catalog())
    print_steps_table(catalog)


def list_secret_keys() -> None:
    """List credential keys (never values)."""
    keys = run_async(get_secrets_service().list_keys())
    if not keys:
        console.print("[dim]No keys stored.[/dim]")
        return
    for name in keys:
        console.print(name)


def show_sync() -> None:
    """Print sync configuration and branch state."""
    status = run_async(get_sync_service().status())
    print_sync_status(status)


def run_setup(*, yes: bool = False, dry_run: bool = False, skip_sync: bool = False) -> None:
    """Run the interactive setup walkthrough."""
    from navbe.cli.setup import setup_cmd

    args: list[str] = []
    if yes:
        args.append("--yes")
    if dry_run:
        args.append("--dry-run")
    if skip_sync:
        args.append("--skip-sync")
    setup_cmd.main(args, standalone_mode=False)


def serve_hint(*, host: str = "127.0.0.1", port: int = 8000) -> None:
    """Print how to start the HTTP server (does not block the REPL)."""
    console.print(
        f"[dim]Start the API outside this session:[/dim]\n"
        f"  [cyan]navbe serve --host {host} --port {port}[/cyan]\n"
        f"[dim]Serving takes over the terminal; exit the menu first if needed.[/dim]"
    )


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
