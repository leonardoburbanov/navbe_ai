"""Resend-backed failure email notifier."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from navbe.domains.schedules.models import ScheduleSpec
from navbe.domains.secrets.models import is_secret_ref, parse_secret_ref
from navbe.domains.secrets.service import SecretsService

logger = logging.getLogger(__name__)

_RESEND_EMAILS_URL = "https://api.resend.com/emails"


class ResendFailureNotifier:
    """Send schedule-failure emails via Resend using a ``$secret`` API key."""

    def __init__(self, secrets_service: SecretsService) -> None:
        """Bind to the secrets service for API key resolution."""
        self._secrets = secrets_service

    async def notify_failure(
        self,
        *,
        schedule: ScheduleSpec,
        error: str | None,
        failure_count: int,
    ) -> None:
        """POST a failure email; log and return on errors (never raise)."""
        notify = schedule.notify
        if notify is None or notify.channel != "email":
            return

        try:
            api_key = await self._resolve_api_key(notify.api_key)
        except Exception:
            logger.exception(
                "Could not resolve Resend API key for schedule '%s'",
                schedule.schedule_id,
            )
            return

        subject = (
            f"[Navbe] Schedule '{schedule.schedule_id}' failed "
            f"({failure_count}x)"
        )
        body = (
            f"Schedule: {schedule.schedule_id}\n"
            f"Flow: {schedule.flow_id}\n"
            f"Consecutive failures: {failure_count}\n"
            f"Last error: {error or '(none)'}\n"
            f"Last run: {schedule.last_run_id or '(none)'}\n"
        )
        payload = {
            "from": notify.from_addr,
            "to": [notify.to],
            "subject": subject,
            "text": body,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    _RESEND_EMAILS_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if resp.status_code >= 400:
                    logger.error(
                        "Resend notify failed for schedule '%s': %s %s",
                        schedule.schedule_id,
                        resp.status_code,
                        resp.text,
                    )
        except httpx.HTTPError:
            logger.exception(
                "Resend HTTP error for schedule '%s'",
                schedule.schedule_id,
            )

    async def _resolve_api_key(self, api_key: dict[str, Any]) -> str:
        """Resolve ``{\"$secret\": \"KEY\"}`` to the secret value."""
        if not is_secret_ref(api_key):
            raise ValueError("api_key must be a $secret ref")
        ref = parse_secret_ref(api_key)
        return await self._secrets.resolve_ref(ref.key)
