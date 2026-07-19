"""Subprocess contract tests for ``uv run navbe-mcp`` (stdio)."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def stdio_env(tmp_path: Path) -> dict[str, str]:
    """Env for a subprocess using isolated Navbe data dirs."""
    env = os.environ.copy()
    env["NAVBE_DB_PATH"] = str(tmp_path / "navbe.db")
    env["NAVBE_FLOWS_DIR"] = str(tmp_path / "flows")
    env["FASTMCP_SHOW_SERVER_BANNER"] = "false"
    return env


async def test_stdio_entrypoint_starts_and_responds_to_initialize(
    stdio_env: dict[str, str],
) -> None:
    """Spawn navbe-mcp, complete initialize over stdio, then disconnect."""
    transport = StdioTransport(
        command="uv",
        args=["run", "navbe-mcp"],
        env=stdio_env,
        cwd=str(ROOT),
    )
    async with Client(transport=transport) as client:
        result = client.initialize_result
        assert result is not None
        server_info = getattr(result, "serverInfo", None) or getattr(
            result, "server_info", None
        )
        assert server_info is not None
        assert getattr(server_info, "name", None)
        tools = await client.list_tools()
        names = {tool.name for tool in tools}
        assert "flow.create" in names
        assert "flow.run" in names


async def test_stdio_validate_and_create_minimal_flow(
    stdio_env: dict[str, str],
) -> None:
    """Smoke: validate + create a one-node set_var flow over stdio MCP."""
    spec = {
        "flow_id": "smoke_set_var",
        "entry_node": "n1",
        "nodes": [
            {
                "id": "n1",
                "step_type": "set_var",
                "config": {"var_name": "amount", "value_from": "amount"},
            }
        ],
        "edges": [],
    }
    transport = StdioTransport(
        command="uv",
        args=["run", "navbe-mcp"],
        env=stdio_env,
        cwd=str(ROOT),
    )
    async with Client(transport=transport) as client:
        validation = await client.call_tool("flow.validate", {"spec": spec})
        assert validation.data["valid"] is True

        created = await client.call_tool("flow.create", {"spec": spec})
        assert created.data["flow_id"] == "smoke_set_var"


async def test_stdio_entrypoint_exits_cleanly_on_sigterm(
    stdio_env: dict[str, str],
) -> None:
    """Terminate the stdio server without hanging or orphaned locks."""
    proc = subprocess.Popen(
        ["uv", "run", "navbe-mcp"],
        cwd=str(ROOT),
        env=stdio_env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        time.sleep(1.0)
        if sys.platform == "win32":
            proc.terminate()
        else:
            proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
            pytest.fail("navbe-mcp did not exit after SIGTERM/terminate")
        assert proc.returncode is not None
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
