"""navbe sync — GitHub workspace mirror (flows + reserved asset layout)."""

from __future__ import annotations

from typing import Annotated

import typer

from navbe.cli.actions import show_sync
from navbe.cli.errors import handle_navbe_errors, run_async
from navbe.cli.format import print_sync_result, print_sync_status
from navbe.dependencies import get_sync_service

app = typer.Typer(
    help=(
        "Sync versionable workspace metadata with GitHub "
        "(flows now; connectors/destinations/schedules when registered). "
        "Auth: navbe login github."
    )
)
branch_app = typer.Typer(help="Branch operations.")
app.add_typer(branch_app, name="branch")


@app.command("configure")
@handle_navbe_errors
def sync_configure(
    remote_url: Annotated[
        str | None,
        typer.Option("--remote-url", help="HTTPS GitHub remote URL."),
    ] = None,
    local_repo_dir: Annotated[
        str | None,
        typer.Option("--local-repo-dir", help="Working clone directory."),
    ] = None,
    flows_subdir: Annotated[
        str | None,
        typer.Option("--flows-subdir", help="Flows subdir inside clone (default: flows)."),
    ] = None,
    default_branch: Annotated[
        str | None,
        typer.Option("--default-branch", help="Default branch (default: main)."),
    ] = None,
) -> None:
    """Persist sync settings (token via navbe login github)."""
    config = run_async(
        get_sync_service().configure(
            remote_url=remote_url,
            local_repo_dir=local_repo_dir,
            flows_subdir=flows_subdir,
            default_branch=default_branch,
        )
    )
    typer.echo(f"Saved sync config (remote={config.remote_url or '-'})")
    status = run_async(get_sync_service().status())
    print_sync_status(status)


@app.command("connect")
@handle_navbe_errors
def sync_connect(
    owner: Annotated[str, typer.Argument(help="GitHub user or org.")],
    name: Annotated[str, typer.Argument(help="Repository name.")],
    private: Annotated[
        bool,
        typer.Option("--private/--public", help="Create as private if missing."),
    ] = True,
    local_repo_dir: Annotated[
        str | None,
        typer.Option("--local-repo-dir", help="Working clone directory."),
    ] = None,
    default_branch: Annotated[
        str | None,
        typer.Option("--default-branch", help="Default branch (default: main)."),
    ] = None,
) -> None:
    """Create-or-bind owner/name, configure remote, and init the clone."""
    status = run_async(
        get_sync_service().connect(
            owner=owner,
            name=name,
            private=private,
            local_repo_dir=local_repo_dir,
            default_branch=default_branch,
        )
    )
    print_sync_status(status)


@app.command("init")
@handle_navbe_errors
def sync_init() -> None:
    """Clone or bind the configured GitHub repository."""
    status = run_async(get_sync_service().init())
    print_sync_status(status)


@app.command("status")
@handle_navbe_errors
def sync_status_cmd() -> None:
    """Show branch, dirty flag, and asset counts."""
    show_sync()


@branch_app.command("create")
@handle_navbe_errors
def sync_branch_create(
    name: Annotated[str, typer.Argument(help="New branch name.")],
) -> None:
    """Create and checkout a branch from default_branch."""
    status = run_async(get_sync_service().branch_create(name))
    print_sync_status(status)


@app.command("checkout")
@handle_navbe_errors
def sync_checkout(
    branch: Annotated[str, typer.Argument(help="Existing branch name.")],
) -> None:
    """Checkout an existing branch (fails if working tree is dirty)."""
    status = run_async(get_sync_service().checkout(branch))
    print_sync_status(status)


@app.command("push")
@handle_navbe_errors
def sync_push(
    message: Annotated[
        str | None,
        typer.Option("--message", "-m", help="Commit message."),
    ] = None,
) -> None:
    """Push local workspace assets to GitHub."""
    result = run_async(get_sync_service().push(message))
    print_sync_result(result)


@app.command("pull")
@handle_navbe_errors
def sync_pull() -> None:
    """Pull workspace assets from GitHub into local Navbe (ff-only)."""
    result = run_async(get_sync_service().pull())
    print_sync_result(result)
