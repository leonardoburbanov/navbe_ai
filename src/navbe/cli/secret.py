"""navbe secret — local credentials (never echo values)."""

from __future__ import annotations

import getpass

import click
from rich.console import Console

from navbe.cli.errors import handle_navbe_errors, run_async
from navbe.dependencies import get_secrets_service

console = Console()


@click.group("secret")
def secret_group() -> None:
    """Manage local credentials (navbe_credentials.json). Values are never shown."""


@secret_group.command("set")
@click.argument("key")
@handle_navbe_errors
def secret_set(key: str) -> None:
    """Store a credential key (prompts for value via hidden input)."""
    value = getpass.getpass(f"Value for {key}: ")
    if not value:
        raise click.ClickException("Empty value; aborted.")
    run_async(get_secrets_service().set(key, value))
    console.print(f"[green]Stored[/green] key={key}")


@secret_group.command("list")
@handle_navbe_errors
def secret_list() -> None:
    """List credential keys (never values)."""
    from navbe.cli.actions import list_secret_keys

    list_secret_keys()


@secret_group.command("delete")
@click.argument("key")
@handle_navbe_errors
def secret_delete(key: str) -> None:
    """Delete a key from the local credentials file."""
    deleted = run_async(get_secrets_service().delete(key))
    if deleted:
        console.print(f"[green]Deleted[/green] key={key}")
    else:
        console.print(f"[dim]Key not found:[/dim] {key}")


@secret_group.command("has")
@click.argument("key")
@handle_navbe_errors
def secret_has(key: str) -> None:
    """Check whether a key exists (credentials file or env)."""
    present = run_async(get_secrets_service().has(key))
    label = "yes" if present else "no"
    console.print(f"{key}: {label}")
