"""Application entrypoint — FastAPI + mounted FastMCP (no business logic)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from navbe.api.v1.routes import flows as flows_routes
from navbe.api.v1.routes import runs as runs_routes
from navbe.api.v1.routes import schedules as schedules_routes
from navbe.api.v1.routes import secrets as secrets_routes
from navbe.api.v1.routes import sync as sync_routes
from navbe.dependencies import (
    get_catalog_service,
    get_db_engine,
    get_flow_service,
    get_github_auth_service,
    get_run_service,
    get_schedule_service,
    get_scheduler_loop,
    get_secrets_service,
    get_sync_service,
)
from navbe.domains.flows.repository import metadata as flows_metadata
from navbe.domains.schedules.repository import metadata as schedules_metadata
from navbe.mcp_app.server import create_mcp_server


def create_app() -> FastAPI:
    """Build the FastAPI app with REST routers and a mounted MCP ASGI app."""
    mcp_server = create_mcp_server(
        flow_service=get_flow_service(),
        run_service=get_run_service(),
        catalog_service=get_catalog_service(),
        secrets_service=get_secrets_service(),
        sync_service=get_sync_service(),
        github_auth_service=get_github_auth_service(),
        schedule_service=get_schedule_service(),
    )
    # Verified against fastmcp 3.4.x: http_app(path="/") + lifespan + mount.
    mcp_http = mcp_server.http_app(path="/")

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        async with mcp_http.lifespan(_app):
            engine = get_db_engine()
            async with engine.begin() as conn:
                await conn.run_sync(flows_metadata.create_all)
                await conn.run_sync(schedules_metadata.create_all)
            scheduler = get_scheduler_loop()
            scheduler.start()
            try:
                yield
            finally:
                await scheduler.stop()

    app = FastAPI(title="Navbe", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness probe for humans and load balancers."""
        return {"status": "ok"}

    app.include_router(flows_routes.router, prefix="/api/v1/flows", tags=["flows"])
    app.include_router(runs_routes.router, prefix="/api/v1/runs", tags=["runs"])
    app.include_router(
        schedules_routes.router, prefix="/api/v1/schedules", tags=["schedules"]
    )
    app.include_router(secrets_routes.router, prefix="/api/v1/secrets", tags=["secrets"])
    app.include_router(sync_routes.router, prefix="/api/v1/sync", tags=["sync"])
    app.mount("/mcp", mcp_http)
    app.state.mcp_server = mcp_server  # type: ignore[attr-defined]
    return app


app = create_app()
