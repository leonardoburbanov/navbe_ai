"""Shared CLI actions used by Click commands and the interactive slash REPL."""

from __future__ import annotations

import time

from rich.live import Live
from rich.text import Text

from navbe.cli.errors import run_async
from navbe.cli.format import (
    build_runs_table,
    console,
    print_flows_table,
    print_run_diagram,
    print_run_state,
    print_run_steps,
    print_runs_table,
    print_schedule,
    print_schedules_table,
    print_steps_table,
    print_sync_status,
)
from navbe.cli.info import _gather_info, _print_info
from navbe.cli.mcp_config import mcp_config_snippet
from navbe.dependencies import (
    get_catalog_service,
    get_flow_service,
    get_run_service,
    get_schedule_service,
    get_secrets_service,
    get_sync_service,
)
from navbe.domains.execution.models import RunState, RunStatus

_TERMINAL = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}
_ACTIVE = {RunStatus.PENDING, RunStatus.RUNNING, RunStatus.PAUSED}


def show_info(*, as_json: bool = False) -> None:
    """Print local paths, credentials readiness, and sync state."""
    import json

    import typer

    data = run_async(_gather_info())
    if as_json:
        typer.echo(json.dumps(data, indent=2))
        return
    _print_info(data)
    console.print()
    console.print("[dim]MCP snippet (paste into Claude/Cursor MCP config):[/dim]")
    console.print(mcp_config_snippet())


def list_flows() -> None:
    """List all persisted flows."""
    flows = run_async(get_flow_service().list())
    print_flows_table(flows)


def list_runs(flow_id: str | None = None) -> None:
    """List all runs, or only those for ``flow_id``."""
    runs = run_async(get_run_service().list_runs(flow_id))
    print_runs_table(runs)


def show_run_status(run_id: str, *, diagram: bool = False) -> None:
    """Print status and executed steps for a run."""
    detail = run_async(get_run_service().detail(run_id))
    print_run_state(detail.state)
    console.print()
    print_run_steps(detail.steps)
    if diagram:
        print_run_diagram(detail.diagram)


def cancel_run(run_id: str) -> None:
    """Cancel an active run and print the resulting state."""
    state = run_async(get_run_service().cancel(run_id))
    print_run_state(state)


def list_schedules() -> None:
    """List all schedules."""
    items = run_async(get_schedule_service().list())
    print_schedules_table(items)


def show_schedule(schedule_id: str) -> None:
    """Print one schedule document."""
    schedule = run_async(get_schedule_service().get(schedule_id))
    print_schedule(schedule)


def enable_schedule(schedule_id: str) -> None:
    """Enable a schedule."""
    schedule = run_async(get_schedule_service().enable(schedule_id))
    print_schedule(schedule)


def disable_schedule(schedule_id: str) -> None:
    """Disable a schedule."""
    schedule = run_async(get_schedule_service().disable(schedule_id))
    print_schedule(schedule)


def list_schedule_runs(schedule_id: str | None = None) -> None:
    """List schedule-triggered runs."""
    runs = run_async(get_run_service().list_schedule_runs(schedule_id))
    print_runs_table(runs)


def create_schedule(payload: dict) -> None:
    """Create a schedule from a dict payload."""
    metadata = run_async(get_schedule_service().create(payload))
    console.print(
        f"[green]Created[/green] schedule [bold]{metadata.schedule_id}[/bold] "
        f"(next {metadata.next_run_at})"
    )


def update_schedule(
    schedule_id: str,
    *,
    when: str | None = None,
    flow_id: str | None = None,
    name: str | None = None,
) -> None:
    """Patch when/flow/name on an existing schedule."""
    prior = run_async(get_schedule_service().get(schedule_id))
    payload = prior.model_dump(mode="json", by_alias=True)
    if when is not None:
        payload["when"] = when
    if flow_id is not None:
        payload["flow_id"] = flow_id
    if name is not None:
        payload["name"] = name
    metadata = run_async(get_schedule_service().update(payload))
    console.print(
        f"[cyan]Updated[/cyan] schedule [bold]{metadata.schedule_id}[/bold] "
        f"(next {metadata.next_run_at})"
    )


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
    """List credentials with masked hints (never values)."""
    from rich.table import Table

    items = run_async(get_secrets_service().list_credentials())
    if not items:
        console.print("[dim]No keys stored.[/dim]")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("key")
    table.add_column("app")
    table.add_column("hint")
    table.add_column("source")
    for item in items:
        table.add_row(
            item.key,
            item.app or "-",
            item.hint or "-",
            item.source,
        )
    console.print(table)


def show_sync() -> None:
    """Print sync configuration and branch state."""
    status = run_async(get_sync_service().status())
    print_sync_status(status)


def run_setup(*, yes: bool = False, dry_run: bool = False, skip_sync: bool = False) -> None:
    """Run the interactive setup walkthrough."""
    from navbe.cli.setup import setup_cmd

    setup_cmd(dry_run=dry_run, yes=yes, skip_sync=skip_sync)


def serve_hint(*, host: str = "127.0.0.1", port: int = 8000) -> None:
    """Print how to start the HTTP server (does not block the REPL)."""
    console.print(
        f"[dim]Start the daemon outside this session:[/dim]\n"
        f"  [cyan]navbe serve --detach --host {host} --port {port}[/cyan]\n"
        f"  [cyan]navbe status[/cyan]   [cyan]navbe stop[/cyan]\n"
        f"[dim]Or foreground: navbe serve --host {host} --port {port}[/dim]"
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
