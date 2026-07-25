"""Schedule repository and notifier contracts."""

from datetime import datetime
from typing import Protocol, runtime_checkable

from navbe.domains.schedules.models import ScheduleMetadata, ScheduleSpec


@runtime_checkable
class ScheduleRepository(Protocol):
    """Persistence port for schedule specs."""

    async def save(self, schedule: ScheduleSpec) -> ScheduleMetadata:
        """Persist a new schedule and return its metadata."""
        ...

    async def get(self, schedule_id: str) -> ScheduleSpec:
        """Load a schedule by id."""
        ...

    async def list(self) -> list[ScheduleMetadata]:
        """List indexed schedule metadata."""
        ...

    async def update(self, schedule: ScheduleSpec) -> ScheduleMetadata:
        """Overwrite an existing schedule."""
        ...

    async def upsert(self, schedule: ScheduleSpec) -> ScheduleMetadata:
        """Write schedule.json and upsert index (sync import)."""
        ...

    async def delete_index(self, schedule_id: str) -> None:
        """Remove a schedule_id from the index after its directory was deleted."""
        ...

    async def list_due(self, now: datetime) -> list[ScheduleSpec]:
        """Return enabled schedules with ``next_run_at <= now``."""
        ...


@runtime_checkable
class FailureNotifier(Protocol):
    """Port for alerting on repeated schedule failures."""

    async def notify_failure(
        self,
        *,
        schedule: ScheduleSpec,
        error: str | None,
        failure_count: int,
    ) -> None:
        """Send a failure alert for ``schedule`` (must not raise to callers)."""
        ...
