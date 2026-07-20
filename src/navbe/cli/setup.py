"""navbe setup — guided first-run onboarding."""

from __future__ import annotations

import shutil
import subprocess
import sys

import click
from rich.console import Console

from navbe import __version__
from navbe.cli.errors import handle_navbe_errors, run_async
from navbe.cli.onboarding import (
    DOCS_CONNECT,
    RECOMMENDED_KEYS,
    ensure_data_dirs,
    find_repo_root,
    mcp_config_snippet,
    print_banner,
    print_quick_start,
    python_version_ok,
    section,
)
from navbe.core.config import get_settings
from navbe.dependencies import get_secrets_service

console = Console()


def _run_uv_sync(dry_run: bool) -> tuple[bool, str]:
    """Run ``uv sync`` when uv is available."""
    if shutil.which("uv") is None:
        return False, "uv not on PATH — install from https://docs.astral.sh/uv/"
    cmd = ["uv", "sync"]
    if dry_run:
        return True, f"would run: {' '.join(cmd)}"
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:500]
        return False, f"uv sync failed: {err}"
    return True, "dependencies synced"


@click.command("setup")
@click.option("--dry-run", is_flag=True, help="Preview steps without making changes.")
@click.option("--skip-sync", is_flag=True, help="Skip uv sync step.")
@handle_navbe_errors
def setup_cmd(dry_run: bool, skip_sync: bool) -> None:
    """Install deps, verify paths, and print agent connection steps.

    Similar to ``agents-cli setup``: one command to get from clone → ready.
    """
    print_banner()
    console.print(f"[dim]Navbe v{__version__}[/dim]")
    if dry_run:
        console.print("[yellow]Dry run — no changes will be made.[/yellow]")

    step = 1

    # 1. Environment
    section("Environment", step)
    step += 1
    if python_version_ok():
        console.print(f" [green]✓[/green] Python {sys.version_info.major}.{sys.version_info.minor}")
    else:
        console.print(" [red]✗[/red] Python 3.12+ required")
    repo = find_repo_root()
    if repo:
        console.print(f" [green]✓[/green] Repo root: {repo}")
    else:
        console.print(" [yellow]![/yellow] Not inside a navbe checkout (info still works)")

    # 2. Dependencies
    section("Dependencies", step)
    step += 1
    if skip_sync:
        console.print(" [dim]Skipped (--skip-sync)[/dim]")
    elif dry_run:
        ok, msg = _run_uv_sync(dry_run=True)
        console.print(f" [cyan]→[/cyan] {msg}")
    else:
        ok, msg = _run_uv_sync(dry_run=False)
        icon = "[green]✓[/green]" if ok else "[yellow]![/yellow]"
        console.print(f" {icon} {msg}")

    # 3. Local data dirs
    section("Local data", step)
    step += 1
    settings = get_settings()
    if dry_run:
        console.print(
            f" [cyan]→[/cyan] would ensure {settings.flows_dir} "
            f"and {settings.db_path.parent}"
        )
    else:
        actions = ensure_data_dirs(settings.flows_dir, settings.db_path)
        if actions:
            for action in actions:
                console.print(f" [green]✓[/green] {action}")
        else:
            console.print(" [green]✓[/green] Data directories present")

    # 4. Credentials
    section("Credentials", step)
    step += 1
    keys = run_async(get_secrets_service().list_keys()) if not dry_run else []
    if keys:
        console.print(f" [green]✓[/green] {len(keys)} key(s) in {settings.credentials_path.name}")
    else:
        console.print(" [dim]No keys yet — run:[/dim] navbe secret set GITHUB_TOKEN")
    console.print(" [dim]Recommended keys:[/dim]", ", ".join(RECOMMENDED_KEYS))

    # 5. Agent connection
    section("Connect your coding agent", step)
    step += 1
    console.print(" Agents use [bold]navbe-mcp[/bold] over stdio (not this CLI).")
    if repo:
        console.print()
        console.print(" [bold]Claude Desktop / Cursor MCP config:[/bold]")
        console.print(mcp_config_snippet(repo))
        plugin_zip = repo / "claude-plugin" / "navbe-plugin.zip"
        if plugin_zip.is_file():
            console.print()
            console.print(f" [bold]Claude plugin:[/bold] upload {plugin_zip}")
            console.print("  (includes navbe-flows skill + .mcp.json)")
    else:
        console.print(" [dim]Run setup from the navbe repo to print an MCP snippet.[/dim]")
    console.print()
    console.print(f" [dim]Full guide:[/dim] {DOCS_CONNECT}")

    # 6. Summary
    section("Next steps", step)
    console.print(" [cyan]navbe info[/cyan]           Check paths, sync, and credential readiness")
    console.print(" [cyan]navbe secret set KEY[/cyan]  Store API keys (values never shown)")
    console.print(" [cyan]navbe steps[/cyan]           Browse available step types")
    console.print(" [cyan]navbe sync status[/cyan]    After configuring GitHub mirror")
    console.print()
    if not dry_run:
        console.print(
            "[bold green]Done.[/bold green] Open your agent and call "
            "[cyan]navbe_howto[/cyan]."
        )
    else:
        console.print("[yellow]Dry run complete.[/yellow]")
    console.print()
    print_quick_start()
