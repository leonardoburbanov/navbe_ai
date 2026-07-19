"""Tests for catalog_* MCP tools."""

from fastmcp import Client

from tests.unit.mcp_app.conftest import FakeCatalogService, make_server


async def test_catalog_steps_mirrors_service() -> None:
    """catalog_steps returns CatalogService.get_steps_catalog()."""
    catalog = FakeCatalogService()
    server = make_server(catalog_service=catalog)
    async with Client(server) as client:
        result = await client.call_tool("catalog_steps", {})
    assert result.data == catalog.steps


async def test_catalog_connectors_mirrors_service() -> None:
    """catalog_connectors returns CatalogService.get_connectors_catalog()."""
    catalog = FakeCatalogService()
    server = make_server(catalog_service=catalog)
    async with Client(server) as client:
        result = await client.call_tool("catalog_connectors", {})
    assert result.data == catalog.connectors


async def test_catalog_full_mirrors_service() -> None:
    """catalog_full returns CatalogService.get_full_catalog()."""
    catalog = FakeCatalogService()
    server = make_server(catalog_service=catalog)
    async with Client(server) as client:
        result = await client.call_tool("catalog_full", {})
    assert result.data == {"steps": catalog.steps, "connectors": catalog.connectors}
