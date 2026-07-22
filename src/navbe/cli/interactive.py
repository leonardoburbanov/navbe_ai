"""Interactive slash-command ops session (Claude Code / Antigravity-style)."""

from __future__ import annotations

import shlex
import sys
from collections.abc import Callable
from dataclasses import dataclass

from rich.table import Table

from navbe import __version__
from navbe.cli.actions import (
    list_flows,
    list_runs,
    list_secret_keys,
    list_steps,
    run_setup,
    serve_hint,
    show_info,
    show_run_status,
    show_sync,
    watch_runs,
)
from navbe.cli.format import console
from navbe.cli.onboarding import print_banner
from navbe.core.exceptions import NavbeError


@dataclass(frozen=True)
class SlashCommand:
    """One slash command in the interactive registry."""

    name: str
    help: str
    handler: Callable[[list[str]], None]


def _cmd_help(_args: list[str]) -> None:
    """Print available slash commands."""
    table = Table(title="Slash commands", show_header=True)
    table.add_column("command")
    table.add_column("description")
    for cmd in COMMANDS:
        table.add_row(f"/{cmd.name}", cmd.help)
    console.print(table)


def _cmd_info(args: list[str]) -> None:
    show_info(as_json="--json" in args)


def _cmd_flows(_args: list[str]) -> None:
    list_flows()


def _cmd_runs(args: list[str]) -> None:
    flow_id = args[0] if args else None
    list_runs(flow_id)


def _cmd_watch(args: list[str]) -> None:
    run_id = args[0] if args else None
    watch_runs(run_id)


def _cmd_status(args: list[str]) -> None:
    if not args:
        console.print("[red]Usage:[/red] /status <run_id>")
        return
    show_run_status(args[0])


def _cmd_steps(_args: list[str]) -> None:
    list_steps()


def _cmd_secrets(_args: list[str]) -> None:
    list_secret_keys()


def _cmd_sync(_args: list[str]) -> None:
    show_sync()


def _cmd_setup(_args: list[str]) -> None:
    run_setup()


def _cmd_serve(_args: list[str]) -> None:
    serve_hint()


def _cmd_exit(_args: list[str]) -> None:
    raise SystemExit(0)


COMMANDS: list[SlashCommand] = [
    SlashCommand("help", "List commands", _cmd_help),
    SlashCommand("info", "Paths, credentials, sync readiness", _cmd_info),
    SlashCommand("flows", "List all flows", _cmd_flows),
    SlashCommand("runs", "List all runs (optional: /runs <flow_id>)", _cmd_runs),
    SlashCommand("watch", "Live watch all runs (or /watch <run_id>)", _cmd_watch),
    SlashCommand("status", "One-shot run status (/status <run_id>)", _cmd_status),
    SlashCommand("steps", "List step types", _cmd_steps),
    SlashCommand("secrets", "List secret keys (never values)", _cmd_secrets),
    SlashCommand("sync", "Sync status", _cmd_sync),
    SlashCommand("setup", "Interactive onboarding walkthrough", _cmd_setup),
    SlashCommand("serve", "How to start HTTP API (does not block)", _cmd_serve),
    SlashCommand("exit", "Quit the session", _cmd_exit),
]

_BY_NAME = {cmd.name: cmd for cmd in COMMANDS}


def _dispatch(line: str) -> None:
    """Parse and run one slash line."""
    text = line.strip()
    if not text:
        return
    if not text.startswith("/"):
        console.print("[dim]Commands start with / — try[/dim] [cyan]/help[/cyan]")
        return
    try:
        parts = shlex.split(text[1:])
    except ValueError as exc:
        console.print(f"[red]Bad input:[/red] {exc}")
        return
    if not parts:
        _cmd_help([])
        return
    name, args = parts[0].lower(), parts[1:]
    if name in {"quit", "q"}:
        name = "exit"
    cmd = _BY_NAME.get(name)
    if cmd is None:
        console.print(f"[red]Unknown:[/red] /{name}  — try [cyan]/help[/cyan]")
        return
    cmd.handler(args)


def run_session() -> None:
    """Banner + slash REPL until /exit or Ctrl+D."""
    print_banner()
    console.print(f"[dim]Navbe v{__version__} · interactive ops[/dim]")
    console.print(
        "[dim]Type[/dim] [cyan]/help[/cyan] [dim]· Ctrl+C cancels watch ·[/dim] "
        "[cyan]/exit[/cyan] [dim]to quit[/dim]"
    )
    console.print()

    while True:
        try:
            line = input("navbe> ")
        except EOFError:
            console.print()
            break
        except KeyboardInterrupt:
            console.print("\n[dim]Use /exit to quit.[/dim]")
            continue
        try:
            _dispatch(line)
        except SystemExit as exc:
            if exc.code in (0, None):
                break
            continue
        except NavbeError as exc:
            console.print(f"[red]Error [{exc.code}]:[/red] {exc.message}")
            if exc.details:
                console.print(exc.details)


def should_start_interactive() -> bool:
    """True when stdin is a TTY (safe to open a REPL)."""
    return sys.stdin.isatty()
