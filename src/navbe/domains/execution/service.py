"""Orchestration use-cases for starting, canceling, and inspecting runs."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from navbe.core.exceptions import ExecutionError
from navbe.domains.connectors.service import ConnectorService
from navbe.domains.execution.diagram import build_step_executions, render_run_mermaid
from navbe.domains.execution.interfaces import ExecutionEngine
from navbe.domains.execution.models import (
    ACTIVE_RUN_STATUSES,
    RunDetail,
    RunState,
    RunStatus,
)
from navbe.domains.flows.models import FlowSpec
from navbe.domains.flows.service import FlowService

logger = logging.getLogger(__name__)

RunSettledCallback = Callable[[RunState], Awaitable[None]]


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
    """Facade for starting, inspecting, canceling, and resuming flow runs."""

    def __init__(
        self,
        engine: ExecutionEngine,
        flow_service: FlowService,
        connector_service: ConnectorService,
        *,
        on_settled: RunSettledCallback | None = None,
    ) -> None:
        """Create a run service with injected collaborators."""
        self._engine = engine
        self._flow_service = flow_service
        self._connector_service = connector_service
        self._on_settled = on_settled
        # Keep strong refs so create_task work is not GC'd mid-run.
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._tasks_by_run: dict[str, asyncio.Task[Any]] = {}

    def set_on_settled(self, callback: RunSettledCallback | None) -> None:
        """Attach or clear a post-settle hook (used by the scheduler)."""
        self._on_settled = callback

    async def is_flow_busy(self, flow_id: str) -> bool:
        """True when ``flow_id`` has a pending/running/paused run."""
        runs = await self._engine.list_runs(flow_id)
        return any(run.status in ACTIVE_RUN_STATUSES for run in runs)

    async def start(
        self,
        flow_id: str,
        initial_input: Any = None,
        *,
        wait: bool = False,
        timeout: float = 300.0,
        trigger: Literal["manual", "schedule"] = "manual",
        schedule_id: str | None = None,
        skip_if_busy: bool = False,
    ) -> str | None:
        """Fetch a flow, schedule execution, return run_id.

        When ``wait`` is True, block until the run settles (completed /
        failed / paused / cancelled) or ``timeout`` seconds elapse. The
        background run keeps going if the wait times out (shielded).

        When ``skip_if_busy`` is True and the flow is active, return None
        instead of raising (scheduler path). Manual starts raise.
        """
        if await self.is_flow_busy(flow_id):
            if skip_if_busy:
                logger.info("Skipping start for busy flow '%s'", flow_id)
                return None
            raise ExecutionError(
                f"Flow '{flow_id}' already has an active run "
                "(cancel it before starting another)",
                details={"flow_id": flow_id},
            )

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
                    trigger=trigger,
                    schedule_id=schedule_id,
                    created_at=now,
                    updated_at=now,
                ),
            )

        task = asyncio.create_task(
            self._run_and_settle(flow_spec, run_id, initial_input)
        )
        self._background_tasks.add(task)
        self._tasks_by_run[run_id] = task

        def _cleanup(done: asyncio.Task[Any]) -> None:
            self._background_tasks.discard(done)
            self._tasks_by_run.pop(run_id, None)

        task.add_done_callback(_cleanup)

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

    async def _run_and_settle(
        self,
        flow_spec: FlowSpec,
        run_id: str,
        initial_input: Any,
    ) -> RunState:
        """Run the engine and invoke the settled callback."""
        state = await self._engine.run(flow_spec, run_id, initial_input)
        if self._on_settled is not None:
            try:
                await self._on_settled(state)
            except Exception:
                logger.exception("on_settled callback failed for run '%s'", run_id)
        return state

    async def cancel(self, run_id: str) -> RunState:
        """Cancel an active run; no-op-ish error if already terminal."""
        state = await self._engine.get_status(run_id)
        if state.status not in ACTIVE_RUN_STATUSES:
            raise ExecutionError(
                f"Run '{run_id}' is not active (status={state.status})",
                details={"run_id": run_id, "status": str(state.status)},
            )

        task = self._tasks_by_run.get(run_id)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Live cancel may already have persisted CANCELLED; orphaned pending
        # runs (no in-process task) still need an explicit write.
        try:
            latest = await self._engine.get_status(run_id)
            if latest.status not in ACTIVE_RUN_STATUSES:
                return latest
            state = latest
        except Exception:
            pass

        now = datetime.now(UTC)
        cancelled = state.model_copy(
            update={
                "status": RunStatus.CANCELLED,
                "error": "cancelled",
                "updated_at": now,
            }
        )
        repo = getattr(self._engine, "repository", None)
        if repo is not None:
            await repo.save_state(run_id, cancelled)
        return cancelled

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
        state = await self._engine.resume(run_id, decision)
        if self._on_settled is not None:
            try:
                await self._on_settled(state)
            except Exception:
                logger.exception("on_settled callback failed for run '%s'", run_id)
        return state

    async def list_runs(self, flow_id: str | None = None) -> list[RunState]:
        """List runs for a flow (or all runs), most recent first (by updated_at)."""
        return await self._engine.list_runs(flow_id)

    async def list_schedule_runs(self, schedule_id: str | None = None) -> list[RunState]:
        """List runs triggered by schedules (optionally one schedule_id)."""
        runs = await self._engine.list_runs(None)
        scheduled = [r for r in runs if r.trigger == "schedule"]
        if schedule_id is not None:
            scheduled = [r for r in scheduled if r.schedule_id == schedule_id]
        return scheduled
