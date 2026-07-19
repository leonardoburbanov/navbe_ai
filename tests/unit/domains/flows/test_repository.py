"""Tests for FileSystemFlowRepository."""

import json
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from navbe.core.database import create_engine
from navbe.core.exceptions import NotFoundError
from navbe.domains.flows.models import FlowSpec
from navbe.domains.flows.repository import FileSystemFlowRepository, metadata

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def _demo_spec() -> FlowSpec:
    """Load demo FlowSpec."""
    return FlowSpec.model_validate_json(
        (FIXTURES / "sales_bot_objection_test.json").read_text(encoding="utf-8")
    )


@pytest.fixture
async def repo(tmp_path: Path):
    """Repository backed by tmp filesystem + in-memory-ish sqlite file."""
    engine = create_engine(str(tmp_path / "flows.db"))
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    repository = FileSystemFlowRepository(
        flows_dir=tmp_path / "flows",
        session_factory=session_factory,
    )
    yield repository
    await engine.dispose()


async def test_save_creates_flow_json_at_expected_path(
    repo: FileSystemFlowRepository,
    tmp_path: Path,
) -> None:
    """save() writes flow.json that round-trips."""
    spec = _demo_spec()
    await repo.save(spec)
    path = tmp_path / "flows" / spec.flow_id / "flow.json"
    assert path.exists()
    loaded = FlowSpec.model_validate_json(path.read_text(encoding="utf-8"))
    assert loaded.flow_id == spec.flow_id
    assert loaded.entry_node == spec.entry_node
    assert loaded.edges[0].from_ == "turn_1"
    assert '"from"' in path.read_text(encoding="utf-8")


async def test_save_creates_index_row(repo: FileSystemFlowRepository) -> None:
    """save() indexes the flow for list()."""
    spec = _demo_spec()
    await repo.save(spec)
    listed = await repo.list()
    assert any(item.flow_id == spec.flow_id for item in listed)


async def test_get_existing_flow_returns_equivalent_spec(repo: FileSystemFlowRepository) -> None:
    """get() returns a FlowSpec equal to what was saved."""
    spec = _demo_spec()
    await repo.save(spec)
    retrieved = await repo.get(spec.flow_id)
    assert retrieved.model_dump(by_alias=True) == spec.model_dump(by_alias=True)


async def test_get_nonexistent_flow_raises_not_found(repo: FileSystemFlowRepository) -> None:
    """Missing flows raise NotFoundError with flow_id details."""
    with pytest.raises(NotFoundError) as exc_info:
        await repo.get("missing")
    assert exc_info.value.details["flow_id"] == "missing"


async def test_update_increments_version(repo: FileSystemFlowRepository) -> None:
    """update() bumps version in the index."""
    spec = _demo_spec()
    await repo.save(spec)
    updated = spec.model_copy(update={"name": "updated name"})
    meta = await repo.update(updated)
    assert meta.version == 2
    listed = await repo.list()
    row = next(item for item in listed if item.flow_id == spec.flow_id)
    assert row.version == 2
    assert row.name == "updated name"


async def test_update_preserves_previous_version_file(
    repo: FileSystemFlowRepository,
    tmp_path: Path,
) -> None:
    """update() archives flow.v1.json before overwriting flow.json."""
    spec = _demo_spec()
    await repo.save(spec)
    updated = spec.model_copy(update={"name": "v2"})
    await repo.update(updated)

    flow_dir = tmp_path / "flows" / spec.flow_id
    assert (flow_dir / "flow.json").exists()
    assert (flow_dir / "flow.v1.json").exists()
    archived = json.loads((flow_dir / "flow.v1.json").read_text(encoding="utf-8"))
    assert archived["name"] == "Sales bot objection handling"
    current = json.loads((flow_dir / "flow.json").read_text(encoding="utf-8"))
    assert current["name"] == "v2"


async def test_list_returns_all_saved_flows(repo: FileSystemFlowRepository) -> None:
    """list() returns metadata for every saved flow."""
    base = _demo_spec()
    for suffix in ("a", "b", "c"):
        await repo.save(
            base.model_copy(update={"flow_id": f"flow_{suffix}", "name": f"Flow {suffix}"})
        )
    listed = await repo.list()
    ids = {item.flow_id for item in listed}
    assert ids == {"flow_a", "flow_b", "flow_c"}
