"""navbe github — install / uninstall / reinstall the Navbe AI GitHub App."""

from __future__ import annotations

import typer
from rich.panel import Panel

from navbe.cli.errors import handle_navbe_errors, run_async
from navbe.cli.format import console
from navbe.cli.login import _print_connect_next_steps, _print_github_status, login_github
from navbe.dependencies import get_github_auth_service

app = typer.Typer(
    help=(
        "Manage the Navbe AI GitHub App connection "
        "(install, uninstall, reinstall, status)."
    ),
)


@app.command("status")
@handle_navbe_errors
def github_status() -> None:
    """Show whether you are authorized and whether Navbe AI is installed."""
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
    if gh.logged_in:
        _print_connect_next_steps(
            login=gh.login,
            app_installed=gh.app_installed,
            install_url=gh.install_url,
        )
        if gh.configure_url or gh.uninstall_url:
            console.print()
            console.print("[dim]Manage installation on GitHub:[/dim]")
            if gh.configure_url:
                console.print(f"  Configure / uninstall: [cyan]{gh.configure_url}[/cyan]")
            elif gh.uninstall_url:
                console.print(f"  Installed apps: [cyan]{gh.uninstall_url}[/cyan]")
    else:
        console.print("Not connected. Run: [cyan]navbe login github[/cyan]")


@app.command("install")
@handle_navbe_errors
def github_install() -> None:
    """Show how to install Navbe AI on your GitHub account (browser)."""
    auth = get_github_auth_service()
    gh = run_async(auth.status())
    install_url = gh.install_url or auth.install_url

    lines = [
        "[bold]Install Navbe AI on GitHub[/bold]",
        "",
        "This lets Navbe create/update the repo that stores your flows.",
        "You do [bold]not[/bold] create a GitHub App — you only install ours.",
        "",
        f"1. Open: [cyan]{install_url}[/cyan]",
        "2. Choose your user or organization",
        "3. Grant repository access (All, or only the sync repo)",
        "4. Confirm permissions include Contents + Administration",
        "",
    ]
    if not gh.logged_in:
        lines.extend(
            [
                "Then authorize this machine:",
                "  [cyan]navbe login github[/cyan]",
            ]
        )
    else:
        lines.extend(
            [
                "Then bind your workspace repo:",
                "  [cyan]navbe sync connect[/cyan]",
            ]
        )

    console.print(Panel("\n".join(lines), border_style="cyan", title="Install"))
    _print_github_status(
        logged_in=gh.logged_in,
        login=gh.login,
        pending=gh.pending,
        app_installed=gh.app_installed,
        install_url=install_url,
    )


@app.command("uninstall")
@handle_navbe_errors
def github_uninstall(
    keep_login: bool = typer.Option(
        False,
        "--keep-login",
        help="Do not clear the local GitHub token (only show uninstall URL).",
    ),
) -> None:
    """Uninstall Navbe AI from GitHub and disconnect this machine."""
    auth = get_github_auth_service()
    gh = run_async(auth.status())
    uninstall_url = gh.uninstall_url or auth.installations_list_url

    lines = [
        "[bold]Uninstall Navbe AI[/bold]",
        "",
        "1. Open GitHub and remove the app installation:",
        f"   [cyan]{uninstall_url}[/cyan]",
        "   Click [bold]Navbe AI[/bold] → [bold]Uninstall[/bold]",
        "",
    ]
    if keep_login:
        lines.append("Local login token was kept (--keep-login).")
    else:
        lines.append("2. This machine will forget the local GitHub login token.")

    console.print(Panel("\n".join(lines), border_style="yellow", title="Uninstall"))

    if not keep_login:
        gh = run_async(auth.logout())
        console.print("[green]Local GitHub login cleared.[/green]")
    else:
        gh = run_async(auth.status())

    _print_github_status(
        logged_in=gh.logged_in,
        login=gh.login,
        pending=gh.pending,
        app_installed=gh.app_installed,
        install_url=gh.install_url,
    )
    console.print()
    console.print("To connect again later: [cyan]navbe github reinstall[/cyan]")


@app.command("reinstall")
@handle_navbe_errors
def github_reinstall(
    skip_login: bool = typer.Option(
        False,
        "--skip-login",
        help="Only print install URLs; do not start device login.",
    ),
) -> None:
    """Uninstall guidance, then install + login again (fix permissions / repos)."""
    auth = get_github_auth_service()
    gh = run_async(auth.status())
    uninstall_url = gh.uninstall_url or auth.installations_list_url
    install_url = auth.install_url

    lines = [
        "[bold]Reinstall Navbe AI[/bold]",
        "",
        "Use this when permissions or repo access look wrong",
        '(e.g. GitHub shows "No permissions" / "No repositories").',
        "",
        "[bold]1. Uninstall the current installation[/bold]",
        f"   [cyan]{uninstall_url}[/cyan]",
        "   → Navbe AI → Uninstall",
        "",
        "[bold]2. Install again with the right access[/bold]",
        f"   [cyan]{install_url}[/cyan]",
        "   Grant Contents + Administration, and pick your sync repos",
        "",
        "[bold]3. Authorize this machine[/bold]",
        "   [cyan]navbe login github[/cyan]",
        "",
        "[bold]4. Pick your flow repo[/bold]",
        "   [cyan]navbe sync connect[/cyan]",
    ]
    console.print(Panel("\n".join(lines), border_style="cyan", title="Reinstall"))

    # Clear stale local token so the next login is clean.
    run_async(auth.logout())
    console.print("[green]Local GitHub login cleared for a clean reconnect.[/green]")
    console.print()

    if skip_login:
        console.print("After installing in the browser, run: [cyan]navbe login github[/cyan]")
        return

    console.print("Starting login now (finish install in the browser first if needed)…")
    console.print()
    login_github(status_only=False, timeout=300.0)
