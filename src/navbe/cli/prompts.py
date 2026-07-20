"""Interactive CLI helpers (confirm, pause, spinners)."""

from __future__ import annotations

import subprocess
import sys

import click
from rich.console import Console

console = Console()


def mcp_process_count() -> int:
    """Return how many ``navbe-mcp`` processes appear to be running."""
    if sys.platform == "win32":
        proc = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq navbe-mcp.exe", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.stdout.lower().count("navbe-mcp.exe")
    proc = subprocess.run(
        ["pgrep", "-fc", "navbe-mcp"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in (0, 1):
        return 0
    try:
        return int(proc.stdout.strip() or "0")
    except ValueError:
        return 0


def confirm(interactive: bool, message: str, *, default: bool = True) -> bool:
    """Ask yes/no when interactive; otherwise return ``default``."""
    if not interactive:
        return default
    return click.confirm(message, default=default)


def pause(interactive: bool, message: str = "Press Enter to continue...") -> None:
    """Wait for Enter between setup sections when interactive."""
    if not interactive:
        return
    click.pause(info=message)


def choice(
    interactive: bool,
    message: str,
    options: list[str],
    *,
    default: str,
) -> str:
    """Pick one of ``options`` when interactive; otherwise return ``default``."""
    if not interactive:
        return default
    return click.prompt(
        message,
        type=click.Choice(options, case_sensitive=False),
        default=default,
        show_choices=True,
    )
