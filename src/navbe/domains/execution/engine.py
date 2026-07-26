"""LangGraph-backed execution engine."""

import asyncio
from datetime import UTC, datetime
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from navbe.core.exceptions import ExecutionError, NavbeError, NotFoundError
from navbe.domains.execution.graph_compiler import compile_flow
from navbe.domains.execution.interfaces import RunRepository
from navbe.domains.execution.models import NodeTrace, RunState, RunStatus
from navbe.domains.flows.models import FlowSpec


class LangGraphEngine:
    """Execute FlowSpecs via LangGraph with SQLite checkpoints."""

    def __init__(
        self,
        run_repository: RunRepository,
        checkpoint_db_path: str,
        *,
        resolve_connectors: Any | None = None,
        get_flow_spec: Any | None = None,
        llm_client: Any | None = None,
    ) -> None:
        """Create an engine with repository + checkpoint path."""
        self._repository = run_repository
        self._checkpoint_db_path = checkpoint_db_path
        self._resolve_connectors = resolve_connectors
        self._get_flow_spec = get_flow_spec
        self._llm_client = llm_client
        self._run_flows: dict[str, FlowSpec] = {}

    @property
    def repository(self) -> RunRepository:
        """Expose the run repository for callers that need list helpers."""
        return self._repository

    async def list_runs(self, flow_id: str | None = None) -> list[RunState]:
        """List runs for a flow (or all runs), most recent first."""
        return await self._repository.list_runs(flow_id)

    async def _resolve_connectors_map(self, flow_spec: FlowSpec) -> dict[str, Any]:
        """Resolve runnable connector instances for a flow (not checkpointed)."""
        if self._resolve_connectors is None:
            return {}
        return await self._resolve_connectors(flow_spec)

    async def _on_trace(self, run_id: str, trace: NodeTrace) -> None:
        """Persist one node trace for ``run_id``."""
        await self._repository.save_trace(run_id, trace)

    def _compile(
        self,
        flow_spec: FlowSpec,
        *,
        run_id: str,
        connectors: dict[str, Any],
    ) -> Any:
        """Compile a flow with connectors and trace callback for this run."""

        async def on_trace(trace: NodeTrace) -> None:
            await self._on_trace(run_id, trace)

        return compile_flow(
            flow_spec,
            llm_client=self._llm_client,
            connectors=connectors,
            on_trace=on_trace,
        )

    async def _load_prior_meta(self, run_id: str) -> tuple[Any, Any]:
        """Return (trigger, schedule_id) from a prior pending state if present."""
        try:
            prior = await self._repository.get_state(run_id)
            return prior.trigger, prior.schedule_id
        except Exception:
            # Missing prior state (NotFoundError / KeyError from fakes) → defaults.
            return "manual", None

    async def run(self, flow_spec: FlowSpec, run_id: str, initial_input: Any) -> RunState:
        """Compile and invoke a flow, persisting the final RunState."""
        now = datetime.now(UTC)
        self._run_flows[run_id] = flow_spec
        trigger, schedule_id = await self._load_prior_meta(run_id)
        await self._repository.save_state(
            run_id,
            RunState(
                run_id=run_id,
                flow_id=flow_spec.flow_id,
                status=RunStatus.RUNNING,
                trigger=trigger,
                schedule_id=schedule_id,
                created_at=now,
                updated_at=now,
            ),
        )
        connectors = await self._resolve_connectors_map(flow_spec)
        graph = self._compile(flow_spec, run_id=run_id, connectors=connectors)
        # Connectors stay out of state — AsyncSqliteSaver cannot msgpack them.
        initial_state = {
            "node_outputs": {},
            "flow_vars": {},
            "current_input": initial_input,
        }

        try:
            async with AsyncSqliteSaver.from_conn_string(self._checkpoint_db_path) as checkpointer:
                app = graph.compile(checkpointer=checkpointer)
                config = cast(
                    RunnableConfig,
                    {"configurable": {"thread_id": run_id}},
                )
                final_state = await app.ainvoke(initial_state, config=config)

            if isinstance(final_state, dict) and final_state.get("__interrupt__"):
                interrupt = final_state["__interrupt__"][0]
                node_id = None
                if hasattr(interrupt, "value") and isinstance(interrupt.value, dict):
                    node_id = interrupt.value.get("node_id")
                run_state = RunState(
                    run_id=run_id,
                    flow_id=flow_spec.flow_id,
                    status=RunStatus.PAUSED,
                    node_outputs=final_state.get("node_outputs", {}),
                    current_node=node_id,
                    trigger=trigger,
                    schedule_id=schedule_id,
                    created_at=now,
                    updated_at=datetime.now(UTC),
                )
            else:
                run_state = RunState(
                    run_id=run_id,
                    flow_id=flow_spec.flow_id,
                    status=RunStatus.COMPLETED,
                    node_outputs=final_state.get("node_outputs", {}),
                    trigger=trigger,
                    schedule_id=schedule_id,
                    created_at=now,
                    updated_at=datetime.now(UTC),
                )
        except asyncio.CancelledError:
            run_state = RunState(
                run_id=run_id,
                flow_id=flow_spec.flow_id,
                status=RunStatus.CANCELLED,
                error="cancelled",
                trigger=trigger,
                schedule_id=schedule_id,
                created_at=now,
                updated_at=datetime.now(UTC),
            )
            await self._repository.save_state(run_id, run_state)
            raise
        except NavbeError as exc:
            run_state = RunState(
                run_id=run_id,
                flow_id=flow_spec.flow_id,
                status=RunStatus.FAILED,
                error=exc.message,
                trigger=trigger,
                schedule_id=schedule_id,
                created_at=now,
                updated_at=datetime.now(UTC),
            )
        except Exception as exc:
            run_state = RunState(
                run_id=run_id,
                flow_id=flow_spec.flow_id,
                status=RunStatus.FAILED,
                error=str(exc),
                trigger=trigger,
                schedule_id=schedule_id,
                created_at=now,
                updated_at=datetime.now(UTC),
            )

        await self._repository.save_state(run_id, run_state)
        return run_state

    async def get_status(self, run_id: str) -> RunState:
        """Return persisted run state."""
        return await self._repository.get_state(run_id)

    async def _get_flow_spec_for_run(self, run_id: str) -> FlowSpec:
        """Recover the FlowSpec used for a run."""
        if run_id in self._run_flows:
            return self._run_flows[run_id]
        if self._get_flow_spec is not None:
            state = await self._repository.get_state(run_id)
            return await self._get_flow_spec(state.flow_id)
        raise NotFoundError(
            f"FlowSpec for run '{run_id}' is not available",
            details={"run_id": run_id},
        )

    async def resume(self, run_id: str, decision: dict) -> RunState:
        """Resume a paused HITL run with ``Command(resume=decision)``."""
        prior = await self._repository.get_state(run_id)
        if prior.status != RunStatus.PAUSED:
            raise ExecutionError(
                f"Run '{run_id}' is not paused (status={prior.status})",
                details={"run_id": run_id, "status": str(prior.status)},
            )
        flow_spec = await self._get_flow_spec_for_run(run_id)
        connectors = await self._resolve_connectors_map(flow_spec)
        graph = self._compile(flow_spec, run_id=run_id, connectors=connectors)
        now = datetime.now(UTC)

        try:
            async with AsyncSqliteSaver.from_conn_string(self._checkpoint_db_path) as checkpointer:
                app = graph.compile(checkpointer=checkpointer)
                config = cast(
                    RunnableConfig,
                    {"configurable": {"thread_id": run_id}},
                )
                final_state = await app.ainvoke(Command(resume=decision), config=config)

            if isinstance(final_state, dict) and final_state.get("__interrupt__"):
                interrupt = final_state["__interrupt__"][0]
                node_id = None
                if hasattr(interrupt, "value") and isinstance(interrupt.value, dict):
                    node_id = interrupt.value.get("node_id")
                run_state = RunState(
                    run_id=run_id,
                    flow_id=flow_spec.flow_id,
                    status=RunStatus.PAUSED,
                    node_outputs=final_state.get("node_outputs", prior.node_outputs),
                    current_node=node_id,
                    trigger=prior.trigger,
                    schedule_id=prior.schedule_id,
                    created_at=prior.created_at,
                    updated_at=now,
                )
            else:
                run_state = RunState(
                    run_id=run_id,
                    flow_id=flow_spec.flow_id,
                    status=RunStatus.COMPLETED,
                    node_outputs=final_state.get("node_outputs", {}),
                    trigger=prior.trigger,
                    schedule_id=prior.schedule_id,
                    created_at=prior.created_at,
                    updated_at=now,
                )
        except NavbeError as exc:
            run_state = RunState(
                run_id=run_id,
                flow_id=flow_spec.flow_id,
                status=RunStatus.FAILED,
                error=exc.message,
                node_outputs=prior.node_outputs,
                trigger=prior.trigger,
                schedule_id=prior.schedule_id,
                created_at=prior.created_at,
                updated_at=now,
            )
        except Exception as exc:
            run_state = RunState(
                run_id=run_id,
                flow_id=flow_spec.flow_id,
                status=RunStatus.FAILED,
                error=str(exc),
                node_outputs=prior.node_outputs,
                trigger=prior.trigger,
                schedule_id=prior.schedule_id,
                created_at=prior.created_at,
                updated_at=now,
            )

        await self._repository.save_state(run_id, run_state)
        return run_state
