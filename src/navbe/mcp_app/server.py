"""FastMCP server factory — dependencies injected by the caller."""

from fastmcp import FastMCP

from navbe.core.config import get_settings
from navbe.domains.catalog.service import CatalogService
from navbe.domains.execution.service import RunService
from navbe.domains.flows.service import FlowService
from navbe.mcp_app.resources import register_resources
from navbe.mcp_app.tools import register_tools


def create_mcp_server(
    flow_service: FlowService,
    run_service: RunService,
    catalog_service: CatalogService,
) -> FastMCP:
    """Build a FastMCP server with flow/catalog tools and resources."""
    settings = get_settings()
    mcp = FastMCP(settings.mcp_server_name)
    register_tools(
        mcp,
        flow_service=flow_service,
        run_service=run_service,
        catalog_service=catalog_service,
    )
    register_resources(
        mcp,
        catalog_service=catalog_service,
        flow_service=flow_service,
    )
    return mcp
