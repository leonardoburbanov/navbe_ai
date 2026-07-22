"""Tests for catalog and flows MCP resources."""

import json

import pytest
from fastmcp import Client

from navbe.core.exceptions import NotFoundError
from tests.unit.mcp_app.conftest import FakeCatalogService, FakeFlowService, make_server


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


async def test_flows_index_resource_lists_metadata() -> None:
    """navbe://flows returns saved flow metadata."""
    flow_service = FakeFlowService()
    await flow_service.create({"flow_id": "demo", "name": "Demo"})
    server = make_server(flow_service=flow_service)
    async with Client(server) as client:
        body = await _read_json(client, "navbe://flows")
    assert body["flows"][0]["flow_id"] == "demo"


async def test_flow_by_id_resource_returns_spec() -> None:
    """navbe://flows/{flow_id} returns the FlowSpec."""
    flow_service = FakeFlowService()
    await flow_service.create({"flow_id": "demo", "name": "Demo"})
    server = make_server(flow_service=flow_service)
    async with Client(server) as client:
        body = await _read_json(client, "navbe://flows/demo")
    assert body["flow_id"] == "demo"
    assert body["entry_node"] == "n1"


async def test_flow_by_id_missing_raises() -> None:
    """Missing flow resource surfaces NotFoundError (not a silent empty body)."""
    flow_service = FakeFlowService()
    flow_service.get_error = NotFoundError("missing", details={"flow_id": "ghost"})
    server = make_server(flow_service=flow_service)
    async with Client(server) as client:
        with pytest.raises(Exception):  # noqa: B017 — MCP wraps NotFoundError
            await client.read_resource("navbe://flows/ghost")
