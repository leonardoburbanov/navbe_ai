"""Orchestration use-cases for starting and inspecting runs."""

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.service import ConnectorService
from navbe.domains.execution.diagram import build_step_executions, render_run_mermaid
from navbe.domains.execution.interfaces import ExecutionEngine
from navbe.domains.execution.models import RunDetail, RunState, RunStatus
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
        # Keep strong refs so create_task work is not GC'd mid-run.
        self._background_tasks: set[asyncio.Task[Any]] = set()

    async def start(
        self,
        flow_id: str,
        initial_input: Any = None,
        *,
        wait: bool = False,
        timeout: float = 300.0,
    ) -> str:
        """Fetch a flow, schedule execution, return run_id.

        When ``wait`` is True, block until the run settles (completed /
        failed / paused) or ``timeout`` seconds elapse. The background
        run keeps going if the wait times out (shielded).
        """
        flow_spec = await self._flow_service.get(flow_id)
        run_id = str(uuid4())
        now = datetime.now(UTC)
        repo = getattr(self._engine, "repository", None)
        if repo is not None:
            await repo.save_state(
                run_id,
                RunState(
                    run_id=run_id,
                    flow_id=flow_spec.flow_id,
                    status=RunStatus.PENDING,
                    created_at=now,
                    updated_at=now,
                ),
            )

        task = asyncio.create_task(self._engine.run(flow_spec, run_id, initial_input))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        if wait:
            try:
                # shield: canceling the wait must not cancel the run.
                await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
            except TimeoutError as exc:
                raise ExecutionError(
                    f"Run '{run_id}' did not settle within {timeout}s",
                    details={"run_id": run_id, "timeout": timeout},
                ) from exc
        return run_id

    async def status(self, run_id: str) -> RunState:
        """Return the latest run status."""
        return await self._engine.get_status(run_id)

    async def detail(self, run_id: str) -> RunDetail:
        """Return run state, step timeline, and Mermaid diagram."""
        state = await self._engine.get_status(run_id)
        flow = await self._flow_service.get(state.flow_id)
        repo = getattr(self._engine, "repository", None)
        traces = await repo.list_traces(run_id) if repo is not None else []
        steps = build_step_executions(
            flow,
            traces,
            status=state.status,
            current_node=state.current_node,
        )
        diagram = render_run_mermaid(
            flow,
            traces,
            state.status,
            current_node=state.current_node,
        )
        return RunDetail(state=state, steps=steps, diagram=diagram)

    async def resume(self, run_id: str, decision: dict) -> RunState:
        """Resume a paused run."""
        return await self._engine.resume(run_id, decision)

    async def list_runs(self, flow_id: str | None = None) -> list[RunState]:
        """List runs for a flow (or all runs), most recent first (by updated_at)."""
        return await self._engine.list_runs(flow_id)
