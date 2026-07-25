"""Filesystem + SQLite persistence for schedule specs."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiofiles
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    delete,
    insert,
    select,
    update,
)

from navbe.core.exceptions import NotFoundError, ValidationError
from navbe.domains.schedules.models import ScheduleMetadata, ScheduleSpec

metadata = MetaData()

schedules_index = Table(
    "schedules_index",
    metadata,
    Column("schedule_id", String, primary_key=True),
    Column("flow_id", String, nullable=False),
    Column("name", String),
    Column("enabled", Boolean, default=True),
    Column("when_expr", String, nullable=False),
    Column("next_run_at", DateTime, nullable=True),
    Column("path", String),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)


def _naive_utc(value: datetime | None) -> datetime | None:
    """Store UTC datetimes without tzinfo for SQLite compatibility."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _aware_utc(value: datetime | None) -> datetime | None:
    """Rehydrate naive DB datetimes as UTC-aware."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class FileSystemScheduleRepository:
    """Store schedule.json under schedules_dir and index rows in SQLite."""

    def __init__(self, schedules_dir: Path, session_factory: Any) -> None:
        """Create a repository over ``schedules_dir`` and an async session factory."""
        self._schedules_dir = schedules_dir
        self._session_factory = session_factory

    def _schedule_path(self, schedule_id: str) -> Path:
        """Return the canonical schedule.json path for ``schedule_id``."""
        return self._schedules_dir / schedule_id / "schedule.json"

    async def _write_spec(self, path: Path, schedule: ScheduleSpec) -> None:
        """Write a ScheduleSpec JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "w", encoding="utf-8") as handle:
            await handle.write(schedule.model_dump_json(by_alias=True, indent=2))

    async def save(self, schedule: ScheduleSpec) -> ScheduleMetadata:
        """Persist a new schedule and index it."""
        path = self._schedule_path(schedule.schedule_id)
        if path.exists():
            raise ValidationError(
                f"Schedule '{schedule.schedule_id}' already exists",
                details={"schedule_id": schedule.schedule_id},
            )

        await self._write_spec(path, schedule)
        now = datetime.now(UTC).replace(tzinfo=None)

        async with self._session_factory() as session:
            await session.execute(
                insert(schedules_index).values(
                    schedule_id=schedule.schedule_id,
                    flow_id=schedule.flow_id,
                    name=schedule.name,
                    enabled=schedule.enabled,
                    when_expr=schedule.when,
                    next_run_at=_naive_utc(schedule.next_run_at),
                    path=str(path),
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

        return ScheduleMetadata(
            schedule_id=schedule.schedule_id,
            flow_id=schedule.flow_id,
            name=schedule.name,
            enabled=schedule.enabled,
            when=schedule.when,
            next_run_at=schedule.next_run_at,
            created_at=now,
            updated_at=now,
            path=str(path),
        )

    async def get(self, schedule_id: str) -> ScheduleSpec:
        """Load a ScheduleSpec from disk."""
        path = self._schedule_path(schedule_id)
        if not path.exists():
            raise NotFoundError(
                f"Schedule '{schedule_id}' not found",
                details={"schedule_id": schedule_id},
            )
        async with aiofiles.open(path, encoding="utf-8") as handle:
            content = await handle.read()
        return ScheduleSpec.model_validate_json(content)

    async def list(self) -> list[ScheduleMetadata]:
        """Return all indexed schedule metadata."""
        async with self._session_factory() as session:
            result = await session.execute(select(schedules_index))
            return [
                ScheduleMetadata(
                    schedule_id=row.schedule_id,
                    flow_id=row.flow_id,
                    name=row.name or "",
                    enabled=bool(row.enabled),
                    when=row.when_expr,
                    next_run_at=_aware_utc(row.next_run_at),
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                    path=row.path,
                )
                for row in result
            ]

    async def update(self, schedule: ScheduleSpec) -> ScheduleMetadata:
        """Overwrite schedule.json and refresh the index row."""
        path = self._schedule_path(schedule.schedule_id)
        if not path.exists():
            raise NotFoundError(
                f"Schedule '{schedule.schedule_id}' not found",
                details={"schedule_id": schedule.schedule_id},
            )

        async with self._session_factory() as session:
            result = await session.execute(
                select(schedules_index).where(
                    schedules_index.c.schedule_id == schedule.schedule_id
                )
            )
            row = result.one_or_none()
            if row is None:
                raise NotFoundError(
                    f"Schedule '{schedule.schedule_id}' not found in index",
                    details={"schedule_id": schedule.schedule_id},
                )
            created_at = row.created_at
            await self._write_spec(path, schedule)
            now = datetime.now(UTC).replace(tzinfo=None)
            await session.execute(
                update(schedules_index)
                .where(schedules_index.c.schedule_id == schedule.schedule_id)
                .values(
                    flow_id=schedule.flow_id,
                    name=schedule.name,
                    enabled=schedule.enabled,
                    when_expr=schedule.when,
                    next_run_at=_naive_utc(schedule.next_run_at),
                    path=str(path),
                    updated_at=now,
                )
            )
            await session.commit()

        return ScheduleMetadata(
            schedule_id=schedule.schedule_id,
            flow_id=schedule.flow_id,
            name=schedule.name,
            enabled=schedule.enabled,
            when=schedule.when,
            next_run_at=schedule.next_run_at,
            created_at=created_at,
            updated_at=now,
            path=str(path),
        )

    async def upsert(self, schedule: ScheduleSpec) -> ScheduleMetadata:
        """Write schedule.json and upsert index (for sync pull)."""
        path = self._schedule_path(schedule.schedule_id)
        await self._write_spec(path, schedule)
        now = datetime.now(UTC).replace(tzinfo=None)

        async with self._session_factory() as session:
            result = await session.execute(
                select(schedules_index).where(
                    schedules_index.c.schedule_id == schedule.schedule_id
                )
            )
            row = result.one_or_none()
            if row is None:
                await session.execute(
                    insert(schedules_index).values(
                        schedule_id=schedule.schedule_id,
                        flow_id=schedule.flow_id,
                        name=schedule.name,
                        enabled=schedule.enabled,
                        when_expr=schedule.when,
                        next_run_at=_naive_utc(schedule.next_run_at),
                        path=str(path),
                        created_at=now,
                        updated_at=now,
                    )
                )
                await session.commit()
                return ScheduleMetadata(
                    schedule_id=schedule.schedule_id,
                    flow_id=schedule.flow_id,
                    name=schedule.name,
                    enabled=schedule.enabled,
                    when=schedule.when,
                    next_run_at=schedule.next_run_at,
                    created_at=now,
                    updated_at=now,
                    path=str(path),
                )

            created_at = row.created_at
            await session.execute(
                update(schedules_index)
                .where(schedules_index.c.schedule_id == schedule.schedule_id)
                .values(
                    flow_id=schedule.flow_id,
                    name=schedule.name,
                    enabled=schedule.enabled,
                    when_expr=schedule.when,
                    next_run_at=_naive_utc(schedule.next_run_at),
                    path=str(path),
                    updated_at=now,
                )
            )
            await session.commit()

        return ScheduleMetadata(
            schedule_id=schedule.schedule_id,
            flow_id=schedule.flow_id,
            name=schedule.name,
            enabled=schedule.enabled,
            when=schedule.when,
            next_run_at=schedule.next_run_at,
            created_at=created_at,
            updated_at=now,
            path=str(path),
        )

    async def delete_index(self, schedule_id: str) -> None:
        """Remove a schedule_id from the SQLite index."""
        async with self._session_factory() as session:
            await session.execute(
                delete(schedules_index).where(
                    schedules_index.c.schedule_id == schedule_id
                )
            )
            await session.commit()

    async def list_due(self, now: datetime) -> list[ScheduleSpec]:
        """Return enabled schedules whose next_run_at is due."""
        now_naive = _naive_utc(now)
        async with self._session_factory() as session:
            result = await session.execute(
                select(schedules_index.c.schedule_id).where(
                    schedules_index.c.enabled.is_(True),
                    schedules_index.c.next_run_at.is_not(None),
                    schedules_index.c.next_run_at <= now_naive,
                )
            )
            ids = [row.schedule_id for row in result]

        due: list[ScheduleSpec] = []
        for schedule_id in ids:
            due.append(await self.get(schedule_id))
        return due
