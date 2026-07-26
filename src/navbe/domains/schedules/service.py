"""Use-cases for schedule CRUD, due firing, and failure accounting."""

import builtins
import logging
from datetime import UTC, datetime
from typing import Any

import pydantic

from navbe.core.exceptions import ValidationError
from navbe.domains.execution.models import RunState, RunStatus
from navbe.domains.flows.service import FlowService
from navbe.domains.schedules.interfaces import FailureNotifier, ScheduleRepository
from navbe.domains.schedules.models import ScheduleMetadata, ScheduleSpec
from navbe.domains.schedules.when import compute_next_run_at, validate_when

logger = logging.getLogger(__name__)


class ScheduleService:
    """Facade for schedule persistence and post-run failure handling."""

    def __init__(
        self,
        repository: ScheduleRepository,
        flow_service: FlowService,
        *,
        notifier: FailureNotifier | None = None,
    ) -> None:
        """Create a service with injectable repository and optional notifier."""
        self._repository = repository
        self._flow_service = flow_service
        self._notifier = notifier

    def _validate_spec_dict(self, payload: dict[str, Any]) -> ScheduleSpec:
        """Parse and validate a schedule dict (when + structure)."""
        try:
            schedule = ScheduleSpec.model_validate(payload)
        except pydantic.ValidationError as exc:
            raise ValidationError(
                "Invalid ScheduleSpec structure",
                details={"errors": exc.errors()},
            ) from exc
        validate_when(schedule.when)
        return schedule

    async def _ensure_flow_exists(self, flow_id: str) -> None:
        """Raise if the target flow is missing."""
        await self._flow_service.get(flow_id)

    async def create(self, payload: dict[str, Any]) -> ScheduleMetadata:
        """Validate, compute next_run_at, and persist a new schedule."""
        schedule = self._validate_spec_dict(payload)
        await self._ensure_flow_exists(schedule.flow_id)
        if schedule.next_run_at is None:
            schedule = schedule.model_copy(
                update={"next_run_at": compute_next_run_at(schedule.when)}
            )
        return await self._repository.save(schedule)

    async def update(self, payload: dict[str, Any]) -> ScheduleMetadata:
        """Validate and overwrite an existing schedule.

        Recomputes ``next_run_at`` from now when ``when`` changes or the
        schedule is re-enabled.
        """
        schedule = self._validate_spec_dict(payload)
        await self._ensure_flow_exists(schedule.flow_id)
        prior = await self._repository.get(schedule.schedule_id)
        when_changed = prior.when != schedule.when
        reenabled = (not prior.enabled) and schedule.enabled
        if when_changed or reenabled or schedule.next_run_at is None:
            schedule = schedule.model_copy(
                update={"next_run_at": compute_next_run_at(schedule.when)}
            )
        # Preserve runtime counters unless the caller explicitly sends them.
        schedule = schedule.model_copy(
            update={
                "consecutive_failures": schedule.consecutive_failures
                if "consecutive_failures" in payload
                else prior.consecutive_failures,
                "notify_latched": schedule.notify_latched
                if "notify_latched" in payload
                else prior.notify_latched,
                "last_run_at": schedule.last_run_at
                if "last_run_at" in payload
                else prior.last_run_at,
                "last_run_id": schedule.last_run_id
                if "last_run_id" in payload
                else prior.last_run_id,
            }
        )
        return await self._repository.update(schedule)

    async def get(self, schedule_id: str) -> ScheduleSpec:
        """Load a schedule by id."""
        return await self._repository.get(schedule_id)

    async def list(self) -> builtins.list[ScheduleMetadata]:
        """List saved schedule metadata."""
        return await self._repository.list()

    async def enable(self, schedule_id: str) -> ScheduleSpec:
        """Enable a schedule and refresh next_run_at."""
        schedule = await self._repository.get(schedule_id)
        updated = schedule.model_copy(
            update={
                "enabled": True,
                "next_run_at": compute_next_run_at(schedule.when),
            }
        )
        await self._repository.update(updated)
        return updated

    async def disable(self, schedule_id: str) -> ScheduleSpec:
        """Disable a schedule (keeps next_run_at for display)."""
        schedule = await self._repository.get(schedule_id)
        updated = schedule.model_copy(update={"enabled": False})
        await self._repository.update(updated)
        return updated

    async def list_due(self, now: datetime | None = None) -> builtins.list[ScheduleSpec]:
        """Return enabled schedules that are due."""
        return await self._repository.list_due(now or datetime.now(UTC))

    async def advance_next_run(self, schedule_id: str) -> ScheduleSpec:
        """Bump ``next_run_at`` from now (after fire or busy skip)."""
        schedule = await self._repository.get(schedule_id)
        updated = schedule.model_copy(
            update={"next_run_at": compute_next_run_at(schedule.when)}
        )
        await self._repository.update(updated)
        return updated

    async def record_fire(self, schedule_id: str, run_id: str) -> ScheduleSpec:
        """Record that a scheduled run was started."""
        schedule = await self._repository.get(schedule_id)
        now = datetime.now(UTC)
        updated = schedule.model_copy(
            update={
                "last_run_at": now,
                "last_run_id": run_id,
                "next_run_at": compute_next_run_at(schedule.when, after=now),
            }
        )
        await self._repository.update(updated)
        return updated

    async def on_run_settled(self, state: RunState) -> None:
        """Update failure counters / notify when a scheduled run settles."""
        if state.trigger != "schedule" or not state.schedule_id:
            return
        if state.status == RunStatus.PAUSED:
            return

        try:
            schedule = await self._repository.get(state.schedule_id)
        except Exception:
            logger.exception(
                "Schedule '%s' missing for settled run '%s'",
                state.schedule_id,
                state.run_id,
            )
            return

        if state.status == RunStatus.COMPLETED:
            updated = schedule.model_copy(
                update={"consecutive_failures": 0, "notify_latched": False}
            )
            await self._repository.update(updated)
            return

        if state.status not in {RunStatus.FAILED, RunStatus.CANCELLED}:
            return

        # Cancelled does not count toward failure notify threshold.
        if state.status == RunStatus.CANCELLED:
            return

        failures = schedule.consecutive_failures + 1
        notify_latched = schedule.notify_latched
        updated = schedule.model_copy(update={"consecutive_failures": failures})

        threshold = (
            schedule.notify.failure_threshold if schedule.notify is not None else None
        )
        should_notify = (
            schedule.notify is not None
            and threshold is not None
            and failures >= threshold
            and not notify_latched
            and self._notifier is not None
        )
        if should_notify:
            try:
                await self._notifier.notify_failure(
                    schedule=updated,
                    error=state.error,
                    failure_count=failures,
                )
                updated = updated.model_copy(update={"notify_latched": True})
            except Exception:
                logger.exception(
                    "Failure notifier failed for schedule '%s'",
                    schedule.schedule_id,
                )

        await self._repository.update(updated)
