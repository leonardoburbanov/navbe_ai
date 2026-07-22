"""navbe mcp — show / write MCP client configuration."""

from __future__ import annotations

from typing import Annotated, Literal

import typer
from rich.console import Console
from rich.panel import Panel

from navbe.cli.errors import handle_navbe_errors
from navbe.cli.mcp_config import (
    configure_clients,
    mcp_config_snippet,
    resolve_navbe_mcp_command,
)

console = Console()

app = typer.Typer(help="Configure Cursor / Claude Desktop to use navbe-mcp.")


@app.command("show")
@handle_navbe_errors
def mcp_show() -> None:
    """Print a pasteable MCP JSON snippet (mcpServers wrapper)."""
    command, args = resolve_navbe_mcp_command()
    console.print(f"[dim]command=[/dim]{command} [dim]args=[/dim]{args or '[]'}")
    console.print(
        Panel(
            mcp_config_snippet(wrap=True),
            title="MCP config",
            border_style="cyan",
        )
    )


@app.command("configure")
@handle_navbe_errors
def mcp_configure(
    client: Annotated[
        Literal["cursor", "claude", "all"],
        typer.Option("--client", "-c", help="Which MCP client config to update."),
    ] = "all",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview paths without writing."),
    ] = False,
) -> None:
    """Merge the navbe MCP server into Cursor and/or Claude Desktop configs."""
    for line in configure_clients(client, dry_run=dry_run):
        icon = "[cyan]->[/cyan]" if dry_run else "[green]ok[/green]"
        console.print(f" {icon} {line}")
    if not dry_run:
        console.print(
            "[dim]Reload MCP in the client (Cursor: Settings → MCP; "
            "Claude: fully quit and reopen).[/dim]"
        )
