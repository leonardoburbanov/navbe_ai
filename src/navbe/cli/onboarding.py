"""Shared onboarding copy, banner, and path helpers."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

console = Console()

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


def print_banner() -> None:
    """Print Navbe welcome banner."""
    console.print(
        Panel(
            "[bold cyan]Navbe[/bold cyan] — local-first flow orchestration\n"
            "[dim]Human ops console · agents use navbe-mcp[/dim]",
            border_style="cyan",
        )
    )


def print_quick_start() -> None:
    """Print numbered getting-started steps."""
    console.print(QUICK_START)


def section(title: str, number: int) -> None:
    """Print a numbered section header (agents-cli style)."""
    line = "─" * (len(title) + 3)
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
