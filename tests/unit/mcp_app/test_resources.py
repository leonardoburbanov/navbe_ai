"""Tests for catalog MCP resources."""

import json

from fastmcp import Client

from tests.unit.mcp_app.conftest import FakeCatalogService, make_server


async def _read_json(client: Client, uri: str) -> dict:
    """Read a resource URI and parse its JSON text body."""
    contents = await client.read_resource(uri)
    return json.loads(contents[0].text)


async def test_steps_resource_returns_catalog_service_output() -> None:
    """steps resource matches CatalogService.get_steps_catalog()."""
    catalog = FakeCatalogService()
    server = make_server(catalog_service=catalog)
    async with Client(server) as client:
        assert await _read_json(client, "navbe://catalog/steps") == catalog.steps


async def test_connectors_resource_returns_catalog_service_output() -> None:
    """connectors resource matches CatalogService.get_connectors_catalog()."""
    catalog = FakeCatalogService()
    server = make_server(catalog_service=catalog)
    async with Client(server) as client:
        assert await _read_json(client, "navbe://catalog/connectors") == catalog.connectors


async def test_full_resource_combines_both() -> None:
    """full resource matches CatalogService.get_full_catalog()."""
    catalog = FakeCatalogService()
    server = make_server(catalog_service=catalog)
    async with Client(server) as client:
        assert await _read_json(client, "navbe://catalog/full") == {
            "steps": catalog.steps,
            "connectors": catalog.connectors,
        }
