"""Tests for secret_* MCP tools."""

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from navbe.core.exceptions import ValidationError
from navbe.mcp_app.errors import parse_tool_error
from tests.unit.mcp_app.conftest import FakeSecretsService, make_server


async def test_secret_set_list_delete_round_trip() -> None:
    """secret_set stores; secret_list returns keys + items; secret_delete removes."""
    secrets = FakeSecretsService()
    server = make_server(secrets_service=secrets)
    async with Client(server) as client:
        stored = await client.call_tool(
            "secret_set",
            {"key": "API_KEY", "value": "sk-should-not-echo", "app": "crm"},
        )
        assert stored.data["key"] == "API_KEY"
        assert stored.data["stored"] is True
        assert stored.data["hint"] == "****echo"
        assert stored.data["app"] == "crm"
        assert "sk-should-not-echo" not in str(stored.data)

        listed = await client.call_tool("secret_list", {})
        assert listed.data["keys"] == ["API_KEY"]
        assert listed.data["items"][0]["hint"] == "****echo"
        assert listed.data["items"][0]["app"] == "crm"
        assert "sk-should-not-echo" not in str(listed.data)

        hinted = await client.call_tool("secret_hint", {"key": "API_KEY"})
        assert hinted.data["hint"] == "****echo"
        assert hinted.data["source"] == "store"

        has = await client.call_tool("secret_has", {"key": "API_KEY"})
        assert has.data == {"key": "API_KEY", "present": True}

        deleted = await client.call_tool("secret_delete", {"key": "API_KEY"})
        assert deleted.data == {"key": "API_KEY", "deleted": True}


async def test_secret_set_validation_error_never_echoes_value() -> None:
    """ValidationError from set becomes ToolError without the secret value."""
    secrets = FakeSecretsService()
    secrets.set_error = ValidationError("Invalid secret key", details={"key": "bad"})
    server = make_server(secrets_service=secrets)
    async with Client(server) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool("secret_set", {"key": "bad", "value": "super-secret"})
    payload = parse_tool_error(exc_info.value)
    assert payload["code"] == "validation_error"
    assert "super-secret" not in str(payload)
