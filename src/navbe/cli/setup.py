"""navbe setup — interactive first-run onboarding."""

from __future__ import annotations

import getpass
import shutil
import subprocess
import sys
from typing import Annotated, cast

import typer
from rich.console import Console
from rich.panel import Panel

from navbe import __version__
from navbe.cli.errors import handle_navbe_errors, run_async
from navbe.cli.mcp_config import ClientName, configure_clients
from navbe.cli.onboarding import (
    DOCS_CONNECT,
    RECOMMENDED_KEYS,
    ensure_data_dirs,
    find_repo_root,
    mcp_config_snippet,
    print_banner,
    python_version_ok,
    section,
)
from navbe.cli.prompts import choice, confirm, mcp_process_count, pause
from navbe.core.config import get_settings
from navbe.dependencies import get_secrets_service, get_sync_service

console = Console()


def _run_uv_sync() -> tuple[bool, str]:
    """Run ``uv sync`` when uv is available."""
    if shutil.which("uv") is None:
        return False, "uv not on PATH - install from https://docs.astral.sh/uv/"
    proc = subprocess.run(["uv", "sync"], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:500]
        if "navbe-mcp" in err and (
            "being used" in err or "utilizado" in err or "error 32" in err
        ):
            return (
                False,
                "navbe-mcp.exe is locked. Stop MCP (Ctrl+C / Claude restart), then retry.",
            )
        return False, f"uv sync failed: {err}"
    return True, "dependencies synced"


async def _interactive_secrets(interactive: bool) -> None:
    """Optionally store recommended keys via hidden prompts."""
    service = get_secrets_service()
    keys = await service.list_keys()
    if not interactive:
        if keys:
            console.print(f" [green]ok[/green] {len(keys)} key(s) already stored")
        else:
            console.print(" [dim]Skipped - run: navbe secret set KEY[/dim]")
        return
    if keys:
        console.print(f" [green]ok[/green] {len(keys)} key(s) already stored")
        if not confirm(interactive, "Add another credential now?", default=False):
            return
    else:
        if not confirm(interactive, "Store a credential now?", default=True):
            console.print(" [dim]Skip for now - use: navbe secret set KEY[/dim]")
            return

    key = choice(
        interactive,
        "Key name",
        list(RECOMMENDED_KEYS),
        default="NAVBE_ANTHROPIC_API_KEY",
    )
    value = getpass.getpass(f"Value for {key} (hidden): ")
    if not value.strip():
        console.print("[yellow]Empty value - skipped.[/yellow]")
        return
    await service.set(key, value)
    console.print(f" [green]ok[/green] Stored {key} (value not shown)")


async def _interactive_sync(interactive: bool) -> None:
    """Optionally configure GitHub workspace sync (after Device Flow login)."""
    if not interactive:
        console.print(
            " [dim]Skipped - run: navbe login github && navbe sync connect[/dim]"
        )
        return
    if not confirm(interactive, "Configure GitHub workspace sync?", default=False):
        return
    if confirm(interactive, "Log in to GitHub now (device flow)?", default=True):
        from navbe.dependencies import get_github_auth_service

        auth = get_github_auth_service()
        begin = await auth.begin()
        console.print(f" Open [cyan]{begin.verification_uri}[/cyan]")
        console.print(f" Enter code: [bold yellow]{begin.user_code}[/bold yellow]")
        with console.status("[bold cyan]Waiting for GitHub authorization..."):
            await auth.complete(timeout=300.0)
        console.print(" [green]ok[/green] GitHub login stored")
    if confirm(interactive, "Create or bind a repo with sync connect?", default=True):
        from navbe.cli.repo_pick import pick_accessible_repo
        from navbe.dependencies import get_github_auth_service

        auth = get_github_auth_service()
        repos = await auth.list_accessible_repos()
        gh = await auth.status()
        owner, name, private = pick_accessible_repo(repos, default_login=gh.login)
        with console.status("[bold cyan]Connecting sync repo..."):
            status = await get_sync_service().connect(
                owner=owner,
                name=name,
                private=private,
            )
        console.print(
            f" [green]ok[/green] remote={status.remote_url or '-'} "
            f"initialized={status.initialized}"
        )
        return
    remote = typer.prompt(
        "GitHub remote URL",
        default="https://github.com/org/navbe-workspace.git",
    )
    if not remote.strip():
        console.print("[yellow]Empty URL - skipped.[/yellow]")
        return
    config = await get_sync_service().configure(remote_url=remote.strip())
    console.print(f" [green]ok[/green] Saved remote={config.remote_url}")
    if confirm(interactive, "Run sync init (clone/bind repo)?", default=False):
        with console.status("[bold cyan]Initializing sync clone..."):
            status = await get_sync_service().init()
        console.print(
            f" [green]ok[/green] branch={status.branch or '-'} "
            f"initialized={status.initialized}"
        )


