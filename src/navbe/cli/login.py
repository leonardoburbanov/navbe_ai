"""navbe login — credential readiness (local keys, not OAuth)."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.table import Table

from navbe.cli.errors import handle_navbe_errors, run_async
from navbe.cli.format import console
from navbe.cli.onboarding import RECOMMENDED_KEYS
from navbe.dependencies import get_secrets_service


async def _auth_status_rows() -> list[tuple[str, bool]]:
    """Return recommended keys and whether each is present."""
    service = get_secrets_service()
    rows: list[tuple[str, bool]] = []
    for key in RECOMMENDED_KEYS:
        rows.append((key, await service.has(key)))
    return rows


@handle_navbe_errors
def login_cmd(
    status_only: Annotated[
        bool,
        typer.Option(
            "--status",
            help="Show which recommended keys are present (never values).",
        ),
    ] = False,
) -> None:
    """Check or set local credentials (Navbe uses secret keys, not cloud login).

    Use ``navbe secret set KEY`` to store values. This command shows readiness.
    """
    rows = run_async(_auth_status_rows())
    table = Table(title="Credential readiness")
    table.add_column("key")
    table.add_column("present")
    for key, present in rows:
        style = "green" if present else "dim"
        table.add_row(key, f"[{style}]{'yes' if present else 'no'}[/{style}]")
    console.print(table)

    if status_only:
        return

    console.print()
    console.print("Store keys locally (hidden prompt, never echoed):")
    console.print("  [cyan]navbe secret set GITHUB_TOKEN[/cyan]")
    console.print("  [cyan]navbe secret set NAVBE_ANTHROPIC_API_KEY[/cyan]")
    console.print()
    console.print("[dim]List keys:[/dim] navbe secret list")
