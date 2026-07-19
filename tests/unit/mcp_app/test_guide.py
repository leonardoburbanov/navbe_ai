"""Tests for Claude-facing Navbe howto tool / resource / prompt."""

from fastmcp import Client

from navbe.mcp_app.guide import NAVBE_HOWTO
from tests.unit.mcp_app.conftest import make_server


async def test_navbe_howto_tool_returns_playbook() -> None:
    """navbe_howto tool returns the shared playbook text."""
    server = make_server()
    async with Client(server) as client:
        result = await client.call_tool("navbe_howto", {})
    assert result.data["guide"] == NAVBE_HOWTO
    assert "catalog_steps" in result.data["guide"]
    assert "Ask the user before" in result.data["guide"]


async def test_navbe_guide_resource_matches_howto() -> None:
    """navbe://guide matches NAVBE_HOWTO."""
    server = make_server()
    async with Client(server) as client:
        contents = await client.read_resource("navbe://guide")
    assert contents[0].text == NAVBE_HOWTO


async def test_navbe_howto_prompt_registered() -> None:
    """Prompt navbe_howto is registered and returns the playbook."""
    server = make_server()
    async with Client(server) as client:
        prompts = await client.list_prompts()
        names = {prompt.name for prompt in prompts}
        assert "navbe_howto" in names
        result = await client.get_prompt("navbe_howto")
    blob = str(result)
    assert "catalog_steps" in blob
    assert "flow_run" in blob
