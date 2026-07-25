"""Resend email API connector (API key from credentials via ``$secret``)."""

from typing import Any

import httpx

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.interfaces import ConnectorConfig
from navbe.domains.connectors.registry import ConnectorRegistry

_RESEND_BASE_URL = "https://api.resend.com"


class ResendConfig(ConnectorConfig):
    """Configuration for a Resend connector.

    Set ``api_key`` to ``{"$secret": "RESEND_API_KEY"}`` in the FlowSpec.
    Store the value with ``secret_set`` / ``navbe secret set RESEND_API_KEY --app resend``.
    """

    api_key: str
    timeout: int = 30


@ConnectorRegistry.register("resend")
class ResendConnector:
    """HTTP client for api.resend.com; auth from resolved ``api_key`` (never env)."""

    config_schema = ResendConfig
    actions = {
        "get": "GET request",
        "post": "POST request (e.g. /emails)",
        "put": "PUT request",
        "delete": "DELETE request",
    }

    def __init__(self, config: dict[str, Any]) -> None:
        """Validate config and build Bearer auth headers from ``api_key``."""
        self.config = ResendConfig.model_validate(config)
        self._headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    async def test_connection(self) -> bool:
        """Return True when Resend accepts the API key (GET /domains or /api-keys)."""
        try:
            async with httpx.AsyncClient(
                base_url=_RESEND_BASE_URL,
                headers=self._headers,
                timeout=5,
            ) as client:
                # Lightweight authenticated probe; 401/403 → False.
                resp = await client.get("/domains")
                return resp.status_code < 500 and resp.status_code != 401
        except httpx.HTTPError:
            return False

    async def execute(self, action: str, payload: dict[str, Any]) -> Any:
        """Execute an HTTP action against api.resend.com."""
        if action not in self.actions:
            raise ExecutionError(
                f"Unsupported action '{action}' for resend connector",
                details={"action": action, "available": list(self.actions)},
            )

        try:
            async with httpx.AsyncClient(
                base_url=_RESEND_BASE_URL,
                headers=self._headers,
                timeout=self.config.timeout,
            ) as client:
                resp = await client.request(
                    action.upper(),
                    payload.get("path", ""),
                    json=payload.get("body"),
                    params=payload.get("params"),
                )
                resp.raise_for_status()
                if not resp.content:
                    return {}
                return resp.json()
        except httpx.HTTPStatusError as exc:
            raise ExecutionError(
                f"Resend request failed with status {exc.response.status_code}",
                details={
                    "action": action,
                    "path": payload.get("path", ""),
                    "status_code": exc.response.status_code,
                },
            ) from exc
        except httpx.HTTPError as exc:
            raise ExecutionError(
                "Resend request failed",
                details={"action": action, "path": payload.get("path", "")},
            ) from exc
