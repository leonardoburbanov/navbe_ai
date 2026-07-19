"""Tests for mcp_tool_error_handler."""

import pytest
from fastmcp.exceptions import ToolError

from navbe.core.exceptions import NotFoundError, ValidationError
from navbe.mcp_app.errors import mcp_tool_error_handler, parse_tool_error


@mcp_tool_error_handler
async def _ok() -> dict:
    return {"ok": True}


@mcp_tool_error_handler
async def _validation() -> dict:
    raise ValidationError("bad input", details={"issues": [{"code": "x"}]})


@mcp_tool_error_handler
async def _missing() -> dict:
    raise NotFoundError("gone", details={"id": "1"})


@mcp_tool_error_handler
async def _bug() -> dict:
    raise RuntimeError("real bug")


async def test_wrapper_passes_through_success() -> None:
    """Decorated success path is unchanged."""
    assert await _ok() == {"ok": True}


async def test_wrapper_converts_validation_error() -> None:
    """ValidationError becomes ToolError with structured JSON payload."""
    with pytest.raises(ToolError) as exc_info:
        await _validation()
    payload = parse_tool_error(exc_info.value)
    assert payload["error"] is True
    assert payload["code"] == "validation_error"
    assert payload["details"]["issues"] == [{"code": "x"}]


async def test_wrapper_converts_not_found_error() -> None:
    """NotFoundError becomes ToolError with code not_found."""
    with pytest.raises(ToolError) as exc_info:
        await _missing()
    payload = parse_tool_error(exc_info.value)
    assert payload["code"] == "not_found"
    assert payload["details"]["id"] == "1"


async def test_wrapper_does_not_swallow_non_navbe_exceptions() -> None:
    """Bare RuntimeError propagates for loud development failures."""
    with pytest.raises(RuntimeError, match="real bug"):
        await _bug()
