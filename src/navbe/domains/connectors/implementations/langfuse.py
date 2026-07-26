"""Langfuse Public API connector via httpx (no SDK).

Endpoints:
- test_connection / probe: GET /api/public/projects
- create: POST /api/public/ingestion
- read: GET /api/public/traces or /api/public/traces/{trace_id}
- update / delete: unsupported (fail loud)
"""

from typing import Any

import httpx

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.implementations._payload import action_payload
from navbe.domains.connectors.interfaces import ConnectorConfig
from navbe.domains.connectors.registry import ConnectorRegistry


class LangfuseConfig(ConnectorConfig):
    """Langfuse host + public/secret keys (use ``$secret`` for keys)."""

    host: str
    public_key: str
    secret_key: str
    timeout: int = 30


@ConnectorRegistry.register("langfuse")
class LangfuseConnector:
    """CRUD-shaped wrappers over Langfuse Public API."""

    config_schema = LangfuseConfig
    actions = {
        "create": "POST /api/public/ingestion",
        "read": "GET /api/public/traces",
        "update": "Unsupported — raises ExecutionError",
        "delete": "Unsupported — raises ExecutionError",
    }

    def __init__(self, config: dict[str, Any]) -> None:
        """Validate config and store Basic-auth credentials."""
        self.config = LangfuseConfig.model_validate(config)
        self._host = self.config.host.rstrip("/")
        self._auth = (self.config.public_key, self.config.secret_key)

    async def test_connection(self) -> bool:
        """Return True when GET /api/public/projects succeeds."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self._host}/api/public/projects",
                    auth=self._auth,
                )
                return resp.status_code < 500 and resp.status_code != 401
        except httpx.HTTPError:
            return False

    async def execute(self, action: str, payload: dict[str, Any]) -> Any:
        """Run a Langfuse Public API action."""
        if action not in self.actions:
            raise ExecutionError(
                f"Unsupported action '{action}' for langfuse connector",
                details={"action": action, "available": list(self.actions)},
            )
        if action in ("update", "delete"):
            raise ExecutionError(
                f"langfuse '{action}' is not supported by the Public API wrapper",
                details={"action": action},
            )
        fields = action_payload(payload, "trace_id", "batch", "body")

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                if action == "create":
                    body = fields.get("batch") or fields.get("body") or fields
                    resp = await client.post(
                        f"{self._host}/api/public/ingestion",
                        auth=self._auth,
                        json=body,
                    )
                else:
                    trace_id = fields.get("trace_id")
                    path = (
                        f"{self._host}/api/public/traces/{trace_id}"
                        if trace_id
                        else f"{self._host}/api/public/traces"
                    )
                    params = {
                        k: v
                        for k, v in fields.items()
                        if k not in ("trace_id", "batch", "body", "path") and v is not None
                    }
                    resp = await client.get(path, auth=self._auth, params=params or None)
                resp.raise_for_status()
                if not resp.content:
                    return {}
                return resp.json()
        except httpx.HTTPStatusError as exc:
            raise ExecutionError(
                f"langfuse request failed with status {exc.response.status_code}",
                details={"action": action, "status_code": exc.response.status_code},
            ) from exc
        except httpx.HTTPError as exc:
            raise ExecutionError(
                "langfuse request failed",
                details={"action": action},
            ) from exc
