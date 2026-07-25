"""Standalone end-to-end execution of the sales-bot demo flow."""

import asyncio
import json
from pathlib import Path

from pytest_httpserver import HTTPServer
from sqlalchemy.ext.asyncio import async_sessionmaker

import navbe.domains.connectors.implementations  # noqa: F401
import navbe.domains.steps.implementations  # noqa: F401
from navbe.core.database import create_engine
from navbe.domains.connectors.service import ConnectorService
from navbe.domains.execution.engine import LangGraphEngine
from navbe.domains.execution.models import RunStatus
from navbe.domains.execution.repository import FileSystemRunRepository
from navbe.domains.execution.service import RunService, resolve_connector_configs
from navbe.domains.flows.repository import FileSystemFlowRepository, metadata
from navbe.domains.flows.service import FlowService
from navbe.domains.secrets.json_file import JsonFileSecretsProvider
from navbe.domains.secrets.service import SecretsService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class FakeLLMClient:
    """Deterministic LLM client for demo execution."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, *, prompt: str, model: str) -> str:
        self.calls += 1
        if "Classify the objection" in prompt:
            return '{"route": "handle"}'
        if "Respond to objection" in prompt:
            return "Here is a helpful response to your concern."
        return "Hello, thanks for your time today."


def load_fixture(name: str) -> dict:
    """Load a JSON fixture."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def build_real_flow_service(tmp_path: Path) -> FlowService:
    """Wire a real FlowService against tmp filesystem + sqlite."""
    engine = create_engine(str(tmp_path / "flows.db"))
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _ensure() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)

    # Create tables synchronously via event loop helper in the test body.
    flow_repo = FileSystemFlowRepository(
        flows_dir=tmp_path / "flows",
        session_factory=session_factory,
    )
    service = FlowService(flow_repo)
    service._engine = engine  # type: ignore[attr-defined]
    return service


async def test_full_demo_flow_executes_end_to_end(
    tmp_path: Path,
    httpserver: HTTPServer,
) -> None:
    """Execute the sales-bot demo with mocked HTTP + LLM."""
    httpserver.expect_request("/leads/lead-1/notes", method="POST").respond_with_json(
        {"ok": True}
    )

    db_engine = create_engine(str(tmp_path / "flows.db"))
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with db_engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    flow_service = FlowService(
        FileSystemFlowRepository(
            flows_dir=tmp_path / "flows",
            session_factory=session_factory,
        )
    )

    demo = load_fixture("sales_bot_objection_test.json")
    demo["connectors"]["crm"]["config"]["base_url"] = httpserver.url_for("/")
    demo["connectors"]["crm"]["config"]["headers"] = {"Authorization": "Bearer test"}
    # Start at capture_objection so set_var receives a dict input (not LLM text).
    demo["nodes"] = [node for node in demo["nodes"] if node["id"] != "turn_1"]
    demo["edges"] = [
        edge
        for edge in demo["edges"]
        if edge.get("from") != "turn_1" and edge.get("to") != "turn_1"
    ]
    demo["entry_node"] = "capture_objection"
    for node in demo["nodes"]:
        if node["id"] == "persist_outcome":
            node["config"]["path"] = "/leads/lead-1/notes"
    await flow_service.create(demo)

    creds = JsonFileSecretsProvider(tmp_path / "creds.json")
    await creds.set("CRM_API_KEY", "sk-test")
    connector_service = ConnectorService(
        secrets_service=SecretsService(creds, store=creds),
    )
    run_repo = FileSystemRunRepository(
        runs_dir_for=lambda flow_id: tmp_path / "runs" / flow_id,
    )
    llm = FakeLLMClient()

    async def _resolve(flow_spec):  # type: ignore[no-untyped-def]
        return await resolve_connector_configs(flow_spec, connector_service)

    engine = LangGraphEngine(
        run_repository=run_repo,
        checkpoint_db_path=str(tmp_path / "checkpoints.db"),
        resolve_connectors=_resolve,
        get_flow_spec=flow_service.get,
        llm_client=llm,
    )
    run_service = RunService(engine, flow_service, connector_service)

    run_id = await run_service.start(
        "sales_bot_objection_test",
        {"text": "Your price is too high", "amount": 1},
    )
    final = None
    for _ in range(50):
        if run_service._background_tasks:
            await asyncio.gather(*list(run_service._background_tasks), return_exceptions=True)
        final = await run_service.status(run_id)
        if final.status in (RunStatus.COMPLETED, RunStatus.FAILED):
            break
        await asyncio.sleep(0.05)
    assert final is not None
    assert final.status == RunStatus.COMPLETED
    assert "persist_outcome" in final.node_outputs
    assert "router" in final.node_outputs
    assert final.node_outputs["router"]["route"] == "handle"

    run_dir = tmp_path / "runs" / "sales_bot_objection_test" / run_id
    assert (run_dir / "state.json").exists()
    assert (run_dir / "transcript.md").exists()
    await db_engine.dispose()
