"""navbe info — show local config, paths, and readiness."""

from __future__ import annotations

import json
import platform
import shutil
from pathlib import Path
from typing import Any

import click
from rich.table import Table

from navbe import __version__
from navbe.cli.errors import handle_navbe_errors, run_async
from navbe.cli.format import console
from navbe.cli.onboarding import (
    DOCS_CONNECT,
    RECOMMENDED_KEYS,
    find_repo_root,
    mcp_config_snippet,
)
from navbe.core.config import get_settings
from navbe.dependencies import get_secrets_service, get_sync_service
from navbe.domains.sync.service import list_flow_ids


async def _gather_info() -> dict[str, Any]:
    """Collect status fields for display or JSON export."""
    settings = get_settings()
    secrets = get_secrets_service()
    keys = await secrets.list_keys()
    key_presence = {key: await secrets.has(key) for key in RECOMMENDED_KEYS}
    sync_status = await get_sync_service().status()
    repo = find_repo_root()
    flows_dir = settings.flows_dir.resolve()
    flow_count = len(list_flow_ids(flows_dir)) if flows_dir.exists() else 0
    return {
        "version": __version__,
        "cwd": str(Path.cwd()),
        "repo_root": str(repo) if repo else None,
        "python": platform.python_version(),
        "git_on_path": shutil.which("git") is not None,
        "uv_on_path": shutil.which("uv") is not None,
        "paths": {
            "flows_dir": str(flows_dir),
            "flows_dir_exists": flows_dir.exists(),
            "db_path": str(settings.db_path.resolve()),
            "db_path_exists": settings.db_path.exists(),
            "credentials_path": str(settings.credentials_path.resolve()),
            "credentials_exists": settings.credentials_path.exists(),
            "sync_config_path": str(settings.sync_config_path.resolve()),
            "sync_config_exists": settings.sync_config_path.exists(),
        },
        "credentials": {
            "stored_key_count": len(keys),
            "recommended": key_presence,
        },
        "sync": sync_status.model_dump(),
        "flows": {"local_count": flow_count},
        "docs": {"connect_agents": DOCS_CONNECT, "quickstart": "docs/agents/quickstart.md"},
    }


def _print_info(data: dict[str, Any]) -> None:
    """Render human-readable info table."""
    console.print(f"[bold]Navbe[/bold] v{data['version']}")
    console.print(f"[dim]cwd[/dim] {data['cwd']}")
    if data["repo_root"]:
        console.print(f"[dim]repo[/dim] {data['repo_root']}")
    console.print(
        f"[dim]tools[/dim] python {data['python']} · "
        f"uv={'yes' if data['uv_on_path'] else 'no'} · "
        f"git={'yes' if data['git_on_path'] else 'no'}"
    )

    path_rows = [
        ("flows_dir", data["paths"]["flows_dir"], data["paths"]["flows_dir_exists"]),
        ("db_path", data["paths"]["db_path"], data["paths"]["db_path_exists"]),
        (
            "credentials_path",
            data["paths"]["credentials_path"],
            data["paths"]["credentials_exists"],
        ),
        (
            "sync_config_path",
            data["paths"]["sync_config_path"],
            data["paths"]["sync_config_exists"],
        ),
    ]
    paths = Table(title="Paths")
    paths.add_column("setting")
    paths.add_column("path", overflow="fold")
    paths.add_column("exists")
    for name, path, exists in path_rows:
        paths.add_row(name, path, "yes" if exists else "no")
    console.print(paths)

    creds = data["credentials"]
    console.print(f"[bold]Credentials[/bold] {creds['stored_key_count']} key(s) in store")
    rec = Table(show_header=False, box=None)
    rec.add_column("key")
    rec.add_column("present")
    for key, present in creds["recommended"].items():
        style = "green" if present else "dim"
        rec.add_row(key, f"[{style}]{'yes' if present else 'no'}[/{style}]")
    console.print(rec)

    sync = data["sync"]
    console.print(
        f"[bold]Sync[/bold] configured={sync['configured']} "
        f"initialized={sync['initialized']} "
        f"branch={sync.get('branch') or '-'}"
    )
    console.print(f"[bold]Flows[/bold] {data['flows']['local_count']} local flow(s)")
    console.print(f"[dim]Docs[/dim] {DOCS_CONNECT}")


@click.command("info")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@handle_navbe_errors
def info_cmd(as_json: bool) -> None:
    """Show local paths, credential readiness, sync state, and CLI version."""
    data = run_async(_gather_info())
    if as_json:
        click.echo(json.dumps(data, indent=2))
        return
    _print_info(data)
    repo = data.get("repo_root")
    if repo:
        console.print()
        console.print("[dim]MCP snippet (paste into Claude/Cursor MCP config):[/dim]")
        console.print(mcp_config_snippet(Path(repo)))
