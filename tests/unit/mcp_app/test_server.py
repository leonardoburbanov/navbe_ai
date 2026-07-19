"""Tests for create_mcp_server registration."""

from fastmcp import Client

from tests.unit.mcp_app.conftest import make_server


async def test_server_registers_expected_tools() -> None:
    """Server exposes the six flow.* tools."""
    server = make_server()
    async with Client(server) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools}
    assert {
        "flow.create",
        "flow.validate",
        "flow.run",
        "flow.status",
        "flow.resume",
        "flow.list_runs",
    } <= names


async def test_server_registers_expected_resources() -> None:
    """Server exposes catalog resources."""
    server = make_server()
    async with Client(server) as client:
        resources = await client.list_resources()
        uris = {str(resource.uri) for resource in resources}
    assert "navbe://catalog/steps" in uris
    assert "navbe://catalog/connectors" in uris
