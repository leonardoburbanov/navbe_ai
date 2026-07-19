"""MCP resources backed by CatalogService."""

from typing import Any

from fastmcp import FastMCP

from navbe.domains.catalog.service import CatalogService


def register_resources(mcp: FastMCP, catalog_service: CatalogService) -> None:
    """Register navbe://catalog/* resources on ``mcp``."""

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
