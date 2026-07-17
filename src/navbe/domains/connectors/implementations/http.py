"""HTTP connector implementation."""

from typing import Any

import httpx

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.interfaces import ConnectorConfig
from navbe.domains.connectors.registry import ConnectorRegistry


class HTTPConfig(ConnectorConfig):
    """Configuration for an HTTP connector."""

    base_url: str
    headers: dict[str, str] = {}
    timeout: int = 30


@ConnectorRegistry.register("http")
class HTTPConnector:
    """Connector that performs HTTP requests against a base URL."""

    config_schema = HTTPConfig
    actions = {
        "get": "GET request",
        "post": "POST request",
        "put": "PUT request",
        "delete": "DELETE request",
    }

    def __init__(self, config: dict[str, Any]) -> None:
        """Validate and store HTTP connector config."""
        self.config = HTTPConfig.model_validate(config)

    async def test_connection(self) -> bool:
        """Return True when the base URL responds with a non-5xx status."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(self.config.base_url)
                return resp.status_code < 500
        except httpx.HTTPError:
            return False

    async def execute(self, action: str, payload: dict[str, Any]) -> Any:
        """Execute an HTTP action against the configured base URL."""
        if action not in self.actions:
            raise ExecutionError(
                f"Unsupported action '{action}' for http connector",
                details={"action": action, "available": list(self.actions)},
            )

        try:
            async with httpx.AsyncClient(
                base_url=self.config.base_url,
                headers=self.config.headers,
                timeout=self.config.timeout,
            ) as client:
                resp = await client.request(
                    action.upper(),
                    payload.get("path", ""),
                    json=payload.get("body"),
                    params=payload.get("params"),
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            raise ExecutionError(
                f"HTTP connector request failed with status {exc.response.status_code}",
                details={
                    "action": action,
                    "path": payload.get("path", ""),
                    "status_code": exc.response.status_code,
                },
            ) from exc
        except httpx.HTTPError as exc:
            raise ExecutionError(
                "HTTP connector request failed",
                details={"action": action, "path": payload.get("path", "")},
            ) from exc
