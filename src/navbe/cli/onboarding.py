"""Shared onboarding copy, banner, and path helpers."""

from __future__ import annotations

import getpass
import json
import shutil
import sys
from pathlib import Path

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from navbe import __version__

# UTF-8 + modern Windows console so box-drawing / ship glyphs render.
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

# Compact Navbe spaceship mark (brand blue).
_SPACESHIP = f"""\
[{NAVBE_BLUE}]          .
         /|\\
        /_|_\\
       | o o |
       |__V__|
      //|||||\\\\
     *' ^^^ '*[/{NAVBE_BLUE}]"""


def _ensure_utf8_stdio() -> None:
    """Prefer UTF-8 so the welcome ship and box borders render on Windows."""
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
    """Claude Code-style welcome: title in border, two panes, spaceship mark."""
    _ensure_utf8_stdio()
    name = _display_name()
    cwd = str(Path.cwd())

    left = Align.center(
        Group(
            Text(f"Welcome back {name}!", style="bold white", justify="center"),
            Text(""),
            Text.from_markup(_SPACESHIP, justify="center"),
            Text(""),
            Text(
                "local-first ops · Typer CLI · MCP for agents",
                style="dim",
                justify="center",
            ),
            Text(cwd, style="dim", justify="center"),
        ),
        vertical="middle",
    )

    tips = Group(
        Text("Tips for getting started", style=f"bold {NAVBE_BLUE}"),
        Text(
            "Run /setup to onboard, then /flows and /runs to explore.",
            style="white",
        ),
    )
    whats_new = Group(
        Text("What's new", style=f"bold {NAVBE_BLUE}"),
        Text(
            "Interactive slash menu with live /watch across all runs",
            style="white",
        ),
        Text(
            "navbe flows list / runs list without needing IDs first",
            style="white",
        ),
        Text(
            "Human CLI on Typer; agents keep using navbe-mcp",
            style="white",
        ),
        Text(""),
        Text("/help for more", style="dim italic"),
    )
    right = Group(tips, Text(""), Rule(style=NAVBE_BLUE), Text(""), whats_new)

    # Vertical divider pane split (Claude Code layout).
    split = Table(
        expand=True,
        show_header=False,
        show_edge=False,
        box=box.MINIMAL,
        padding=(1, 2),
        border_style=NAVBE_BLUE,
        collapse_padding=True,
    )
    split.add_column(ratio=1, justify="center", vertical="middle")
    split.add_column(ratio=1, justify="left", vertical="middle")
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
