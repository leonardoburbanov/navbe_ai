"""Google Calendar connector via httpx (refresh token; no Google SDK)."""

from typing import Any

import httpx

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.implementations._payload import action_payload
from navbe.domains.connectors.interfaces import ConnectorConfig
from navbe.domains.connectors.registry import ConnectorRegistry

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_CALENDAR_BASE = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarConfig(ConnectorConfig):
    """OAuth client credentials + refresh token (all ``$secret``-able)."""

    client_id: str
    client_secret: str
    refresh_token: str
    timeout: int = 30


@ConnectorRegistry.register("google_calendar")
class GoogleCalendarConnector:
    """CRUD for Calendar events using a stored OAuth refresh token."""

    config_schema = GoogleCalendarConfig
    actions = {
        "create": "Insert calendar event",
        "read": "Get or list calendar events",
        "update": "Patch calendar event",
        "delete": "Delete calendar event",
    }

    def __init__(self, config: dict[str, Any]) -> None:
        """Validate Google Calendar OAuth config."""
        self.config = GoogleCalendarConfig.model_validate(config)

    async def _access_token(self, client: httpx.AsyncClient) -> str:
        """Exchange refresh_token for a short-lived access token."""
        resp = await client.post(
            _TOKEN_URL,
            data={
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "refresh_token": self.config.refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise ExecutionError(
                "google_calendar token refresh returned no access_token",
                details={},
            )
        return str(token)

    async def test_connection(self) -> bool:
        """Return True when token refresh + calendarList works."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                token = await self._access_token(client)
                resp = await client.get(
                    f"{_CALENDAR_BASE}/users/me/calendarList",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"maxResults": 1},
                )
                return resp.status_code < 500 and resp.status_code != 401
        except (httpx.HTTPError, ExecutionError):
            return False

    async def execute(self, action: str, payload: dict[str, Any]) -> Any:
        """Run a calendar event CRUD action."""
        if action not in self.actions:
            raise ExecutionError(
                f"Unsupported action '{action}' for google_calendar connector",
                details={"action": action, "available": list(self.actions)},
            )
        fields = action_payload(
            payload, "calendar_id", "event_id", "event", "timeMin", "timeMax", "maxResults"
        )
        calendar_id = fields.get("calendar_id") or "primary"
        base = f"{_CALENDAR_BASE}/calendars/{calendar_id}/events"

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                token = await self._access_token(client)
                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                if action == "create":
                    event = fields.get("event") or {
                        k: v
                        for k, v in fields.items()
                        if k not in ("calendar_id", "event_id", "path", "params")
                    }
                    resp = await client.post(base, headers=headers, json=event)
                elif action == "read":
                    event_id = fields.get("event_id")
                    if event_id:
                        resp = await client.get(f"{base}/{event_id}", headers=headers)
                    else:
                        params = {
                            k: fields[k]
                            for k in ("timeMin", "timeMax", "maxResults", "q", "pageToken")
                            if fields.get(k) is not None
                        }
                        resp = await client.get(base, headers=headers, params=params or None)
                elif action == "update":
                    event_id = fields.get("event_id")
                    event = fields.get("event")
                    if not event_id or not isinstance(event, dict):
                        raise ExecutionError(
                            "update requires event_id and event",
                            details={"fields": ["event_id", "event"]},
                        )
                    resp = await client.patch(f"{base}/{event_id}", headers=headers, json=event)
                else:
                    event_id = fields.get("event_id")
                    if not event_id:
                        raise ExecutionError(
                            "delete requires event_id",
                            details={"field": "event_id"},
                        )
                    resp = await client.delete(f"{base}/{event_id}", headers=headers)
                resp.raise_for_status()
                if not resp.content:
                    return {}
                return resp.json()
        except ExecutionError:
            raise
        except httpx.HTTPStatusError as exc:
            raise ExecutionError(
                f"google_calendar request failed with status {exc.response.status_code}",
                details={"action": action, "status_code": exc.response.status_code},
            ) from exc
        except httpx.HTTPError as exc:
            raise ExecutionError(
                "google_calendar request failed",
                details={"action": action},
            ) from exc
