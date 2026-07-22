"""navbe sync — GitHub flows mirror (flows/<id>/flow.json only)."""

from __future__ import annotations

import click

from navbe.cli.errors import handle_navbe_errors, run_async
from navbe.cli.format import print_sync_result, print_sync_status
from navbe.dependencies import get_sync_service


@click.group("sync")
def sync_group() -> None:
    """Sync flow organization with GitHub (flow.json only — not runs or credentials)."""


@sync_group.command("configure")
@click.option("--remote-url", default=None, help="HTTPS GitHub remote URL.")
@click.option("--local-repo-dir", default=None, help="Working clone directory.")
@click.option("--flows-subdir", default=None, help="Subdir inside clone (default: flows).")
@click.option("--default-branch", default=None, help="Default branch (default: main).")
@click.option("--token-secret-key", default=None, help="Credentials key for token.")
@handle_navbe_errors
def sync_configure(
    remote_url: str | None,
    local_repo_dir: str | None,
    flows_subdir: str | None,
    default_branch: str | None,
    token_secret_key: str | None,
) -> None:
    """Persist sync settings (token via navbe secret set GITHUB_TOKEN)."""
    config = run_async(
        get_sync_service().configure(
            remote_url=remote_url,
            local_repo_dir=local_repo_dir,
            flows_subdir=flows_subdir,
            default_branch=default_branch,
            token_secret_key=token_secret_key,
        )
    )
    click.echo(f"Saved sync config (remote={config.remote_url or '-'})")
    status = run_async(get_sync_service().status())
    print_sync_status(status)


@sync_group.command("init")
@handle_navbe_errors
def sync_init() -> None:
    """Clone or bind the configured GitHub repository."""
    status = run_async(get_sync_service().init())
    print_sync_status(status)


@sync_group.command("status")
@handle_navbe_errors
def sync_status_cmd() -> None:
    """Show branch, dirty flag, and flow counts."""
    from navbe.cli.actions import show_sync

    show_sync()


@sync_group.group("branch")
def sync_branch_group() -> None:
    """Branch operations."""


@sync_branch_group.command("create")
@click.argument("name")
@handle_navbe_errors
def sync_branch_create(name: str) -> None:
    """Create and checkout a branch from default_branch."""
    status = run_async(get_sync_service().branch_create(name))
    print_sync_status(status)


@sync_group.command("checkout")
@click.argument("branch")
@handle_navbe_errors
def sync_checkout(branch: str) -> None:
    """Checkout an existing branch (fails if working tree is dirty)."""
    status = run_async(get_sync_service().checkout(branch))
    print_sync_status(status)


@sync_group.command("push")
@click.option("--message", "-m", default=None, help="Commit message.")
@handle_navbe_errors
def sync_push(message: str | None) -> None:
    """Push local flows/<id>/flow.json to GitHub."""
    result = run_async(get_sync_service().push(message))
    print_sync_result(result)


@sync_group.command("pull")
@handle_navbe_errors
def sync_pull() -> None:
    """Pull flows from GitHub into local Navbe (ff-only)."""
    result = run_async(get_sync_service().pull())
    print_sync_result(result)
