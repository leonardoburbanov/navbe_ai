"""Entrypoint for stdio-transport MCP clients (Claude Desktop, Cursor AI).

Run with: ``uv run navbe-mcp``
"""

from __future__ import annotations

import argparse
import asyncio

from navbe.dependencies import (
    get_catalog_service,
    get_db_engine,
    get_flow_service,
    get_github_auth_service,
    get_run_service,
    get_secrets_service,
    get_sync_service,
)
from navbe.domains.flows.repository import metadata
from navbe.mcp_app.server import create_mcp_server


async def _ensure_schema() -> None:
    """Create control-plane tables before accepting MCP traffic."""
    engine = get_db_engine()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


def main(argv: list[str] | None = None) -> None:
    """Build the MCP server and run it over stdio."""
    parser = argparse.ArgumentParser(
        prog="navbe-mcp",
        description="Navbe MCP server (stdio) for Claude Desktop and Cursor AI",
    )
    parser.parse_args(argv)

    asyncio.run(_ensure_schema())
    mcp_server = create_mcp_server(
        flow_service=get_flow_service(),
        run_service=get_run_service(),
        catalog_service=get_catalog_service(),
        secrets_service=get_secrets_service(),
        sync_service=get_sync_service(),
        github_auth_service=get_github_auth_service(),
    )
    # Verified against fastmcp 3.4.x: transport="stdio". Banner must stay off
    # so stdout remains a clean MCP JSON-RPC channel.
    mcp_server.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
