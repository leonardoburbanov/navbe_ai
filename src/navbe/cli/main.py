"""Navbe human CLI — secrets, sync, runs, steps."""

from __future__ import annotations

import io
import sys

import click
from rich.console import Console

from navbe.cli.info import info_cmd
from navbe.cli.login import login_cmd
from navbe.cli.onboarding import print_banner, print_quick_start
from navbe.cli.runs import runs_group
from navbe.cli.secret import secret_group
from navbe.cli.serve import serve_cmd
from navbe.cli.setup import setup_cmd
from navbe.cli.steps import steps_group
from navbe.cli.sync import sync_group


def _configure_stdio_utf8() -> None:
    """Avoid UnicodeEncodeError on Windows cp1252 terminals (ponytail: reconfigure)."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")


_configure_stdio_utf8()


@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(package_name="navbe", prog_name="navbe")
def cli(ctx: click.Context) -> None:
    """Navbe ops console — manage auth, sync flows, watch runs, browse steps.

    Agents use ``navbe-mcp``; humans use this CLI.

    \b
    Quick start:
      navbe setup              Interactive onboarding (prompts; use --yes to skip)
      navbe info               Paths, credentials readiness, sync state
      navbe login --status     Which API keys are present (never values)
      navbe secret set KEY     Store a credential (hidden prompt)
      navbe sync pull          Import flows/<id>/flow.json from GitHub
      navbe runs watch RUN_ID  Live run status until done
      navbe steps              Available step types
      navbe serve              HTTP API + MCP mount
    """
    if ctx.invoked_subcommand is None:
        print_banner()
        console = Console()
        console.print(
            "[dim]New here? Run [bold cyan]navbe setup[/bold cyan] "
            "for an interactive walkthrough.[/dim]"
        )
        console.print()
        print_quick_start()
        click.echo()
        click.echo("Run navbe setup to begin, or navbe --help for all commands.")


cli.add_command(setup_cmd)
cli.add_command(info_cmd)
cli.add_command(login_cmd)
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
