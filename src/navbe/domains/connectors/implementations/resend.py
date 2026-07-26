"""Resend email connector — exclusive ``send_email`` action (not generic HTTP)."""

from typing import Any

import httpx

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.implementations._payload import action_payload
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
    """Send email via api.resend.com; auth from resolved ``api_key`` (never env)."""

    config_schema = ResendConfig
    actions = {
        "send_email": "Send an email via Resend POST /emails",
    }

    def __init__(self, config: dict[str, Any]) -> None:
        """Validate config and build Bearer auth headers from ``api_key``."""
        self.config = ResendConfig.model_validate(config)
        self._headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    async def test_connection(self) -> bool:
        """Return True when Resend accepts the API key (GET /domains)."""
        try:
            async with httpx.AsyncClient(
                base_url=_RESEND_BASE_URL,
                headers=self._headers,
                timeout=5,
            ) as client:
                resp = await client.get("/domains")
                return resp.status_code < 500 and resp.status_code != 401
        except httpx.HTTPError:
            return False

    async def execute(self, action: str, payload: dict[str, Any]) -> Any:
        """Send an email; only ``send_email`` is supported."""
        if action not in self.actions:
            raise ExecutionError(
                f"Unsupported action '{action}' for resend connector",
                details={"action": action, "available": list(self.actions)},
            )

        fields = action_payload(payload, "from", "to", "subject", "html", "text")
        missing = [k for k in ("from", "to", "subject") if not fields.get(k)]
        if missing:
            raise ExecutionError(
                "send_email requires from, to, and subject",
                details={"missing": missing},
            )
        if not fields.get("html") and not fields.get("text"):
            raise ExecutionError(
                "send_email requires html or text",
                details={"fields": ["html", "text"]},
            )

        body: dict[str, Any] = {
            "from": fields["from"],
            "to": fields["to"] if isinstance(fields["to"], list) else [fields["to"]],
            "subject": fields["subject"],
        }
        if fields.get("html"):
            body["html"] = fields["html"]
        if fields.get("text"):
            body["text"] = fields["text"]
        for optional in ("cc", "bcc", "reply_to"):
            if fields.get(optional) is not None:
                body[optional] = fields[optional]

        try:
            async with httpx.AsyncClient(
                base_url=_RESEND_BASE_URL,
                headers=self._headers,
                timeout=self.config.timeout,
            ) as client:
                resp = await client.post("/emails", json=body)
                resp.raise_for_status()
                if not resp.content:
                    return {}
                return resp.json()
        except httpx.HTTPStatusError as exc:
            raise ExecutionError(
                f"Resend send_email failed with status {exc.response.status_code}",
                details={"action": action, "status_code": exc.response.status_code},
            ) from exc
        except httpx.HTTPError as exc:
            raise ExecutionError(
                "Resend send_email failed",
                details={"action": action},
            ) from exc
