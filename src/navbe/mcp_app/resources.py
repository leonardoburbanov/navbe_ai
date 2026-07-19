"""MCP resources backed by CatalogService and FlowService."""

from typing import Any

from fastmcp import FastMCP

from navbe.domains.catalog.service import CatalogService
from navbe.domains.flows.service import FlowService
from navbe.mcp_app.guide import NAVBE_HOWTO


def register_resources(
    mcp: FastMCP,
    catalog_service: CatalogService,
    flow_service: FlowService,
) -> None:
    """Register navbe://guide, catalog/*, and flows resources on ``mcp``."""

    @mcp.resource("navbe://guide")
    async def howto_guide() -> str:
        """Claude/Cursor playbook: discover → validate → create → ask → run."""
        return NAVBE_HOWTO

    @mcp.resource("navbe://catalog/steps")
    async def steps_catalog() -> dict[str, Any]:
        """JSON Schema catalog of available step types."""
        return await catalog_service.get_steps_catalog()

    @mcp.resource("navbe://catalog/connectors")
    async def connectors_catalog() -> dict[str, Any]:
        """JSON Schema catalog of available connector types."""
        return await catalog_service.get_connectors_catalog()

    @mcp.resource("navbe://catalog/full")
    async def full_catalog() -> dict[str, Any]:
        """Combined steps + connectors catalog."""
        return await catalog_service.get_full_catalog()

    @mcp.resource("navbe://flows")
    async def flows_index() -> dict[str, Any]:
        """Metadata for all saved flows."""
        flows = await flow_service.list()
        return {"flows": [flow.model_dump(mode="json") for flow in flows]}

    @mcp.resource("navbe://flows/{flow_id}")
    async def flow_by_id(flow_id: str) -> dict[str, Any]:
        """Full FlowSpec for a saved flow id."""
        flow_spec = await flow_service.get(flow_id)
        return flow_spec.model_dump(by_alias=True)
