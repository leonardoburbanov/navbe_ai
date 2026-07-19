"""Application entrypoint — FastAPI + mounted FastMCP (no business logic)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from navbe.api.v1.routes import flows as flows_routes
from navbe.api.v1.routes import runs as runs_routes
from navbe.dependencies import (
    get_catalog_service,
    get_db_engine,
    get_flow_service,
    get_run_service,
)
from navbe.domains.flows.repository import metadata
from navbe.mcp_app.server import create_mcp_server


def create_app() -> FastAPI:
    """Build the FastAPI app with REST routers and a mounted MCP ASGI app."""
    mcp_server = create_mcp_server(
        flow_service=get_flow_service(),
        run_service=get_run_service(),
        catalog_service=get_catalog_service(),
    )
    # Verified against fastmcp 3.4.x: http_app(path="/") + lifespan + mount.
    mcp_http = mcp_server.http_app(path="/")

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        async with mcp_http.lifespan(_app):
            engine = get_db_engine()
            async with engine.begin() as conn:
                await conn.run_sync(metadata.create_all)
            yield

    app = FastAPI(title="Navbe", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness probe for humans and load balancers."""
        return {"status": "ok"}

    app.include_router(flows_routes.router, prefix="/api/v1/flows", tags=["flows"])
    app.include_router(runs_routes.router, prefix="/api/v1/runs", tags=["runs"])
    app.mount("/mcp", mcp_http)
    app.state.mcp_server = mcp_server  # type: ignore[attr-defined]
    return app


app = create_app()


def main() -> None:
    """Run the combined FastAPI + MCP process via uvicorn."""
    import uvicorn

    uvicorn.run("navbe.main:app", host="127.0.0.1", port=8000, reload=False)
