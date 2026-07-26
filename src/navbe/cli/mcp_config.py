"""Build and write MCP client configs pointing at the local Navbe daemon."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from navbe.cli.daemon import DEFAULT_HOST, DEFAULT_PORT, default_mcp_url

ClientName = Literal["cursor", "claude", "all"]


def mcp_server_entry(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict[str, Any]:
    """Single-server entry (URL transport; no ``mcpServers`` wrapper)."""
    return {"url": default_mcp_url(host=host, port=port)}


def mcp_config_snippet(
    *,
    wrap: bool = True,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> str:
    """Return JSON for Cursor/Claude Desktop MCP config."""
    entry = mcp_server_entry(host=host, port=port)
    payload: dict[str, Any] = {"mcpServers": {"navbe": entry}} if wrap else {"navbe": entry}
    return json.dumps(payload, indent=2)


def cursor_mcp_path() -> Path:
    """Global Cursor MCP config path."""
    return Path.home() / ".cursor" / "mcp.json"


def claude_desktop_config_path() -> Path | None:
    """Claude Desktop config path for this OS, if a conventional location exists."""
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Claude" / "claude_desktop_config.json"
        return None
    # macOS primary; Linux users can paste via ``navbe mcp show``.
    return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"


def _read_json_object(path: Path) -> dict[str, Any]:
    """Load a JSON object from ``path``, or empty dict if missing/invalid."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def merge_navbe_mcp(
    config: dict[str, Any],
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict[str, Any]:
    """Insert/replace the ``navbe`` server under ``mcpServers``."""
    out = dict(config)
    servers = out.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
    else:
        servers = dict(servers)
    servers["navbe"] = mcp_server_entry(host=host, port=port)
    out["mcpServers"] = servers
    return out


def write_mcp_config(
    path: Path,
    *,
    dry_run: bool = False,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> str:
    """Merge Navbe into ``path`` and write it. Returns a short status string."""
    existing = _read_json_object(path)
    merged = merge_navbe_mcp(existing, host=host, port=port)
    text = json.dumps(merged, indent=2) + "\n"
    if dry_run:
        return f"would write {path}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return f"wrote {path}"


def configure_clients(
    clients: ClientName = "all",
    *,
    dry_run: bool = False,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> list[str]:
    """Write MCP config for the selected client(s). Returns status lines."""
    actions: list[str] = []
    want_cursor = clients in ("cursor", "all")
    want_claude = clients in ("claude", "all")
    if want_cursor:
        actions.append(
            write_mcp_config(cursor_mcp_path(), dry_run=dry_run, host=host, port=port)
        )
    if want_claude:
        claude_path = claude_desktop_config_path()
        if claude_path is None:
            actions.append("skipped Claude Desktop (unsupported platform path)")
        else:
            actions.append(
                write_mcp_config(claude_path, dry_run=dry_run, host=host, port=port)
            )
    return actions
