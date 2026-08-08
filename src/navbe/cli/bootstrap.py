"""navbe bootstrap — one-shot local install: dirs + daemon + MCP client configs."""

from __future__ import annotations

from typing import Annotated, Literal

import typer
from rich.console import Console

from navbe.cli.daemon import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    default_mcp_url,
    start_detached,
)
from navbe.cli.errors import handle_navbe_errors
from navbe.cli.mcp_config import ClientName, configure_clients
from navbe.cli.onboarding import ensure_data_dirs, print_banner
from navbe.core.config import get_settings

console = Console()


@handle_navbe_errors
def bootstrap_cmd(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview steps without starting serve or writing configs."),
    ] = False,
    no_serve: Annotated[
        bool,
        typer.Option("--no-serve", help="Skip starting the daemon (still write MCP URL configs)."),
    ] = False,
    client: Annotated[
        Literal["cursor", "claude", "all"],
        typer.Option("--client", "-c", help="Which MCP client config to update."),
    ] = "all",
    host: Annotated[
        str,
        typer.Option("--host", help="Bind host for navbe serve.", show_default=True),
    ] = DEFAULT_HOST,
    port: Annotated[
        int,
        typer.Option("--port", help="Bind port for navbe serve.", show_default=True),
    ] = DEFAULT_PORT,
) -> None:
    """Create data dirs, start ``navbe serve``, and wire Cursor / Claude to the MCP URL."""
    print_banner()
    settings = get_settings()
    clients: ClientName = client

    console.print("[bold]1. Local data[/bold]")
    if dry_run:
        console.print(
            f" [cyan]->[/cyan] would ensure {settings.flows_dir} "
            f"and {settings.db_path.parent}"
        )
    else:
        actions = ensure_data_dirs(settings.flows_dir, settings.db_path)
        if actions:
            for action in actions:
                console.print(f" [green]ok[/green] {action}")
        else:
            console.print(" [green]ok[/green] data directories present")

    console.print()
    console.print("[bold]2. Daemon[/bold]")
    if no_serve:
        console.print(" [dim]skipped (--no-serve)[/dim]")
    elif dry_run:
        console.print(f" [cyan]->[/cyan] would start navbe serve on {host}:{port}")
    else:
        state = start_detached(host=host, port=port)
        console.print(f" [green]ok[/green] serve pid={state.pid} ({state.health_url})")

    console.print()
    console.print("[bold]3. Agent clients[/bold]")
    for line in configure_clients(clients, dry_run=dry_run, host=host, port=port):
        icon = "[cyan]->[/cyan]" if dry_run else "[green]ok[/green]"
        console.print(f" {icon} {line}")

    console.print()
    console.print("[bold green]Ready[/bold green]")
    console.print(f"  MCP URL  {default_mcp_url(host=host, port=port)}")
    console.print("  Restart Cursor / Claude Desktop so they pick up the config.")
    console.print("  Secrets: [cyan]navbe secret set KEY --app NAME[/cyan]")
    console.print(
        "  Defaults: flows [cyan]starter[/cyan] (HTTP ping) + "
        "[cyan]langfuse_traces[/cyan] (set LANGFUSE_* secrets first)"
    )
    console.print("  Status:  [cyan]navbe status[/cyan]  Stop: [cyan]navbe stop[/cyan]")
