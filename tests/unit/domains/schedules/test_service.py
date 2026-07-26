"""Tests for ScheduleService failure accounting and CRUD helpers."""

import builtins
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

from navbe.domains.execution.models import RunState, RunStatus
from navbe.domains.flows.models import FlowSpec
from navbe.domains.schedules.models import ScheduleMetadata, ScheduleSpec
from navbe.domains.schedules.service import ScheduleService


class FakeScheduleRepo:
    """In-memory schedule repository."""

    def __init__(self) -> None:
        self.items: dict[str, ScheduleSpec] = {}

    async def save(self, schedule: ScheduleSpec) -> ScheduleMetadata:
        self.items[schedule.schedule_id] = schedule
        now = datetime.now(UTC)
        return ScheduleMetadata(
            schedule_id=schedule.schedule_id,
            flow_id=schedule.flow_id,
            name=schedule.name,
            enabled=schedule.enabled,
            when=schedule.when,
            next_run_at=schedule.next_run_at,
            created_at=now,
            updated_at=now,
            path=f"{schedule.schedule_id}/schedule.json",
        )

    async def get(self, schedule_id: str) -> ScheduleSpec:
        return self.items[schedule_id]

    async def list(self) -> builtins.list[ScheduleMetadata]:
        return []

    async def update(self, schedule: ScheduleSpec) -> ScheduleMetadata:
        self.items[schedule.schedule_id] = schedule
        now = datetime.now(UTC)
        return ScheduleMetadata(
            schedule_id=schedule.schedule_id,
            flow_id=schedule.flow_id,
            name=schedule.name,
            enabled=schedule.enabled,
            when=schedule.when,
            next_run_at=schedule.next_run_at,
            created_at=now,
            updated_at=now,
            path=f"{schedule.schedule_id}/schedule.json",
        )

    async def upsert(self, schedule: ScheduleSpec) -> ScheduleMetadata:
        return await self.update(schedule)

    async def delete_index(self, schedule_id: str) -> None:
        self.items.pop(schedule_id, None)

    async def list_due(self, now: datetime) -> builtins.list[ScheduleSpec]:
        due: builtins.list[ScheduleSpec] = []
        for s in self.items.values():
            if s.enabled and s.next_run_at is not None and s.next_run_at <= now:
                due.append(s)
        return due


class FakeFlowService:
    """Minimal flow existence check."""

    async def get(self, flow_id: str) -> FlowSpec:
        return FlowSpec.model_validate(
            {
                "flow_id": flow_id,
                "entry_node": "n1",
                "nodes": [
                    {
                        "id": "n1",
                        "step_type": "set_var",
                        "config": {"var_name": "x", "value_from": "x"},
                    }
                ],
                "edges": [],
            }
        )


def _schedule(**overrides: Any) -> ScheduleSpec:
    base = {
        "schedule_id": "s1",
        "flow_id": "f1",
        "when": "+1h",
        "enabled": True,
        "next_run_at": datetime.now(UTC),
        "notify": {
            "channel": "email",
            "to": "ops@example.com",
            "from": "navbe@example.com",
            "api_key": {"$secret": "RESEND_API_KEY"},
            "failure_threshold": 2,
        },
    }
    base.update(overrides)
    return ScheduleSpec.model_validate(base)


async def test_create_computes_next_run_at() -> None:
    """create() fills next_run_at when omitted."""
    repo = FakeScheduleRepo()
    service = ScheduleService(repo, FakeFlowService())
    meta = await service.create(
        {
            "schedule_id": "s1",
            "flow_id": "f1",
            "when": "+30s",
        }
    )
    assert meta.next_run_at is not None
    assert repo.items["s1"].next_run_at is not None


async def test_on_run_settled_increments_and_notifies_at_threshold() -> None:
    """Failures accumulate; notify fires once at threshold then latches."""
    repo = FakeScheduleRepo()
    repo.items["s1"] = _schedule(consecutive_failures=1, notify_latched=False)
    notifier = AsyncMock()
    service = ScheduleService(repo, FakeFlowService(), notifier=notifier)
    now = datetime.now(UTC)
    await service.on_run_settled(
        RunState(
            run_id="r1",
            flow_id="f1",
            status=RunStatus.FAILED,
            error="boom",
            trigger="schedule",
            schedule_id="s1",
            created_at=now,
            updated_at=now,
        )
    )
    assert repo.items["s1"].consecutive_failures == 2
    assert repo.items["s1"].notify_latched is True
    notifier.notify_failure.assert_awaited_once()


async def test_on_run_settled_success_resets_latch() -> None:
    """Completed scheduled runs reset failure counters and latch."""
    repo = FakeScheduleRepo()
    repo.items["s1"] = _schedule(consecutive_failures=3, notify_latched=True)
    service = ScheduleService(repo, FakeFlowService(), notifier=AsyncMock())
    now = datetime.now(UTC)
    await service.on_run_settled(
        RunState(
            run_id="r1",
            flow_id="f1",
            status=RunStatus.COMPLETED,
            trigger="schedule",
            schedule_id="s1",
            created_at=now,
            updated_at=now,
        )
    )
    assert repo.items["s1"].consecutive_failures == 0
    assert repo.items["s1"].notify_latched is False


async def test_disable_sets_enabled_false() -> None:
    """disable() flips enabled without deleting the schedule."""
    repo = FakeScheduleRepo()
    repo.items["s1"] = _schedule()
    service = ScheduleService(repo, FakeFlowService())
    updated = await service.disable("s1")
    assert updated.enabled is False
    assert repo.items["s1"].enabled is False
