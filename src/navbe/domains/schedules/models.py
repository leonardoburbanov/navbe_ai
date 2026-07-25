"""Pydantic models for flow schedules."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ScheduleNotifyConfig(BaseModel):
    """Email alert when consecutive scheduled failures reach a threshold."""

    model_config = {"extra": "forbid", "populate_by_name": True}

    channel: Literal["email"] = "email"
    to: str
    from_addr: str = Field(alias="from")
    api_key: dict[str, Any]
    failure_threshold: int = 1

    @field_validator("failure_threshold")
    @classmethod
    def threshold_positive(cls, v: int) -> int:
        """Require at least one failure before notifying."""
        if v < 1:
            raise ValueError("failure_threshold must be >= 1")
        return v

    @field_validator("api_key")
    @classmethod
    def api_key_must_be_secret_ref(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Require ``{\"$secret\": \"KEY\"}`` shape (never plaintext)."""
        if set(v.keys()) != {"$secret"} or not isinstance(v.get("$secret"), str):
            raise ValueError('api_key must be {"$secret": "KEY_NAME"}')
        return v


class ScheduleSpec(BaseModel):
    """Persisted schedule document (``schedules/<id>/schedule.json``)."""

    model_config = {"extra": "forbid"}

    schedule_id: str
    flow_id: str
    name: str = ""
    when: str
    enabled: bool = True
    notify: ScheduleNotifyConfig | None = None
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_run_id: str | None = None
    consecutive_failures: int = 0
    notify_latched: bool = False


class ScheduleMetadata(BaseModel):
    """Index metadata for a persisted schedule."""

    schedule_id: str
    flow_id: str
    name: str
    enabled: bool
    when: str
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime
    path: str
