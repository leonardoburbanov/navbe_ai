"""MCP tool error adaptation for Navbe domain exceptions."""

import json
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from fastmcp.exceptions import ToolError

from navbe.core.exceptions import NavbeError


def navbe_error_to_tool_error(exc: NavbeError) -> ToolError:
    """Convert a NavbeError into FastMCP's client-visible ToolError."""
    payload = {
        "error": True,
        "code": exc.code,
        "message": exc.message,
        "details": exc.details,
    }
    return ToolError(json.dumps(payload))


def parse_tool_error(exc: ToolError) -> dict[str, Any]:
    """Parse a ToolError raised by ``mcp_tool_error_handler`` into a dict."""
    return json.loads(str(exc))


def mcp_tool_error_handler[R](
    func: Callable[..., Awaitable[R]],
) -> Callable[..., Awaitable[R]]:
    """Wrap a tool so NavbeError becomes FastMCP ToolError (structured JSON)."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> R:
        try:
            return await func(*args, **kwargs)
        except NavbeError as exc:
            raise navbe_error_to_tool_error(exc) from exc

    return wrapper
