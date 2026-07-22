"""navbe serve — run FastAPI + MCP HTTP."""

from __future__ import annotations

from typing import Annotated

import typer


def serve_cmd(
    host: Annotated[
        str,
        typer.Option("--host", help="Bind host.", show_default=True),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", help="Bind port.", show_default=True),
    ] = 8000,
    reload: Annotated[
        bool,
        typer.Option("--reload", help="Enable auto-reload (dev only)."),
    ] = False,
) -> None:
    """Run the Navbe HTTP API and mounted MCP server."""
    import uvicorn

    uvicorn.run("navbe.main:app", host=host, port=port, reload=reload)
