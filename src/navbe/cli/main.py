"""Navbe human CLI — secrets, sync, runs, steps (Typer)."""

from __future__ import annotations

import io
import sys
from typing import Annotated

import typer
from rich.console import Console

from navbe import __version__
from navbe.cli import flows, mcp, runs, secret, steps, sync
from navbe.cli.info import info_cmd
from navbe.cli.interactive import run_session, should_start_interactive
from navbe.cli.login import login_app, logout_app
from navbe.cli.onboarding import print_banner, print_quick_start
from navbe.cli.serve import serve_cmd
from navbe.cli.setup import setup_cmd

app = typer.Typer(
    name="navbe",
    help=(
        "Navbe ops console — manage auth, sync flows, watch runs, browse steps. "
        "Bare navbe opens the interactive slash menu on a TTY."
    ),
    no_args_is_help=False,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Subcommand groups
app.add_typer(secret.app, name="secret")
app.add_typer(sync.app, name="sync")
app.add_typer(flows.app, name="flows")
app.add_typer(runs.app, name="runs")
app.add_typer(steps.app, name="steps")
app.add_typer(mcp.app, name="mcp")
app.add_typer(login_app, name="login")
app.add_typer(logout_app, name="logout")

# Top-level commands
app.command("setup")(setup_cmd)
app.command("info")(info_cmd)
app.command("serve")(serve_cmd)

# Alias for tests that historically imported ``cli``
cli = app


def _version_callback(value: bool) -> None:
    """Print version and exit when ``--version`` is passed."""
    if value:
        typer.echo(f"navbe {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = None,
) -> None:
    """Agents use ``navbe-mcp``; humans use this CLI.

    Bare ``navbe`` opens the interactive slash menu on a TTY.
    """
    if ctx.invoked_subcommand is not None:
        return
    if should_start_interactive():
        run_session()
        return
    print_banner()
    console = Console()
    console.print(
        "[dim]New here? Run [bold cyan]navbe setup[/bold cyan] "
        "for an interactive walkthrough.[/dim]"
    )
    console.print()
    print_quick_start()
    typer.echo()
    typer.echo("Run navbe setup to begin, or navbe --help for all commands.")


def _configure_stdio_utf8() -> None:
    """Avoid UnicodeEncodeError on Windows cp1252 terminals (ponytail: reconfigure)."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    """Console script entrypoint."""
    _configure_stdio_utf8()
    app()


if __name__ == "__main__":
    main()
