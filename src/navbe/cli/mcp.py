"""navbe mcp — show / write MCP client configuration (URL to local daemon)."""

from __future__ import annotations

from typing import Annotated, Literal

import typer
from rich.console import Console
from rich.panel import Panel

from navbe.cli.daemon import DEFAULT_HOST, DEFAULT_PORT, default_mcp_url
from navbe.cli.errors import handle_navbe_errors
from navbe.cli.mcp_config import configure_clients, mcp_config_snippet

console = Console()

app = typer.Typer(
    help="Configure Cursor / Claude Desktop to use the local Navbe daemon MCP URL."
)


@app.command("show")
@handle_navbe_errors
def mcp_show(
    host: Annotated[
        str,
        typer.Option("--host", help="Daemon host used in the MCP URL.", show_default=True),
    ] = DEFAULT_HOST,
    port: Annotated[
        int,
        typer.Option("--port", help="Daemon port used in the MCP URL.", show_default=True),
    ] = DEFAULT_PORT,
) -> None:
    """Print a pasteable MCP JSON snippet (mcpServers wrapper)."""
    console.print(f"[dim]url=[/dim]{default_mcp_url(host=host, port=port)}")
    console.print(
        Panel(
            mcp_config_snippet(wrap=True, host=host, port=port),
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
    host: Annotated[
        str,
        typer.Option("--host", help="Daemon host used in the MCP URL.", show_default=True),
    ] = DEFAULT_HOST,
    port: Annotated[
        int,
        typer.Option("--port", help="Daemon port used in the MCP URL.", show_default=True),
    ] = DEFAULT_PORT,
) -> None:
    """Merge the navbe MCP URL into Cursor and/or Claude Desktop configs."""
    for line in configure_clients(client, dry_run=dry_run, host=host, port=port):
        icon = "[cyan]->[/cyan]" if dry_run else "[green]ok[/green]"
        console.print(f" {icon} {line}")
    if not dry_run:
        console.print(
            "[dim]Ensure [cyan]navbe serve[/cyan] is running, then reload MCP "
            "(Cursor: Settings → MCP; Claude: fully quit and reopen).[/dim]"
        )
