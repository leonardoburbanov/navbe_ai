"""navbe serve / status / stop — HTTP API + MCP + scheduler daemon."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from navbe.cli.daemon import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    default_mcp_url,
    read_serve_state,
    start_detached,
    stop_detached,
)
from navbe.cli.errors import handle_navbe_errors

console = Console()


@handle_navbe_errors
def serve_cmd(
    host: Annotated[
        str,
        typer.Option("--host", help="Bind host.", show_default=True),
    ] = DEFAULT_HOST,
    port: Annotated[
        int,
        typer.Option("--port", help="Bind port.", show_default=True),
    ] = DEFAULT_PORT,
    reload: Annotated[
        bool,
        typer.Option("--reload", help="Enable auto-reload (dev only; foreground only)."),
    ] = False,
    detach: Annotated[
        bool,
        typer.Option("--detach", "-d", help="Run in the background (pidfile under data home)."),
    ] = False,
) -> None:
    """Run the Navbe HTTP API, mounted MCP server, and schedule ticker."""
    if detach and reload:
        raise typer.BadParameter("--reload cannot be combined with --detach")
    if detach:
        state = start_detached(host=host, port=port)
        console.print(f"[green]ok[/green] navbe serve running (pid {state.pid})")
        console.print(f"  health  {state.health_url}")
        console.print(f"  mcp     {state.mcp_url}")
        console.print("[dim]Stop with: navbe stop[/dim]")
        return

    import uvicorn

    uvicorn.run("navbe.main:app", host=host, port=port, reload=reload)


@handle_navbe_errors
def status_cmd() -> None:
    """Show whether detached ``navbe serve`` is up and the MCP URL."""
    state = read_serve_state()
    if state is None:
        console.print("[yellow]navbe serve is not running[/yellow] (no pidfile)")
        console.print("[dim]Start with: navbe serve --detach[/dim]")
        console.print(f"[dim]Default MCP URL: {default_mcp_url()}[/dim]")
        raise typer.Exit(code=1)

    if not state.alive:
        console.print(
            f"[yellow]stale[/yellow] pidfile pid={state.pid} "
            f"(process not running); run [cyan]navbe stop[/cyan] to clear"
        )
        raise typer.Exit(code=1)

    health = "healthy" if state.healthy else "not responding"
    color = "green" if state.healthy else "yellow"
    console.print(f"[{color}]{health}[/{color}] navbe serve pid={state.pid}")
    console.print(f"  listen  http://{state.host}:{state.port}")
    console.print(f"  health  {state.health_url}")
    console.print(f"  mcp     {state.mcp_url}")
    if not state.healthy:
        raise typer.Exit(code=1)


@handle_navbe_errors
def stop_cmd(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force-kill if needed (Windows always force)."),
    ] = False,
) -> None:
    """Stop the detached ``navbe serve`` process."""
    message = stop_detached(force=force)
    console.print(f"[green]ok[/green] {message}")
