"""navbe steps — browse available step types."""

from __future__ import annotations

from typing import Annotated

import typer

from navbe.cli.actions import list_steps
from navbe.cli.errors import handle_navbe_errors, run_async
from navbe.cli.format import print_step_schema
from navbe.core.exceptions import NotFoundError
from navbe.dependencies import get_catalog_service

app = typer.Typer(
    help="List available step types (from catalog).",
    invoke_without_command=True,
)


@app.callback(invoke_without_command=True)
@handle_navbe_errors
def steps_root(ctx: typer.Context) -> None:
    """List available step types when no subcommand is given."""
    if ctx.invoked_subcommand is None:
        list_steps()


@app.command("show")
@handle_navbe_errors
def steps_show(
    step_type: Annotated[str, typer.Argument(help="Step type name.")],
) -> None:
    """Show config schema for one step type."""
    catalog = run_async(get_catalog_service().get_steps_catalog())
    entry = catalog.get(step_type)
    if entry is None:
        raise NotFoundError(
            f"Unknown step type '{step_type}'",
            details={"step_type": step_type, "hint": "navbe steps"},
        )
    print_step_schema(step_type, entry)
