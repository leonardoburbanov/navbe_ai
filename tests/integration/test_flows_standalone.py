"""Standalone flow persistence without an execution engine."""

import json
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker

import navbe.domains.steps.implementations  # noqa: F401
from navbe.core.database import create_engine
from navbe.domains.flows.repository import FileSystemFlowRepository, metadata
from navbe.domains.flows.service import FlowService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture by filename."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def test_save_demo_flow_and_retrieve(tmp_path: Path) -> None:
    """Create and retrieve the sales-bot demo flow end-to-end."""
    engine = create_engine(str(tmp_path / "test.db"))
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    repo = FileSystemFlowRepository(
        flows_dir=tmp_path / "flows",
        session_factory=session_factory,
    )
    service = FlowService(repo)

    demo_flow_dict = load_fixture("sales_bot_objection_test.json")
    meta = await service.create(demo_flow_dict)

    assert meta.flow_id == "sales_bot_objection_test"
    assert (tmp_path / "flows" / "sales_bot_objection_test" / "flow.json").exists()

    retrieved = await service.get("sales_bot_objection_test")
    assert retrieved.entry_node == "turn_1"
    await engine.dispose()
