"""Helpers for connector execute payloads (direct or via http_request)."""

from typing import Any


def action_payload(payload: dict[str, Any], *keys: str) -> dict[str, Any]:
    """Return action fields from ``payload`` or nested ``body`` from http_request.

    If any of ``keys`` is present at the top level, use ``payload`` as-is.
    Otherwise prefer ``payload["body"]`` when it is a dict.
    """
    if keys and any(key in payload for key in keys):
        return payload
    body = payload.get("body")
    if isinstance(body, dict):
        return body
    return payload
