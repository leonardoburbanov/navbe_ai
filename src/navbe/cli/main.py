"""Navbe human CLI — secrets, sync, runs, steps."""

from __future__ import annotations

import click

from navbe.cli.runs import runs_group
from navbe.cli.secret import secret_group
from navbe.cli.serve import serve_cmd
from navbe.cli.steps import steps_group
from navbe.cli.sync import sync_group


@click.group()
@click.version_option(package_name="navbe", prog_name="navbe")
def cli() -> None:
    """Navbe ops console — manage auth, sync flows, watch runs, browse steps.

    Agents use ``navbe-mcp``; humans use this CLI.
    """


cli.add_command(secret_group)
cli.add_command(sync_group)
cli.add_command(runs_group)
cli.add_command(steps_group)
cli.add_command(serve_cmd)


def main() -> None:
    """Console script entrypoint."""
    cli()


if __name__ == "__main__":
    main()
