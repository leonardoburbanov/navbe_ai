"""Tests for FileSystemScheduleRepository."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from navbe.core.database import create_engine
from navbe.core.exceptions import NotFoundError
from navbe.domains.schedules.models import ScheduleSpec
from navbe.domains.schedules.repository import FileSystemScheduleRepository, metadata


@pytest.fixture
async def repo(tmp_path: Path):
    """Repository backed by tmp filesystem + sqlite file."""
    engine = create_engine(str(tmp_path / "schedules.db"))
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    repository = FileSystemScheduleRepository(
        schedules_dir=tmp_path / "schedules",
        session_factory=session_factory,
    )
    yield repository
    await engine.dispose()


def _spec(**overrides) -> ScheduleSpec:
    data = {
        "schedule_id": "daily",
        "flow_id": "f1",
        "when": "+1h",
        "enabled": True,
        "next_run_at": datetime.now(UTC) - timedelta(seconds=1),
    }
    data.update(overrides)
    return ScheduleSpec.model_validate(data)


async def test_save_and_get(repo: FileSystemScheduleRepository, tmp_path: Path) -> None:
    """save() writes schedule.json that round-trips."""
    spec = _spec()
    await repo.save(spec)
    path = tmp_path / "schedules" / "daily" / "schedule.json"
    assert path.exists()
    loaded = await repo.get("daily")
    assert loaded.schedule_id == "daily"
    assert loaded.when == "+1h"


async def test_list_due(repo: FileSystemScheduleRepository) -> None:
    """list_due returns enabled schedules with next_run_at in the past."""
    await repo.save(_spec())
    await repo.save(
        _spec(
            schedule_id="future",
            next_run_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    due = await repo.list_due(datetime.now(UTC))
    ids = {item.schedule_id for item in due}
    assert "daily" in ids
    assert "future" not in ids


async def test_get_missing_raises(repo: FileSystemScheduleRepository) -> None:
    """Missing schedules raise NotFoundError."""
    with pytest.raises(NotFoundError):
        await repo.get("missing")
