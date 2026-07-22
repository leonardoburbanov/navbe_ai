"""navbe flows — list persisted flows."""

from __future__ import annotations

import click

from navbe.cli.errors import handle_navbe_errors, run_async
from navbe.cli.format import print_flows_table
from navbe.dependencies import get_flow_service


@click.group("flows")
def flows_group() -> None:
    """List persisted flows."""


@flows_group.command("list")
@handle_navbe_errors
def flows_list() -> None:
    """List all flows (from the flows index)."""
    flows = run_async(get_flow_service().list())
    print_flows_table(flows)
