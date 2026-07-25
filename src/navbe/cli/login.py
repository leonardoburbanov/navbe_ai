"""navbe login / logout — GitHub Device Flow + credential readiness."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from navbe.cli.errors import handle_navbe_errors, run_async
from navbe.cli.format import console
from navbe.cli.onboarding import RECOMMENDED_KEYS
from navbe.dependencies import get_github_auth_service, get_secrets_service

login_app = typer.Typer(
    help="Connect your GitHub account so Navbe can sync flows to your repo.",
    invoke_without_command=True,
)
logout_app = typer.Typer(help="Clear managed auth sessions.")


async def _secret_rows() -> list[tuple[str, bool]]:
    """Return recommended secret keys and whether each is present."""
    service = get_secrets_service()
    return [(key, await service.has(key)) for key in RECOMMENDED_KEYS]


def _print_github_status(
    *,
    logged_in: bool,
    login: str | None,
    pending: bool,
    app_installed: bool | None = None,
    install_url: str | None = None,
) -> None:
    """Print GitHub App OAuth presence (never the token)."""
    table = Table(title="GitHub connection")
    table.add_column("field")
    table.add_column("value")
    table.add_row("logged_in", "yes" if logged_in else "no")
    table.add_row("login", login or "-")
    table.add_row("pending", "yes" if pending else "no")
    if app_installed is None:
        installed_bit = "-"
    else:
        installed_bit = "yes" if app_installed else "no"
    table.add_row("app_installed", installed_bit)
    console.print(table)


def _print_connect_next_steps(
    *,
    login: str | None,
    app_installed: bool | None,
    install_url: str | None,
) -> None:
    """Explain the GitHub signup / connect flow in plain language."""
    lines: list[str] = [
        "[bold]Connect GitHub to sync your flows[/bold]",
        "",
        "Navbe uses the [cyan]Navbe AI[/cyan] GitHub App so [bold]you[/bold] do not",
        "create an OAuth app. You only authorize once, then pick a repo.",
    ]
    if login:
        lines.append(f"Signed in as [cyan]{login}[/cyan].")
    lines.append("")

    step = 1
    if app_installed is False:
        lines.extend(
            [
                f"[bold]{step}. Install Navbe AI on your GitHub account[/bold]",
                "   This grants Navbe access to create/update the repo that stores",
                "   your flow definitions (not your credentials).",
            ]
        )
        if install_url:
            lines.append(f"   Open: [cyan]{install_url}[/cyan]")
        lines.append("   Choose your user (or org) and allow the repos you want.")
        lines.append("")
        step += 1

    lines.extend(
        [
            f"[bold]{step}. Pick the repo you already granted to Navbe AI[/bold]",
            "   [cyan]navbe sync connect[/cyan]",
            "   (lists granted repos — choose a number; or pass OWNER REPO)",
            "",
            f"[bold]{step + 1}. Sync flows[/bold]",
            "   [cyan]navbe sync push[/cyan]  — upload local flows to GitHub",
            "   [cyan]navbe sync pull[/cyan]  — download flows from GitHub",
            "",
            "[dim]Wrong permissions / no repos?[/dim] [cyan]navbe github reinstall[/cyan]",
        ]
    )

    console.print(Panel("\n".join(lines), border_style="cyan", title="What's next"))


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
            help="Show GitHub connection + secret key presence (never values).",
        ),
    ] = False,
) -> None:
    """Show auth readiness, or use a subcommand (e.g. ``login github``)."""
    if ctx.invoked_subcommand is not None:
        return

    auth = get_github_auth_service()
    gh = run_async(auth.status())
    _print_github_status(
        logged_in=gh.logged_in,
        login=gh.login,
        pending=gh.pending,
        app_installed=gh.app_installed,
        install_url=gh.install_url,
    )
    console.print()
    rows = run_async(_secret_rows())
    _print_secret_readiness(rows)

    if status_only:
        return

    console.print()
    if gh.logged_in:
        _print_connect_next_steps(
            login=gh.login,
            app_installed=gh.app_installed,
            install_url=gh.install_url,
        )
    else:
        console.print("Connect GitHub (authorize Navbe AI — you do not create an app):")
        console.print("  [cyan]navbe login github[/cyan]")
        console.print()
        console.print("Store connector keys locally (hidden prompt, never echoed):")
        console.print("  [cyan]navbe secret set NAVBE_ANTHROPIC_API_KEY[/cyan]")
        console.print()
        console.print("[dim]List keys:[/dim] navbe secret list")


@login_app.command("github")
@handle_navbe_errors
def login_github(
    status_only: Annotated[
        bool,
        typer.Option("--status", help="Show GitHub connection status only."),
    ] = False,
    timeout: Annotated[
        float,
        typer.Option("--timeout", help="Seconds to wait for browser authorization."),
    ] = 300.0,
) -> None:
    """Authorize Navbe AI on GitHub so this machine can sync your flow repo."""
    auth = get_github_auth_service()
    if status_only:
        gh = run_async(auth.status())
        _print_github_status(
            logged_in=gh.logged_in,
            login=gh.login,
            pending=gh.pending,
            app_installed=gh.app_installed,
            install_url=gh.install_url,
        )
        if gh.logged_in:
            console.print()
            _print_connect_next_steps(
                login=gh.login,
                app_installed=gh.app_installed,
                install_url=gh.install_url,
            )
        return

    begin = run_async(auth.begin())
    console.print("[bold]Step 1 — Authorize Navbe AI in your browser[/bold]")
    console.print("  This proves who you are. You are [bold]not[/bold] creating a GitHub App.")
    console.print(f"  Open: [cyan]{begin.verification_uri}[/cyan]")
    console.print(f"  Enter code: [bold yellow]{begin.user_code}[/bold yellow]")
    console.print(f"  [dim]Expires in {begin.expires_in}s — waiting for authorization…[/dim]")
    gh = run_async(auth.complete(timeout=timeout))
    console.print()
    console.print(f"[green]Authorized as {gh.login or 'GitHub user'}.[/green]")
    _print_github_status(
        logged_in=gh.logged_in,
        login=gh.login,
        pending=gh.pending,
        app_installed=gh.app_installed,
        install_url=gh.install_url,
    )
    console.print()
    _print_connect_next_steps(
        login=gh.login,
        app_installed=gh.app_installed,
        install_url=gh.install_url,
    )


@logout_app.command("github")
@handle_navbe_errors
def logout_github() -> None:
    """Clear the managed GitHub connection on this machine."""
    auth = get_github_auth_service()
    gh = run_async(auth.logout())
    console.print("[green]Disconnected GitHub on this machine.[/green]")
    _print_github_status(
        logged_in=gh.logged_in,
        login=gh.login,
        pending=gh.pending,
        app_installed=gh.app_installed,
        install_url=gh.install_url,
    )
