"""Tests for create_mcp_server registration."""

from fastmcp import Client

from tests.unit.mcp_app.conftest import make_server


async def test_server_registers_expected_tools() -> None:
    """Server exposes flow_* and catalog_* discovery tools."""
    server = make_server()
    async with Client(server) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools}
    assert {
        "catalog_steps",
        "catalog_connectors",
        "catalog_full",
        "flow_list",
        "flow_get",
        "flow_create",
        "flow_validate",
        "flow_update",
        "flow_run",
        "flow_status",
        "flow_resume",
        "flow_list_runs",
    } <= names


async def test_server_registers_expected_resources() -> None:
    """Server exposes catalog and flows resources."""
    server = make_server()
    async with Client(server) as client:
        resources = await client.list_resources()
        uris = {str(resource.uri) for resource in resources}
        templates = await client.list_resource_templates()
        template_uris = {str(template.uriTemplate) for template in templates}
    assert "navbe://catalog/steps" in uris
    assert "navbe://catalog/connectors" in uris
    assert "navbe://flows" in uris
    assert "navbe://flows/{flow_id}" in template_uris
