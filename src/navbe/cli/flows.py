"""navbe flows — list persisted flows."""

from __future__ import annotations

import click

from navbe.cli.actions import list_flows
from navbe.cli.errors import handle_navbe_errors


@click.group("flows")
def flows_group() -> None:
    """List persisted flows."""


@flows_group.command("list")
@handle_navbe_errors
def flows_list() -> None:
    """List all flows (from the flows index)."""
    list_flows()
