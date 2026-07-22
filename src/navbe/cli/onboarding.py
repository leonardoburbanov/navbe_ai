"""Shared onboarding copy, banner, and path helpers."""

from __future__ import annotations

import getpass
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from navbe import __version__
from navbe.cli.errors import run_async
from navbe.domains.execution.models import RunStatus

# UTF-8 + modern Windows console so box-drawing renders.
console = Console(legacy_windows=False, soft_wrap=True)

# Brand accent (Navbe blue)
NAVBE_BLUE = "#1e67e8"

DOCS_QUICKSTART = "docs/agents/quickstart.md"
DOCS_CONNECT = "docs/connect_agents.md"

# Keys humans/agents commonly need — presence only, never values.
RECOMMENDED_KEYS = (
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "NAVBE_ANTHROPIC_API_KEY",
    "CRM_API_KEY",
)

QUICK_START = """\
[bold]Quick start[/bold]

  1. [cyan]navbe setup[/cyan]              Verify install + agent connection hints
  2. [cyan]navbe secret set GITHUB_TOKEN[/cyan]   Store credentials (hidden prompt)
  3. [cyan]navbe sync configure --remote-url URL[/cyan]   Optional GitHub flows mirror
  4. Connect an agent with [cyan]navbe-mcp[/cyan] (see [cyan]navbe setup[/cyan] output)
  5. In the agent: call [cyan]navbe_howto[/cyan], then
     [cyan]catalog_steps[/cyan] / [cyan]flow_list[/cyan]

Agents use [bold]navbe-mcp[/bold]; humans use this CLI. Run [cyan]navbe --help[/cyan] for commands.\
"""

_ACTIVE = {RunStatus.PENDING, RunStatus.RUNNING, RunStatus.PAUSED}


@dataclass(frozen=True)
class _MenuSnapshot:
    """Live workspace facts for the intelligent welcome panel."""

    flow_count: int
    run_count: int
    active_runs: int
    paused_runs: int
    failed_recent: int
    secret_keys: int
    missing_recommended: tuple[str, ...]
    sync_configured: bool
    sync_initialized: bool
    sync_branch: str | None
    cwd: str


