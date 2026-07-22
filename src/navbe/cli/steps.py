"""navbe steps — browse available step types."""

from __future__ import annotations

import click

from navbe.cli.errors import handle_navbe_errors, run_async
from navbe.cli.format import print_step_schema
from navbe.core.exceptions import NotFoundError
from navbe.dependencies import get_catalog_service


@click.group("steps", invoke_without_command=True)
@click.pass_context
@handle_navbe_errors
def steps_group(ctx: click.Context) -> None:
    """List available step types (from catalog)."""
    if ctx.invoked_subcommand is None:
        from navbe.cli.actions import list_steps

        list_steps()


@steps_group.command("show")
@click.argument("step_type")
@handle_navbe_errors
def steps_show(step_type: str) -> None:
    """Show config schema for one step type."""
    catalog = run_async(get_catalog_service().get_steps_catalog())
    entry = catalog.get(step_type)
    if entry is None:
        raise NotFoundError(
            f"Unknown step type '{step_type}'",
            details={"step_type": step_type, "hint": "navbe steps"},
        )
    print_step_schema(step_type, entry)
