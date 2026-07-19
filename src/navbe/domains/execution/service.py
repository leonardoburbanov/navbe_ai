"""Orchestration use-cases for starting and inspecting runs."""

from typing import Any
from uuid import uuid4

from navbe.domains.connectors.service import ConnectorService
from navbe.domains.execution.interfaces import ExecutionEngine
from navbe.domains.execution.models import RunState
from navbe.domains.flows.models import FlowSpec
from navbe.domains.flows.service import FlowService


async def resolve_connector_configs(
    flow_spec: FlowSpec,
    connector_service: ConnectorService,
) -> dict[str, Any]:
    """Resolve FlowSpec connector declarations into runnable instances."""
    resolved: dict[str, Any] = {}
    for name, instance in flow_spec.connectors.items():
        resolved[name] = await connector_service.resolve(
            name,
            {"type": instance.type, "config": instance.config},
        )
    return resolved


class RunService:
    """Facade for starting, inspecting, and resuming flow runs."""

    def __init__(
        self,
        engine: ExecutionEngine,
        flow_service: FlowService,
        connector_service: ConnectorService,
    ) -> None:
        """Create a run service with injected collaborators."""
        self._engine = engine
        self._flow_service = flow_service
        self._connector_service = connector_service

    async def start(self, flow_id: str, initial_input: Any = None) -> str:
        """Fetch a flow and execute it; return the new run_id."""
        flow_spec = await self._flow_service.get(flow_id)
        run_id = str(uuid4())
        await self._engine.run(flow_spec, run_id, initial_input)
        return run_id

    async def status(self, run_id: str) -> RunState:
        """Return the latest run status."""
        return await self._engine.get_status(run_id)

    async def resume(self, run_id: str, decision: dict) -> RunState:
        """Resume a paused run."""
        return await self._engine.resume(run_id, decision)

    async def list_runs(self, flow_id: str) -> list[RunState]:
        """List runs for a flow via the engine Protocol."""
        return await self._engine.list_runs(flow_id)
