"""Map NavbeError to exit codes and human-readable stderr."""

from __future__ import annotations

import json
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any

import typer

from navbe.core.exceptions import NavbeError


def handle_navbe_errors[T](fn: Callable[..., T]) -> Callable[..., T]:
    """Print structured Navbe errors and exit with code 1."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        try:
            return fn(*args, **kwargs)
        except NavbeError as exc:
            typer.echo(f"Error [{exc.code}]: {exc.message}", err=True)
            if exc.details:
                typer.echo(json.dumps(exc.details, indent=2), err=True)
            raise SystemExit(1) from exc

    return wrapper


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine from a sync Typer command."""
    import asyncio

    return asyncio.run(coro)
