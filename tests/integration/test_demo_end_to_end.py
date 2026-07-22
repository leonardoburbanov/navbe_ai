"""CI-safe end-to-end demo against a real local fake sales-bot process."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastmcp import Client
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

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class FakeLLMClient:
    """Deterministic LLM client for the demo flow."""

    def __init__(self, fixed_route: str = "handle") -> None:
        self.fixed_route = fixed_route

    async def complete(self, *, prompt: str, model: str) -> str:
        if "Classify the objection" in prompt:
            return json.dumps({"route": self.fixed_route})
        if "Respond to objection" in prompt:
            return "Here is a helpful response to your price concern."
        return "Hello, thanks for your time today."


def load_fixture(name: str) -> dict:
    """Load a JSON fixture."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _free_port() -> int:
    """Return an unused localhost TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_health(url: str, timeout: float) -> None:
    """Poll until the HTTP health endpoint returns 200."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=1.0).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"Service at {url} did not become healthy in time")


@pytest.fixture
def running_sales_bot():
    """Start scripts/fake_sales_bot.py on a free port; tear down after."""
    port = _free_port()
    env = os.environ.copy()
    env["FAKE_SALES_BOT_PORT"] = str(port)
    proc = subprocess.Popen(
        ["uv", "run", "python", "scripts/fake_sales_bot.py"],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        _wait_for_health(f"{base}/health", timeout=15)
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def build_real_mcp_server(tmp_path: Path, *, llm_client: Any | None = None):
    """Wire real domain services into an in-process FastMCP server."""
    db_engine = create_engine(str(tmp_path / "flows.db"))
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    flows_dir = tmp_path / "navbe_flows"
    flow_service = FlowService(
        FileSystemFlowRepository(
            flows_dir=flows_dir,
            session_factory=session_factory,
        )
    )
    connector_service = ConnectorService(
        secrets_service=SecretsService(EnvSecretsProvider()),
    )
    run_repo = FileSystemRunRepository(
        runs_dir_for=lambda flow_id: flows_dir / flow_id / "runs",
    )

    async def _resolve(flow_spec):  # type: ignore[no-untyped-def]
        return await resolve_connector_configs(flow_spec, connector_service)

    engine = LangGraphEngine(
        run_repository=run_repo,
        checkpoint_db_path=str(tmp_path / "checkpoints.db"),
        resolve_connectors=_resolve,
        get_flow_spec=flow_service.get,
        llm_client=llm_client or FakeLLMClient(fixed_route="handle"),
    )
    run_service = RunService(engine, flow_service, connector_service)
    from tests.unit.mcp_app.conftest import (
        FakeGitHubAuthService,
        FakeSecretsService,
        FakeSyncService,
    )

    mcp = create_mcp_server(
        flow_service,
        run_service,
        CatalogService(),
        FakeSecretsService(),  # type: ignore[arg-type]
        FakeSyncService(),  # type: ignore[arg-type]
        FakeGitHubAuthService(),  # type: ignore[arg-type]
    )
    mcp._navbe_db_engine = db_engine  # type: ignore[attr-defined]
    mcp._navbe_run_service = run_service  # type: ignore[attr-defined]
    mcp._navbe_flows_dir = flows_dir  # type: ignore[attr-defined]
    return mcp


async def test_demo_flow_against_real_sales_bot(
    tmp_path: Path,
    running_sales_bot: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create + run the sales-bot fixture flow against a live local HTTP bot."""
    monkeypatch.setenv("CRM_API_KEY", "sk-test")
    server = build_real_mcp_server(
        tmp_path,
        llm_client=FakeLLMClient(fixed_route="handle"),
    )
    db_engine = server._navbe_db_engine  # type: ignore[attr-defined]
    run_service = server._navbe_run_service  # type: ignore[attr-defined]
    async with db_engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    demo = load_fixture("sales_bot_objection_test.json")
    demo["connectors"]["crm"]["config"]["base_url"] = running_sales_bot
    demo["connectors"]["crm"]["config"]["headers"] = {"Authorization": "Bearer test"}
    # Start at capture_objection so set_var receives structured input.
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
        created = await client.call_tool("flow_create", {"spec": demo})
        flow_id = created.data["flow_id"]

        run = await client.call_tool(
            "flow_run",
            {
                "flow_id": flow_id,
                "initial_input": {
                    "text": "Your price is too high / está caro",
                    "amount": 1,
                },
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
            await asyncio.sleep(0.2)

        assert status is not None
        assert status.data["status"] == RunStatus.COMPLETED
        assert "persist_outcome" in status.data["node_outputs"]
        assert status.data["node_outputs"]["router"]["route"] == "handle"

    transcript_path = (
        tmp_path / "navbe_flows" / flow_id / "runs" / run_id / "transcript.md"
    )
    assert transcript_path.exists()
    await db_engine.dispose()
