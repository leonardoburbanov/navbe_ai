"""Background tick loop that fires due schedules (serve process only)."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from navbe.domains.execution.service import RunService
from navbe.domains.schedules.service import ScheduleService

logger = logging.getLogger(__name__)

DEFAULT_TICK_SECONDS = 10.0


class SchedulerLoop:
    """Poll due schedules and start runs via RunService."""

    def __init__(
        self,
        schedule_service: ScheduleService,
        run_service: RunService,
        *,
        tick_seconds: float = DEFAULT_TICK_SECONDS,
    ) -> None:
        """Bind services and tick interval."""
        self._schedules = schedule_service
        self._runs = run_service
        self._tick_seconds = tick_seconds
        self._task: asyncio.Task[None] | None = None
        self._stopping = False

    def start(self) -> None:
        """Spawn the background tick task."""
        if self._task is not None and not self._task.done():
            return
        self._stopping = False
        self._task = asyncio.create_task(self._run_loop(), name="navbe-scheduler")

    async def stop(self) -> None:
        """Cancel the tick task and wait for it to finish."""
        self._stopping = True
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run_loop(self) -> None:
        """Tick until cancelled."""
        logger.info("Scheduler loop started (tick=%ss)", self._tick_seconds)
        try:
            while not self._stopping:
                try:
                    await self.tick_once()
                except Exception:
                    logger.exception("Scheduler tick failed")
                await asyncio.sleep(self._tick_seconds)
        except asyncio.CancelledError:
            logger.info("Scheduler loop stopped")
            raise

    async def tick_once(self) -> None:
        """Fire all currently due schedules (single-flight aware)."""
        now = datetime.now(UTC)
        due = await self._schedules.list_due(now)
        for schedule in due:
            if await self._runs.is_flow_busy(schedule.flow_id):
                logger.info(
                    "Schedule '%s' skipped — flow '%s' busy",
                    schedule.schedule_id,
                    schedule.flow_id,
                )
                await self._schedules.advance_next_run(schedule.schedule_id)
                continue

            run_id = await self._runs.start(
                schedule.flow_id,
                None,
                wait=False,
                trigger="schedule",
                schedule_id=schedule.schedule_id,
                skip_if_busy=True,
            )
            if run_id is None:
                await self._schedules.advance_next_run(schedule.schedule_id)
                continue
            await self._schedules.record_fire(schedule.schedule_id, run_id)
            logger.info(
                "Schedule '%s' started run '%s'",
                schedule.schedule_id,
                run_id,
            )
