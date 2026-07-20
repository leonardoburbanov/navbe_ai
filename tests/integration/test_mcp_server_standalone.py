"""End-to-end MCP client cycle: catalog → validate → create → run → status."""

import asyncio
import json
from pathlib import Path
from typing import Any

from fastmcp import Client
from pytest_httpserver import HTTPServer
from sqlalchemy.ext.asyncio import async_sessionmaker

import navbe.domains.connectors.implementations  # noqa: F401
import navbe.domains.steps.implementations  # noqa: F401
from navbe.core.database import create_engine
from navbe.domains.catalog.service import CatalogService
from navbe.domains.connectors.service import ConnectorService
from navbe.domains.execution.engine import LangGraphEngine
from navbe.domains.execution.models import RunStatus
from navbe.domains.execution.repository import FileSystemRunRepository
from navbe.domains.execution.service import RunService, resolve_connector_configs
from navbe.domains.flows.repository import FileSystemFlowRepository, metadata
from navbe.domains.flows.service import FlowService
from navbe.domains.secrets.service import EnvSecretsProvider, SecretsService
from navbe.mcp_app.server import create_mcp_server

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class FakeLLMClient:
    """Deterministic LLM for the demo flow."""

    async def complete(self, *, prompt: str, model: str) -> str:
        if "Classify the objection" in prompt:
            return '{"route": "handle"}'
        if "Respond to objection" in prompt:
            return "Here is a helpful response."
        return "Hello."


def load_fixture(name: str) -> dict:
    """Load a JSON fixture."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def build_real_mcp_server(tmp_path: Path, *, llm_client: Any | None = None):
    """Wire real domain services into an in-process FastMCP server."""
    db_engine = create_engine(str(tmp_path / "flows.db"))
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    flow_service = FlowService(
        FileSystemFlowRepository(
            flows_dir=tmp_path / "flows",
            session_factory=session_factory,
        )
    )
    connector_service = ConnectorService(
        secrets_service=SecretsService(EnvSecretsProvider()),
    )
    run_repo = FileSystemRunRepository(
        runs_dir_for=lambda flow_id: tmp_path / "runs" / flow_id,
    )

    async def _resolve(flow_spec):  # type: ignore[no-untyped-def]
        return await resolve_connector_configs(flow_spec, connector_service)

    engine = LangGraphEngine(
        run_repository=run_repo,
        checkpoint_db_path=str(tmp_path / "checkpoints.db"),
        resolve_connectors=_resolve,
        get_flow_spec=flow_service.get,
        llm_client=llm_client or FakeLLMClient(),
    )
    run_service = RunService(engine, flow_service, connector_service)
    catalog_service = CatalogService()
    from tests.unit.mcp_app.conftest import FakeSecretsService

    mcp = create_mcp_server(
        flow_service,
        run_service,
        catalog_service,
        FakeSecretsService(),  # type: ignore[arg-type]
    )
    mcp._navbe_db_engine = db_engine  # type: ignore[attr-defined]
    mcp._navbe_run_service = run_service  # type: ignore[attr-defined]
    return mcp


async def test_full_demo_cycle_via_mcp_client(
    tmp_path: Path,
    httpserver: HTTPServer,
    monkeypatch: Any,
) -> None:
    """Simulate agent: read catalog, validate, create, run, poll status."""
    monkeypatch.setenv("CRM_API_KEY", "sk-test")
    httpserver.expect_request("/leads/lead-1/notes", method="POST").respond_with_json(
        {"ok": True}
    )

    server = build_real_mcp_server(tmp_path)
    db_engine = server._navbe_db_engine  # type: ignore[attr-defined]
    run_service = server._navbe_run_service  # type: ignore[attr-defined]
    async with db_engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    demo = load_fixture("sales_bot_objection_test.json")
    demo["connectors"]["crm"]["config"]["base_url"] = httpserver.url_for("/")
    demo["connectors"]["crm"]["config"]["headers"] = {"Authorization": "Bearer test"}
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

    async with Client(server) as client:
        steps_contents = await client.read_resource("navbe://catalog/steps")
        steps_catalog = json.loads(steps_contents[0].text)
        assert "http_request" in steps_catalog

        validation = await client.call_tool("flow_validate", {"spec": demo})
        assert validation.data["valid"] is True

        created = await client.call_tool("flow_create", {"spec": demo})
        flow_id = created.data["flow_id"]

        listed = await client.call_tool("flow_list", {})
        assert any(flow["flow_id"] == flow_id for flow in listed.data["flows"])

        flows_contents = await client.read_resource("navbe://flows")
        flows_body = json.loads(flows_contents[0].text)
        assert any(flow["flow_id"] == flow_id for flow in flows_body["flows"])

        run = await client.call_tool(
            "flow_run",
            {
                "flow_id": flow_id,
                "initial_input": {"text": "Your price is too high", "amount": 1},
            },
        )
        run_id = run.data["run_id"]

        status = None
        for _ in range(40):
            if run_service._background_tasks:
                await asyncio.gather(
                    *list(run_service._background_tasks),
                    return_exceptions=True,
                )
            status = await client.call_tool("flow_status", {"run_id": run_id})
            if status.data["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(0.1)

        assert status is not None
        assert status.data["status"] == RunStatus.COMPLETED

    await db_engine.dispose()
