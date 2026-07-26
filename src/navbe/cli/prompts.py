"""Interactive CLI helpers (confirm, pause, spinners)."""

from __future__ import annotations

import typer
from rich.console import Console

from navbe.cli.daemon import read_serve_state

console = Console()


def serve_process_running() -> bool:
    """True when a detached ``navbe serve`` pidfile points at a live process."""
    state = read_serve_state()
    return state is not None and state.alive


def confirm(interactive: bool, message: str, *, default: bool = True) -> bool:
    """Ask yes/no when interactive; otherwise return ``default``."""
    if not interactive:
        return default
    return typer.confirm(message, default=default)


def pause(interactive: bool, message: str = "Press Enter to continue...") -> None:
    """Wait for Enter between setup sections when interactive."""
    if not interactive:
        return
    typer.echo(message, nl=False)
    try:
        input()
    except EOFError:
        typer.echo()


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
    opts = "/".join(options)
    while True:
        value = typer.prompt(f"{message} [{opts}]", default=default)
        lowered = value.strip().lower()
        for option in options:
            if option.lower() == lowered:
                return option
        typer.echo(f"Choose one of: {opts}", err=True)
