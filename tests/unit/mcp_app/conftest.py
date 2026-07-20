"""Shared fakes for mcp_app unit tests."""

from datetime import UTC, datetime
from typing import Any

from navbe.core.exceptions import NotFoundError
from navbe.domains.execution.models import RunState, RunStatus
from navbe.domains.flows.models import FlowMetadata, FlowSpec
from navbe.domains.flows.validator import ValidationResult


class FakeCatalogService:
    """Catalog service fake with fixed payloads."""

    def __init__(self) -> None:
        self.steps = {"http_request": {"step_type": "http_request", "config_schema": {}}}
        self.connectors = {
            "http": {"connector_type": "http", "config_schema": {}, "actions": {}}
        }

    async def get_steps_catalog(self) -> dict:
        return self.steps

    async def get_connectors_catalog(self) -> dict:
        return self.connectors

    async def get_full_catalog(self) -> dict:
        return {"steps": self.steps, "connectors": self.connectors}


class FakeFlowService:
    """Flow service fake for MCP tool tests."""

    def __init__(self) -> None:
        self.created: list[dict] = []
        self.updated: list[dict] = []
        self.create_error: Exception | None = None
        self.update_error: Exception | None = None
        self.get_error: Exception | None = None
        self.validate_result = ValidationResult(valid=True, issues=[])
        self.flows: dict[str, FlowSpec] = {}
        self.meta: dict[str, FlowMetadata] = {}

    async def create(self, spec: dict[str, Any]) -> FlowMetadata:
        if self.create_error is not None:
            raise self.create_error
        self.created.append(spec)
        now = datetime.now(UTC)
        meta = FlowMetadata(
            flow_id=spec.get("flow_id", "f1"),
            name=spec.get("name", ""),
            created_at=now,
            updated_at=now,
            version=1,
            path="/tmp/f1/flow.json",
        )
        self.meta[meta.flow_id] = meta
        self.flows[meta.flow_id] = FlowSpec.model_validate(
            {
                "flow_id": meta.flow_id,
                "name": meta.name,
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
        return meta

    async def update(self, spec: dict[str, Any]) -> FlowMetadata:
        if self.update_error is not None:
            raise self.update_error
        flow_id = spec.get("flow_id", "")
        if flow_id not in self.meta:
            raise NotFoundError(
                f"Flow '{flow_id}' not found",
                details={"flow_id": flow_id},
            )
        self.updated.append(spec)
        now = datetime.now(UTC)
        prev = self.meta[flow_id]
        meta = FlowMetadata(
            flow_id=flow_id,
            name=spec.get("name", prev.name),
            created_at=prev.created_at,
            updated_at=now,
            version=prev.version + 1,
            path=prev.path,
        )
        self.meta[flow_id] = meta
        return meta

    async def get(self, flow_id: str) -> FlowSpec:
        if self.get_error is not None:
            raise self.get_error
        if flow_id not in self.flows:
            raise NotFoundError(
                f"Flow '{flow_id}' not found",
                details={"flow_id": flow_id},
            )
        return self.flows[flow_id]

    async def list(self) -> list[FlowMetadata]:
        return list(self.meta.values())

    def validate(self, flow_spec: Any) -> ValidationResult:
        return self.validate_result


class FakeRunService:
    """Run service fake for MCP tool tests."""

    def __init__(self) -> None:
        self.started: list[tuple[str, Any]] = []
        self.start_error: Exception | None = None
        self.status_error: Exception | None = None
        self.resume_error: Exception | None = None
        self.last_decision: dict | None = None
        self.states: dict[str, RunState] = {}
        self.runs_by_flow: dict[str, list[RunState]] = {}
        self._slow_done = False

    async def start(self, flow_id: str, initial_input: Any = None) -> str:
        if self.start_error is not None:
            raise self.start_error
        self.started.append((flow_id, initial_input))
        run_id = f"run-{len(self.started)}"
        now = datetime.now(UTC)
        self.states[run_id] = RunState(
            run_id=run_id,
            flow_id=flow_id,
            status=RunStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        return run_id

    async def status(self, run_id: str) -> RunState:
        if self.status_error is not None:
            raise self.status_error
        if run_id not in self.states:
            raise NotFoundError(f"Run '{run_id}' not found", details={"run_id": run_id})
        return self.states[run_id]

    async def resume(self, run_id: str, decision: dict) -> RunState:
        if self.resume_error is not None:
            raise self.resume_error
        self.last_decision = decision
        if run_id not in self.states:
            raise NotFoundError(f"Run '{run_id}' not found", details={"run_id": run_id})
        state = self.states[run_id]
        if decision.get("approved"):
            state.status = RunStatus.COMPLETED
        else:
            state.status = RunStatus.FAILED
            state.error = "Run halted: node was not approved"
        state.updated_at = datetime.now(UTC)
        return state

    async def list_runs(self, flow_id: str) -> list[RunState]:
        runs = list(self.runs_by_flow.get(flow_id, []))
        runs.sort(key=lambda state: state.updated_at, reverse=True)
        return runs


class FakeSecretsService:
    """Secrets service fake for MCP tool tests (never exposes values in list)."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self.set_error: Exception | None = None

    async def set(self, key: str, value: str) -> None:
        if self.set_error is not None:
            raise self.set_error
        self._data[key] = value

    async def delete(self, key: str) -> bool:
        if key not in self._data:
            return False
        del self._data[key]
        return True

    async def list_keys(self) -> list[str]:
        return sorted(self._data.keys())

    async def has(self, key: str) -> bool:
        return key in self._data


class FakeSyncService:
    """Minimal sync service fake for MCP registration tests."""

    async def configure(self, **kwargs: Any) -> Any:
        from navbe.domains.sync.models import SyncConfig

        return SyncConfig(remote_url=kwargs.get("remote_url") or "")

    async def init(self) -> Any:
        from navbe.domains.sync.models import SyncStatus

        return SyncStatus(configured=True, initialized=True, branch="main")

    async def status(self) -> Any:
        from navbe.domains.sync.models import SyncStatus

        return SyncStatus(configured=False, initialized=False)

    async def branch_create(self, name: str) -> Any:
        from navbe.domains.sync.models import SyncStatus

        return SyncStatus(configured=True, initialized=True, branch=name)

    async def checkout(self, branch: str) -> Any:
        from navbe.domains.sync.models import SyncStatus

        return SyncStatus(configured=True, initialized=True, branch=branch)

    async def push(self, message: str | None = None) -> Any:
        from navbe.domains.sync.models import SyncResult

        return SyncResult(branch="main", message=message or "pushed")

    async def pull(self) -> Any:
        from navbe.domains.sync.models import SyncResult

        return SyncResult(branch="main", message="pulled")


def make_server(
    flow_service: FakeFlowService | None = None,
    run_service: FakeRunService | None = None,
    catalog_service: FakeCatalogService | None = None,
    secrets_service: FakeSecretsService | None = None,
    sync_service: FakeSyncService | None = None,
):
    """Build an MCP server with fakes."""
    from navbe.mcp_app.server import create_mcp_server

    return create_mcp_server(
        flow_service or FakeFlowService(),  # type: ignore[arg-type]
        run_service or FakeRunService(),  # type: ignore[arg-type]
        catalog_service or FakeCatalogService(),  # type: ignore[arg-type]
        secrets_service or FakeSecretsService(),  # type: ignore[arg-type]
        sync_service or FakeSyncService(),  # type: ignore[arg-type]
    )