def _ensure_utf8_stdio() -> None:
    """Prefer UTF-8 so box borders render on Windows."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _display_name() -> str:
    """Best-effort local user name for the welcome line."""
    try:
        name = getpass.getuser().strip()
    except Exception:
        name = ""
    return name or "there"


async def _load_snapshot() -> _MenuSnapshot:
    """Load flows/runs/secrets/sync for the welcome panel (best-effort)."""
    from navbe.dependencies import (
        get_flow_service,
        get_run_service,
        get_secrets_service,
        get_sync_service,
    )

    flows = await get_flow_service().list()
    runs = await get_run_service().list_runs(None)
    secrets = get_secrets_service()
    keys = await secrets.list_keys()
    missing: list[str] = []
    for key in RECOMMENDED_KEYS:
        if not await secrets.has(key):
            missing.append(key)
    sync = await get_sync_service().status()
    active = [r for r in runs if r.status in _ACTIVE]
    paused = [r for r in runs if r.status == RunStatus.PAUSED]
    recent = runs[:8]
    failed_recent = sum(1 for r in recent if r.status == RunStatus.FAILED)
    return _MenuSnapshot(
        flow_count=len(flows),
        run_count=len(runs),
        active_runs=len(active),
        paused_runs=len(paused),
        failed_recent=failed_recent,
        secret_keys=len(keys),
        missing_recommended=tuple(missing),
        sync_configured=bool(sync.configured),
        sync_initialized=bool(sync.initialized),
        sync_branch=sync.branch,
        cwd=str(Path.cwd()),
    )


def _empty_snapshot() -> _MenuSnapshot:
    """Fallback when services are unavailable."""
    return _MenuSnapshot(
        flow_count=0,
        run_count=0,
        active_runs=0,
        paused_runs=0,
        failed_recent=0,
        secret_keys=0,
        missing_recommended=RECOMMENDED_KEYS,
        sync_configured=False,
        sync_initialized=False,
        sync_branch=None,
        cwd=str(Path.cwd()),
    )


def _smart_tip(snap: _MenuSnapshot) -> str:
    """Pick one next action from live workspace state."""
    if snap.paused_runs:
        return (
            f"{snap.paused_runs} run(s) paused on approval - "
            "/status <run_id> then resume via MCP flow_resume."
        )
    if snap.active_runs:
        return (
            f"{snap.active_runs} run(s) still active - "
            "type /watch to follow them live."
        )
    if snap.failed_recent:
        return (
            f"{snap.failed_recent} recent failure(s) - "
            "type /runs then /status <run_id> to inspect."
        )
    if snap.flow_count == 0:
        return (
            "No flows yet - connect an agent (navbe-mcp) and call flow_create, "
            "or sync pull if you use GitHub."
        )
    if snap.run_count == 0:
        return (
            f"{snap.flow_count} flow(s) ready - start a run from your agent "
            "(flow_run), then /watch here."
        )
    if snap.secret_keys == 0:
        return "No credentials stored yet - run /setup or: navbe secret set KEY"
    if "GITHUB_TOKEN" in snap.missing_recommended and not snap.sync_configured:
        return "Optional: store GITHUB_TOKEN then configure sync for GitHub flows."
    if snap.sync_configured and not snap.sync_initialized:
        return "Sync is configured but not initialized - run: navbe sync init"
    return (
        f"{snap.flow_count} flow(s), {snap.run_count} run(s) - "
        "type /flows or /runs to browse."
    )


def _metric_row(label: str, value: str, *, value_style: str = "white") -> Table:
    """One left-aligned label/value row."""
    row = Table.grid(expand=True, padding=(0, 1))
    row.add_column(style="dim", width=14)
    row.add_column(style=value_style)
    row.add_row(label, value)
    return row


def _status_panel(snap: _MenuSnapshot) -> Group:
    """Left pane: welcome + labeled metrics (stable column layout)."""
    name = _display_name()
    sync_bit = "off"
    if snap.sync_configured:
        branch = snap.sync_branch or "-"
        sync_bit = f"on ({branch})" if snap.sync_initialized else "configured"
    active_style = NAVBE_BLUE if snap.active_runs else "white"
    fail_style = "red" if snap.failed_recent else "white"
    return Group(
        Text(f"Welcome back {name}!", style="bold white"),
        Text(
            "Local-first flow orchestration - humans use this CLI, agents use navbe-mcp.",
            style="dim",
        ),
        Text(""),
        _metric_row("flows", str(snap.flow_count)),
        _metric_row("runs", str(snap.run_count)),
        _metric_row("secrets", str(snap.secret_keys)),
        _metric_row("active", str(snap.active_runs), value_style=active_style),
        _metric_row("failed", str(snap.failed_recent), value_style=fail_style),
        _metric_row("sync", sync_bit),
        Text(""),
        Text(snap.cwd, style="dim"),
    )


def _attention_panel(snap: _MenuSnapshot) -> Group:
    """Right lower pane: what needs attention right now."""
    lines: list[Text | str] = [
        Text("Needs attention", style=f"bold {NAVBE_BLUE}"),
    ]
    notes: list[str] = []
    if snap.paused_runs:
        notes.append(f"{snap.paused_runs} paused (HITL) - /runs")
    if snap.active_runs:
        notes.append(f"{snap.active_runs} in progress - /watch")
    if snap.failed_recent:
        notes.append(f"{snap.failed_recent} recent failures - /runs")
    if snap.flow_count == 0:
        notes.append("No flows - create via agent or sync")
    if snap.secret_keys == 0:
        notes.append("No secrets - /setup")
    elif snap.missing_recommended:
        shown = ", ".join(snap.missing_recommended[:2])
        more = "..." if len(snap.missing_recommended) > 2 else ""
        notes.append(f"Missing keys: {shown}{more}")
    if snap.sync_configured and not snap.sync_initialized:
        notes.append("Sync not initialized - navbe sync init")
    if not notes:
        notes.append("All clear")
    for note in notes[:4]:
        lines.append(Text(f"· {note}", style="white"))
    return Group(*lines)


def print_banner() -> None:
    """Print a compact Navbe banner (setup / non-interactive)."""
    _ensure_utf8_stdio()
    console.print(
        Panel(
            f"[bold {NAVBE_BLUE}]Navbe[/bold {NAVBE_BLUE}] - local-first flow orchestration\n"
            "[dim]Human ops console - agents use navbe-mcp[/dim]",
            border_style=NAVBE_BLUE,
            box=box.ROUNDED,
        )
    )


def print_main_menu() -> None:
    """Claude Code-style welcome with live workspace intelligence."""
    _ensure_utf8_stdio()
    try:
        snap = run_async(_load_snapshot())
    except Exception:
        snap = _empty_snapshot()

    left = Group(_status_panel(snap))
    tips = Group(
        Text("Suggested next step", style=f"bold {NAVBE_BLUE}"),
        Text(_smart_tip(snap), style="white"),
    )
    right = Group(
        tips,
        Text(""),
        Rule(style=NAVBE_BLUE),
        Text(""),
        _attention_panel(snap),
    )

    split = Table(
        expand=True,
        show_header=False,
        show_edge=False,
        box=box.MINIMAL,
        padding=(1, 2),
        border_style=NAVBE_BLUE,
        collapse_padding=True,
    )
    split.add_column(ratio=2, justify="left", vertical="middle")
    split.add_column(ratio=3, justify="left", vertical="middle")
    split.add_row(left, right)

    console.print(
        Panel(
            split,
            title=f"[bold {NAVBE_BLUE}]Navbe v{__version__}[/bold {NAVBE_BLUE}]",
            title_align="left",
            border_style=NAVBE_BLUE,
            box=box.ROUNDED,
            padding=(0, 0),
            width=min(max(console.width or 88, 72), 92),
        )
    )
    console.print(
        f"[dim]Type[/dim] [{NAVBE_BLUE}]/help[/{NAVBE_BLUE}] "
        f"[dim]for commands ·[/dim] [{NAVBE_BLUE}]/exit[/{NAVBE_BLUE}] "
        "[dim]to quit[/dim]"
    )
    console.print()


def print_quick_start() -> None:
    """Print numbered getting-started steps."""
    console.print(QUICK_START)


def section(title: str, number: int) -> None:
    """Print a numbered section header (agents-cli style)."""
    line = "-" * (len(title) + 3)
    console.print()
    console.print(f" [bold]{number}. {title}[/bold]")
    console.print(f" [dim]{line}[/dim]")


def find_repo_root(start: Path | None = None) -> Path | None:
    """Return navbe repo root if ``start`` is inside a checkout."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "src" / "navbe").is_dir():
            try:
                text = (candidate / "pyproject.toml").read_text(encoding="utf-8")
            except OSError:
                continue
            if 'name = "navbe"' in text:
                return candidate
    return None


def mcp_config_snippet(repo_root: Path) -> str:
    """Return a Claude/Cursor MCP JSON snippet for this checkout."""
    uv = shutil.which("uv") or "uv"
    snippet = {
        "navbe": {
            "command": uv,
            "args": ["run", "--directory", str(repo_root).replace("\\", "/"), "navbe-mcp"],
        }
    }
    return json.dumps(snippet, indent=2)


def python_version_ok() -> bool:
    """True when running Python 3.12+."""
    return sys.version_info >= (3, 12)


def ensure_data_dirs(flows_dir: Path, db_path: Path) -> list[str]:
    """Create default data dirs; return actions taken."""
    actions: list[str] = []
    for path in (flows_dir, db_path.parent):
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            actions.append(f"created {path}")
    return actions
