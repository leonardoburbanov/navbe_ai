"""Pinecone data-plane connector via httpx (no Pinecone SDK)."""

from typing import Any

import httpx

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.implementations._payload import action_payload
from navbe.domains.connectors.interfaces import ConnectorConfig
from navbe.domains.connectors.registry import ConnectorRegistry


class PineconeConfig(ConnectorConfig):
    """Pinecone index host + API key (key via ``$secret``)."""

    api_key: str
    host: str
    timeout: int = 30


@ConnectorRegistry.register("pinecone")
class PineconeConnector:
    """Domain CRUD: create/update=upsert, read=fetch|query, delete=delete."""

    config_schema = PineconeConfig
    actions = {
        "create": "Upsert vectors",
        "read": "Fetch by ids or query by vector",
        "update": "Upsert vectors",
        "delete": "Delete by ids or filter",
    }

    def __init__(self, config: dict[str, Any]) -> None:
        """Validate config and build data-plane headers."""
        self.config = PineconeConfig.model_validate(config)
        host = self.config.host
        if not host.startswith("http"):
            host = f"https://{host}"
        self._base = host.rstrip("/")
        self._headers = {
            "Api-Key": self.config.api_key,
            "Content-Type": "application/json",
        }

    async def test_connection(self) -> bool:
        """Return True when describe_index_stats succeeds."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.post(
                    f"{self._base}/describe_index_stats",
                    headers=self._headers,
                    json={},
                )
                return resp.status_code < 500 and resp.status_code != 401
        except httpx.HTTPError:
            return False

    async def execute(self, action: str, payload: dict[str, Any]) -> Any:
        """Run a Pinecone data-plane action."""
        if action not in self.actions:
            raise ExecutionError(
                f"Unsupported action '{action}' for pinecone connector",
                details={"action": action, "available": list(self.actions)},
            )
        fields = action_payload(
            payload, "vectors", "ids", "vector", "filter", "namespace", "top_k", "topK"
        )

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                if action in ("create", "update"):
                    body = {
                        k: fields[k]
                        for k in ("vectors", "namespace")
                        if fields.get(k) is not None
                    }
                    if "vectors" not in body:
                        raise ExecutionError(
                            f"{action} requires vectors",
                            details={"field": "vectors"},
                        )
                    resp = await client.post(
                        f"{self._base}/vectors/upsert",
                        headers=self._headers,
                        json=body,
                    )
                elif action == "read":
                    use_query = (
                        fields.get("vector") is not None
                        or fields.get("top_k")
                        or fields.get("topK")
                    )
                    if use_query:
                        body = {
                            "vector": fields.get("vector"),
                            "topK": fields.get("topK") or fields.get("top_k") or 10,
                        }
                        for key in ("namespace", "filter", "includeMetadata", "includeValues"):
                            if fields.get(key) is not None:
                                body[key] = fields[key]
                        resp = await client.post(
                            f"{self._base}/query",
                            headers=self._headers,
                            json=body,
                        )
                    else:
                        body = {"ids": fields.get("ids") or []}
                        if fields.get("namespace") is not None:
                            body["namespace"] = fields["namespace"]
                        if not body["ids"]:
                            raise ExecutionError(
                                "read requires ids or vector(+top_k)",
                                details={"fields": ["ids", "vector"]},
                            )
                        resp = await client.post(
                            f"{self._base}/vectors/fetch",
                            headers=self._headers,
                            json=body,
                        )
                else:
                    body = {
                        k: fields[k]
                        for k in ("ids", "filter", "namespace", "deleteAll")
                        if fields.get(k) is not None
                    }
                    if not body.get("ids") and not body.get("filter") and not body.get("deleteAll"):
                        raise ExecutionError(
                            "delete requires ids, filter, or deleteAll",
                            details={"fields": ["ids", "filter", "deleteAll"]},
                        )
                    resp = await client.post(
                        f"{self._base}/vectors/delete",
                        headers=self._headers,
                        json=body,
                    )
                resp.raise_for_status()
                if not resp.content:
                    return {}
                return resp.json()
        except ExecutionError:
            raise
        except httpx.HTTPStatusError as exc:
            raise ExecutionError(
                f"pinecone request failed with status {exc.response.status_code}",
                details={"action": action, "status_code": exc.response.status_code},
            ) from exc
        except httpx.HTTPError as exc:
            raise ExecutionError(
                "pinecone request failed",
                details={"action": action},
            ) from exc
