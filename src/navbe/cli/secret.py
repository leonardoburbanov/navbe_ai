"""navbe secret — local credentials (masked hints only; never full values)."""

from __future__ import annotations

import getpass
from typing import Annotated

import typer
from rich.console import Console

from navbe.cli.actions import list_secret_keys
from navbe.cli.errors import handle_navbe_errors, run_async
from navbe.dependencies import get_secrets_service

console = Console()

app = typer.Typer(
    help="Manage local credentials (navbe_credentials.json). Values are never shown."
)


@app.command("set")
@handle_navbe_errors
def secret_set(
    key: Annotated[str, typer.Argument(help="Credential key name.")],
    app: Annotated[
        str | None,
        typer.Option("--app", help="Optional app slug (e.g. resend)."),
    ] = None,
) -> None:
    """Store a credential key (prompts for value via hidden input)."""
    value = getpass.getpass(f"Value for {key}: ")
    if not value:
        raise typer.BadParameter("Empty value; aborted.")
    hint = run_async(get_secrets_service().set(key, value, app=app))
    parts = [f"[green]Stored[/green] key={hint.key}", f"hint={hint.hint}"]
    if hint.app:
        parts.append(f"app={hint.app}")
    console.print(" ".join(parts))


@app.command("list")
@handle_navbe_errors
def secret_list() -> None:
    """List credentials with masked hints (never values)."""
    list_secret_keys()


@app.command("hint")
@handle_navbe_errors
def secret_hint(
    key: Annotated[str, typer.Argument(help="Credential key to inspect.")],
) -> None:
    """Show masked metadata for a key (never the full value)."""
    hint = run_async(get_secrets_service().get_hint(key))
    app_label = hint.app or "-"
    hint_label = hint.hint if hint.hint is not None else "(env only — no hint)"
    console.print(f"{hint.key}  app={app_label}  hint={hint_label}  source={hint.source}")


@app.command("delete")
@handle_navbe_errors
def secret_delete(
    key: Annotated[str, typer.Argument(help="Credential key to delete.")],
) -> None:
    """Delete a key from the local credentials file."""
    deleted = run_async(get_secrets_service().delete(key))
    if deleted:
        console.print(f"[green]Deleted[/green] key={key}")
    else:
        console.print(f"[dim]Key not found:[/dim] {key}")


@app.command("has")
@handle_navbe_errors
def secret_has(
    key: Annotated[str, typer.Argument(help="Credential key to check.")],
) -> None:
    """Check whether a key exists (credentials file or env)."""
    present = run_async(get_secrets_service().has(key))
    label = "yes" if present else "no"
    console.print(f"{key}: {label}")
