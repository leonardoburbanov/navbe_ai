"""navbe login / logout — GitHub Device Flow + credential readiness."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.table import Table

from navbe.cli.errors import handle_navbe_errors, run_async
from navbe.cli.format import console
from navbe.cli.onboarding import RECOMMENDED_KEYS
from navbe.dependencies import get_github_auth_service, get_secrets_service

login_app = typer.Typer(
    help="GitHub OAuth login (device flow) and local credential readiness.",
    invoke_without_command=True,
)
logout_app = typer.Typer(help="Clear managed auth sessions.")


async def _secret_rows() -> list[tuple[str, bool]]:
    """Return recommended secret keys and whether each is present."""
    service = get_secrets_service()
    return [(key, await service.has(key)) for key in RECOMMENDED_KEYS]


def _print_github_status(*, logged_in: bool, login: str | None, pending: bool) -> None:
    """Print GitHub OAuth presence (never the token)."""
    table = Table(title="GitHub OAuth")
    table.add_column("field")
    table.add_column("value")
    table.add_row("logged_in", "yes" if logged_in else "no")
    table.add_row("login", login or "-")
    table.add_row("pending", "yes" if pending else "no")
    console.print(table)


def _print_secret_readiness(rows: list[tuple[str, bool]]) -> None:
    """Print recommended connector secret keys (presence only)."""
    table = Table(title="Local secrets (connectors)")
    table.add_column("key")
    table.add_column("present")
    for key, present in rows:
        style = "green" if present else "dim"
        table.add_row(key, f"[{style}]{'yes' if present else 'no'}[/{style}]")
    console.print(table)


@login_app.callback(invoke_without_command=True)
@handle_navbe_errors
def login_cmd(
    ctx: typer.Context,
    status_only: Annotated[
        bool,
        typer.Option(
            "--status",
            help="Show GitHub OAuth + secret key presence (never values).",
        ),
    ] = False,
) -> None:
    """Show auth readiness, or use a subcommand (e.g. ``login github``)."""
    if ctx.invoked_subcommand is not None:
        return

    auth = get_github_auth_service()
    gh = run_async(auth.status())
    _print_github_status(logged_in=gh.logged_in, login=gh.login, pending=gh.pending)
    console.print()
    rows = run_async(_secret_rows())
    _print_secret_readiness(rows)

    if status_only:
        return

    console.print()
    if not gh.logged_in:
        console.print("GitHub sync auth:")
        console.print("  [cyan]navbe login github[/cyan]")
    console.print("Store connector keys locally (hidden prompt, never echoed):")
    console.print("  [cyan]navbe secret set NAVBE_ANTHROPIC_API_KEY[/cyan]")
    console.print()
    console.print("[dim]List keys:[/dim] navbe secret list")


@login_app.command("github")
@handle_navbe_errors
def login_github(
    status_only: Annotated[
        bool,
        typer.Option("--status", help="Show GitHub OAuth status only."),
    ] = False,
    timeout: Annotated[
        float,
        typer.Option("--timeout", help="Seconds to wait for browser authorization."),
    ] = 300.0,
) -> None:
    """Log in to GitHub via Device Flow (stores a managed token for sync)."""
    auth = get_github_auth_service()
    if status_only:
        gh = run_async(auth.status())
        _print_github_status(logged_in=gh.logged_in, login=gh.login, pending=gh.pending)
        return

    begin = run_async(auth.begin())
    console.print("[bold]GitHub device login[/bold]")
    console.print(f"  Open: [cyan]{begin.verification_uri}[/cyan]")
    console.print(f"  Enter code: [bold yellow]{begin.user_code}[/bold yellow]")
    console.print(f"  [dim]Expires in {begin.expires_in}s — waiting for authorization…[/dim]")
    gh = run_async(auth.complete(timeout=timeout))
    console.print()
    console.print("[green]Logged in.[/green]")
    _print_github_status(logged_in=gh.logged_in, login=gh.login, pending=gh.pending)
    console.print()
    console.print("Next: [cyan]navbe sync connect OWNER REPO[/cyan]")


@logout_app.command("github")
@handle_navbe_errors
def logout_github() -> None:
    """Clear the managed GitHub OAuth token."""
    auth = get_github_auth_service()
    gh = run_async(auth.logout())
    console.print("[green]Logged out of GitHub.[/green]")
    _print_github_status(logged_in=gh.logged_in, login=gh.login, pending=gh.pending)
