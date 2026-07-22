"""navbe flows — list persisted flows."""

from __future__ import annotations

import typer

from navbe.cli.actions import list_flows
from navbe.cli.errors import handle_navbe_errors

app = typer.Typer(help="List persisted flows.")


@app.command("list")
@handle_navbe_errors
def flows_list() -> None:
    """List all flows (from the flows index)."""
    list_flows()
