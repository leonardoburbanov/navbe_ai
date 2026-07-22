"""Rich formatters for CLI output."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rich.console import Console
from rich.table import Table

from navbe.domains.execution.models import RunState, RunStatus
from navbe.domains.flows.models import FlowMetadata
from navbe.domains.sync.models import SyncResult, SyncStatus

console = Console()

_STATUS_STYLE = {
    RunStatus.PENDING: "dim",
    RunStatus.RUNNING: "cyan",
    RunStatus.PAUSED: "yellow",
    RunStatus.COMPLETED: "green",
    RunStatus.FAILED: "red",
}


def _fmt_dt(value: datetime | None) -> str:
    """Format a datetime for tables."""
    if value is None:
        return "-"
    return value.isoformat(timespec="seconds")


def print_run_state(state: RunState) -> None:
    """Print a single run status block."""
    style = _STATUS_STYLE.get(state.status, "")
    console.print(f"[bold]run_id[/bold]  {state.run_id}")
    console.print(f"[bold]flow_id[/bold] {state.flow_id}")
    console.print(f"[bold]status[/bold]  [{style}]{state.status}[/{style}]")
    if state.current_node:
        console.print(f"[bold]node[/bold]    {state.current_node}")
    if state.error:
        console.print(f"[bold red]error[/bold red]   {state.error}")
    console.print(f"[bold]updated[/bold] {_fmt_dt(state.updated_at)}")


def print_flows_table(flows: list[FlowMetadata]) -> None:
    """Print persisted flows as a table."""
    table = Table(title="Flows")
    table.add_column("flow_id", overflow="fold")
    table.add_column("name", overflow="fold")
    table.add_column("version")
    table.add_column("updated_at")
    for flow in flows:
        table.add_row(
            flow.flow_id,
            flow.name,
            str(flow.version),
            _fmt_dt(flow.updated_at),
        )
    if not flows:
        console.print("[dim]No flows found.[/dim]")
    else:
        console.print(table)


def build_runs_table(runs: list[RunState], *, title: str = "Run history") -> Table:
    """Build a Rich table of runs (for print or Live)."""
    table = Table(title=title)
    table.add_column("run_id", overflow="fold")
    table.add_column("flow_id", overflow="fold")
    table.add_column("status")
    table.add_column("current_node")
    table.add_column("updated_at")
    table.add_column("error", overflow="fold")
    for run in runs:
        style = _STATUS_STYLE.get(run.status, "")
        table.add_row(
            run.run_id,
            run.flow_id,
            f"[{style}]{run.status}[/{style}]",
            run.current_node or "-",
            _fmt_dt(run.updated_at),
            run.error or "-",
        )
    return table


def print_runs_table(runs: list[RunState]) -> None:
    """Print run history as a table."""
    if not runs:
        console.print("[dim]No runs found.[/dim]")
        return
    console.print(build_runs_table(runs))


def print_sync_status(status: SyncStatus) -> None:
    """Print sync configuration and branch state."""
    table = Table(title="Sync status")
    table.add_column("field")
    table.add_column("value")
    table.add_row("configured", str(status.configured))
    table.add_row("initialized", str(status.initialized))
    table.add_row("remote_url", status.remote_url or "-")
    table.add_row("branch", status.branch or "-")
    table.add_row("dirty", str(status.dirty))
    table.add_row("flows_subdir", status.flows_subdir)
    table.add_row("local_flows", str(status.local_flow_count))
    table.add_row("remote_flows", str(status.remote_flow_count))
    console.print(table)


def print_sync_result(result: SyncResult) -> None:
    """Print push/pull outcome."""
    console.print(f"[bold]branch[/bold]  {result.branch}")
    console.print(f"[bold]commit[/bold]  {result.commit_sha or '-'}")
    console.print(f"[bold]message[/bold] {result.message}")
    if result.flows_added:
        console.print(f"[green]added[/green]   {', '.join(result.flows_added)}")
    if result.flows_updated:
        console.print(f"[cyan]updated[/cyan] {', '.join(result.flows_updated)}")
    if result.flows_removed:
        console.print(f"[red]removed[/red] {', '.join(result.flows_removed)}")


def print_steps_table(catalog: dict[str, dict[str, Any]]) -> None:
    """Print available step types."""
    table = Table(title="Available steps")
    table.add_column("step_type")
    table.add_column("description", overflow="fold")
    for step_type in sorted(catalog):
        schema = catalog[step_type].get("config_schema") or {}
        desc = schema.get("description") or schema.get("title") or "-"
        table.add_row(step_type, str(desc))
    console.print(table)


def print_step_schema(step_type: str, entry: dict[str, Any]) -> None:
    """Print one step type schema summary."""
    import json

    schema = entry.get("config_schema") or {}
    console.print(f"[bold]{step_type}[/bold]")
    if schema.get("description"):
        console.print(schema["description"])
    console.print(json.dumps(schema, indent=2))
