"""navbe serve — run FastAPI + MCP HTTP."""

from __future__ import annotations

import click


@click.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind host.")
@click.option("--port", default=8000, show_default=True, type=int, help="Bind port.")
@click.option("--reload", is_flag=True, help="Enable auto-reload (dev only).")
def serve_cmd(host: str, port: int, reload: bool) -> None:
    """Run the Navbe HTTP API and mounted MCP server."""
    import uvicorn

    uvicorn.run("navbe.main:app", host=host, port=port, reload=reload)