@handle_navbe_errors
def setup_cmd(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview steps without making changes."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Non-interactive: accept defaults, no prompts."),
    ] = False,
    skip_sync: Annotated[
        bool,
        typer.Option("--skip-sync", help="Skip uv sync step."),
    ] = False,
) -> None:
    """Interactive onboarding: deps, credentials, sync, agent connection.

    Walks through each step with prompts. Use ``--yes`` for scripts/CI.
    """
    interactive = not yes and not dry_run
    print_banner()
    console.print(f"[dim]Navbe v{__version__}[/dim]")
    if dry_run:
        console.print("[yellow]Dry run - no changes will be made.[/yellow]")
    elif interactive:
        console.print(
            "[dim]Interactive setup - answer prompts below. "
            "Use --yes to skip prompts.[/dim]"
        )
    console.print()

    step = 1
    repo = find_repo_root()

    # 1. Environment
    section("Environment", step)
    step += 1
    if not python_version_ok():
        console.print(" [red]X[/red] Python 3.12+ required - fix this before continuing.")
        raise SystemExit(1)
    console.print(
        f" [green]ok[/green] Python {sys.version_info.major}.{sys.version_info.minor}"
    )
    if repo:
        console.print(f" [green]ok[/green] Repo root: {repo}")
    else:
        console.print(" [yellow]![/yellow] Not inside a navbe checkout")
    pause(interactive, "Press Enter when ready for dependencies...")

    # 2. Dependencies
    section("Dependencies", step)
    step += 1
    running = mcp_process_count()
    if running:
        console.print(
            f" [yellow]![/yellow] {running} navbe-mcp process(es) running - "
            "stop them before uv sync (Claude/Cursor MCP or terminal Ctrl+C)."
        )
    if skip_sync:
        console.print(" [dim]Skipped (--skip-sync)[/dim]")
    elif repo is None:
        console.print(
            " [green]ok[/green] Tool-installed mode "
            "(no checkout) - skip uv sync"
        )
    elif dry_run:
        console.print(" [cyan]->[/cyan] would run: uv sync")
    elif confirm(interactive, "Run uv sync now?", default=running == 0):
        with console.status("[bold cyan]Running uv sync..."):
            ok, msg = _run_uv_sync()
        icon = "[green]ok[/green]" if ok else "[yellow]![/yellow]"
        console.print(f" {icon} {msg}")
        if not ok and interactive:
            console.print(" [dim]Tip: navbe setup --skip-sync to continue other steps[/dim]")
    else:
        console.print(" [dim]Skipped uv sync[/dim]")
    pause(interactive)

    # 3. Local data
    section("Local data", step)
    step += 1
    settings = get_settings()
    need_dirs = not settings.flows_dir.exists() or not settings.db_path.parent.exists()
    if dry_run:
        console.print(
            f" [cyan]->[/cyan] would ensure {settings.flows_dir} "
            f"and {settings.db_path.parent}"
        )
    elif need_dirs and confirm(interactive, "Create local data directories?", default=True):
        for action in ensure_data_dirs(settings.flows_dir, settings.db_path):
            console.print(f" [green]ok[/green] {action}")
    elif need_dirs:
        console.print(" [dim]Skipped directory creation[/dim]")
    else:
        console.print(" [green]ok[/green] Data directories present")
    pause(interactive)

    # 4. Credentials
    section("Credentials", step)
    step += 1
    console.print(" [dim]Values are never shown or logged.[/dim]")
    if dry_run:
        console.print(" [cyan]->[/cyan] would prompt for navbe secret set")
    else:
        run_async(_interactive_secrets(interactive))
    console.print(f" [dim]Recommended:[/dim] {', '.join(RECOMMENDED_KEYS)}")
    pause(interactive)

    # 5. GitHub sync (optional)
    section("GitHub sync (optional)", step)
    step += 1
    console.print(" [dim]Syncs only flows/<id>/flow.json - not runs or credentials.[/dim]")
    if dry_run:
        console.print(" [cyan]->[/cyan] would optionally configure sync remote")
    else:
        run_async(_interactive_sync(interactive))
    pause(interactive)

    # 6. Agent connection
    section("Connect your coding agent", step)
    step += 1
    console.print(" Agents use [bold]navbe-mcp[/bold] over stdio (not this CLI).")
    console.print(
        Panel(
            mcp_config_snippet(),
            title="MCP config (Claude Desktop / Cursor)",
            border_style="cyan",
        )
    )
    plugin_zip = repo / "claude-plugin" / "navbe-plugin.zip" if repo else None
    if plugin_zip and plugin_zip.is_file():
        console.print(f" [bold]Claude plugin:[/bold] upload {plugin_zip}")

    if dry_run:
        console.print(" [cyan]->[/cyan] would run: navbe mcp configure")
        for line in configure_clients("all", dry_run=True):
            console.print(f" [cyan]->[/cyan] {line}")
    else:
        agent = choice(
            interactive,
            "Which agent config should Navbe write?",
            ["cursor", "claude", "all", "skip"],
            default="cursor",
        )
        if agent != "skip":
            for line in configure_clients(cast(ClientName, agent)):
                console.print(f" [green]ok[/green] {line}")
            console.print(
                " [dim]Or paste the snippet above / run: navbe mcp configure[/dim]"
            )
        else:
            console.print(" [dim]Skipped - run later: navbe mcp configure[/dim]")
    pause(interactive, "Press Enter for next steps...")

    # 7. Finish
    section("You are ready", step)
    if dry_run:
        console.print("[yellow]Dry run complete.[/yellow]")
    else:
        console.print("[bold green]Setup complete.[/bold green]")
        console.print(
            " In your agent, start with [cyan]navbe_howto[/cyan] "
            "then [cyan]flow_list[/cyan]."
        )
        if interactive:
            nxt = choice(
                True,
                "What next?",
                ["info", "steps", "serve", "done"],
                default="done",
            )
            if nxt == "info":
                console.print(" [dim]Run:[/dim] navbe info")
            elif nxt == "steps":
                console.print(" [dim]Run:[/dim] navbe steps")
            elif nxt == "serve":
                console.print(" [dim]Run:[/dim] navbe serve")
    console.print()
    console.print(f"[dim]Docs: {DOCS_CONNECT}[/dim]")
