"""navbe schedules — manage time-based flow schedules."""

from __future__ import annotations

from typing import Annotated

import typer

from navbe.cli.actions import (
    disable_schedule,
    enable_schedule,
    list_schedule_runs,
    list_schedules,
    show_schedule,
)
from navbe.cli.errors import handle_navbe_errors

app = typer.Typer(help="Manage flow schedules (fires while navbe serve is up).")


@app.command("list")
@handle_navbe_errors
def schedules_list() -> None:
    """List all schedules."""
    list_schedules()


@app.command("get")
@handle_navbe_errors
def schedules_get(
    schedule_id: Annotated[str, typer.Argument(help="Schedule id.")],
) -> None:
    """Show one schedule document."""
    show_schedule(schedule_id)


@app.command("enable")
@handle_navbe_errors
def schedules_enable(
    schedule_id: Annotated[str, typer.Argument(help="Schedule id.")],
) -> None:
    """Enable a schedule and refresh next_run_at."""
    enable_schedule(schedule_id)


@app.command("disable")
@handle_navbe_errors
def schedules_disable(
    schedule_id: Annotated[str, typer.Argument(help="Schedule id.")],
) -> None:
    """Disable a schedule so it no longer fires."""
    disable_schedule(schedule_id)


@app.command("runs")
@handle_navbe_errors
def schedules_runs(
    schedule_id: Annotated[
        str | None,
        typer.Argument(help="Optional schedule id to filter runs."),
    ] = None,
) -> None:
    """List runs triggered by schedules."""
    list_schedule_runs(schedule_id)


@app.command("create")
@handle_navbe_errors
def schedules_create(
    schedule_id: Annotated[str, typer.Option("--id", help="Schedule id.")],
    flow_id: Annotated[str, typer.Option("--flow", help="Flow id to run.")],
    when: Annotated[
        str,
        typer.Option("--when", help="Relative (+30s/+1h) or 5-field cron."),
    ],
    name: Annotated[str, typer.Option("--name", help="Optional display name.")] = "",
) -> None:
    """Create a schedule (JSON notify config via MCP/REST if needed)."""
    from navbe.cli.actions import create_schedule

    create_schedule(
        {
            "schedule_id": schedule_id,
            "flow_id": flow_id,
            "when": when,
            "name": name,
            "enabled": True,
        }
    )


@app.command("update")
@handle_navbe_errors
def schedules_update(
    schedule_id: Annotated[str, typer.Argument(help="Schedule id.")],
    when: Annotated[
        str | None,
        typer.Option("--when", help="New when expression."),
    ] = None,
    flow_id: Annotated[
        str | None,
        typer.Option("--flow", help="New flow id."),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", help="New display name."),
    ] = None,
) -> None:
    """Update when / flow / name on an existing schedule."""
    from navbe.cli.actions import update_schedule

    update_schedule(schedule_id, when=when, flow_id=flow_id, name=name)
