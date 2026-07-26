"""Supabase PostgREST connector via httpx (no supabase-py)."""

from typing import Any

import httpx

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.implementations._payload import action_payload
from navbe.domains.connectors.interfaces import ConnectorConfig
from navbe.domains.connectors.registry import ConnectorRegistry


class SupabaseConfig(ConnectorConfig):
    """Supabase project URL + service role key (key via ``$secret``)."""

    url: str
    service_role_key: str
    timeout: int = 30


@ConnectorRegistry.register("supabase")
class SupabaseConnector:
    """CRUD against PostgREST ``/rest/v1/{table}``."""

    config_schema = SupabaseConfig
    actions = {
        "create": "POST insert",
        "read": "GET select",
        "update": "PATCH update",
        "delete": "DELETE",
    }

    def __init__(self, config: dict[str, Any]) -> None:
        """Validate config and build PostgREST headers."""
        self.config = SupabaseConfig.model_validate(config)
        self._base = self.config.url.rstrip("/")
        self._headers = {
            "apikey": self.config.service_role_key,
            "Authorization": f"Bearer {self.config.service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def test_connection(self) -> bool:
        """Return True when the Auth health endpoint responds non-401/5xx."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self._base}/auth/v1/health",
                    headers={"apikey": self.config.service_role_key},
                )
                return resp.status_code < 500 and resp.status_code != 401
        except httpx.HTTPError:
            return False

    def _filters(self, filters: dict[str, Any] | None) -> dict[str, str]:
        if not filters:
            return {}
        # PostgREST: col=eq.value
        out: dict[str, str] = {}
        for key, value in filters.items():
            if isinstance(value, str) and "=" in value:
                out[str(key)] = value
            else:
                out[str(key)] = f"eq.{value}"
        return out

    async def execute(self, action: str, payload: dict[str, Any]) -> Any:
        """Run a PostgREST CRUD action."""
        if action not in self.actions:
            raise ExecutionError(
                f"Unsupported action '{action}' for supabase connector",
                details={"action": action, "available": list(self.actions)},
            )
        fields = action_payload(payload, "table", "row", "rows", "filters", "prefer")
        table = fields.get("table")
        if not table:
            raise ExecutionError(
                "supabase actions require table",
                details={"field": "table"},
            )
        headers = dict(self._headers)
        if fields.get("prefer"):
            headers["Prefer"] = str(fields["prefer"])
        url = f"{self._base}/rest/v1/{table}"

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                if action == "create":
                    body = fields.get("rows") or fields.get("row")
                    if body is None:
                        raise ExecutionError(
                            "create requires row or rows",
                            details={"fields": ["row", "rows"]},
                        )
                    resp = await client.post(url, headers=headers, json=body)
                elif action == "read":
                    resp = await client.get(
                        url,
                        headers=headers,
                        params=self._filters(fields.get("filters")),
                    )
                elif action == "update":
                    body = fields.get("row") or fields.get("rows")
                    if body is None:
                        raise ExecutionError(
                            "update requires row",
                            details={"field": "row"},
                        )
                    resp = await client.patch(
                        url,
                        headers=headers,
                        params=self._filters(fields.get("filters")),
                        json=body,
                    )
                else:
                    resp = await client.delete(
                        url,
                        headers=headers,
                        params=self._filters(fields.get("filters")),
                    )
                resp.raise_for_status()
                if not resp.content:
                    return {}
                return resp.json()
        except ExecutionError:
            raise
        except httpx.HTTPStatusError as exc:
            raise ExecutionError(
                f"supabase request failed with status {exc.response.status_code}",
                details={"action": action, "table": table, "status_code": exc.response.status_code},
            ) from exc
        except httpx.HTTPError as exc:
            raise ExecutionError(
                "supabase request failed",
                details={"action": action, "table": table},
            ) from exc
