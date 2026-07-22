"""Build and write MCP client configs for installed or checkout Navbe."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Literal

from navbe.core.paths import find_repo_root

ClientName = Literal["cursor", "claude", "all"]


def resolve_navbe_mcp_command() -> tuple[str, list[str]]:
    """Return ``(command, args)`` for launching the Navbe MCP server.

    Prefers a checkout ``uv run --directory … navbe-mcp`` when inside the repo;
    otherwise the ``navbe-mcp`` shim on PATH (``uv tool install``).
    """
    repo = find_repo_root()
    if repo is not None:
        uv = shutil.which("uv") or "uv"
        return uv, ["run", "--directory", str(repo).replace("\\", "/"), "navbe-mcp"]
    mcp = shutil.which("navbe-mcp") or "navbe-mcp"
    return mcp, []


def mcp_server_entry() -> dict[str, Any]:
    """Single-server entry (no ``mcpServers`` wrapper)."""
    command, args = resolve_navbe_mcp_command()
    entry: dict[str, Any] = {"command": command}
    if args:
        entry["args"] = args
    return entry


def mcp_config_snippet(*, wrap: bool = True) -> str:
    """Return JSON for Cursor/Claude Desktop MCP config."""
    entry = mcp_server_entry()
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


def merge_navbe_mcp(config: dict[str, Any]) -> dict[str, Any]:
    """Insert/replace the ``navbe`` server under ``mcpServers``."""
    out = dict(config)
    servers = out.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
    else:
        servers = dict(servers)
    servers["navbe"] = mcp_server_entry()
    out["mcpServers"] = servers
    return out


def write_mcp_config(path: Path, *, dry_run: bool = False) -> str:
    """Merge Navbe into ``path`` and write it. Returns a short status string."""
    existing = _read_json_object(path)
    merged = merge_navbe_mcp(existing)
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
) -> list[str]:
    """Write MCP config for the selected client(s). Returns status lines."""
    actions: list[str] = []
    want_cursor = clients in ("cursor", "all")
    want_claude = clients in ("claude", "all")
    if want_cursor:
        actions.append(write_mcp_config(cursor_mcp_path(), dry_run=dry_run))
    if want_claude:
        claude_path = claude_desktop_config_path()
        if claude_path is None:
            actions.append("skipped Claude Desktop (unsupported platform path)")
        else:
            actions.append(write_mcp_config(claude_path, dry_run=dry_run))
    return actions
