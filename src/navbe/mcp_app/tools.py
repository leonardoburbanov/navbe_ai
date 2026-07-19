"""Thin MCP tool adapters over FlowService and RunService."""


import pydantic
from fastmcp import FastMCP

from navbe.core.exceptions import ValidationError
from navbe.domains.execution.service import RunService
from navbe.domains.flows.models import FlowSpec
from navbe.domains.flows.service import FlowService
from navbe.mcp_app.errors import mcp_tool_error_handler


def register_tools(
    mcp: FastMCP,
    *,
    flow_service: FlowService,
    run_service: RunService,
) -> None:
    """Register flow.* tools on ``mcp``."""

    @mcp.tool(name="flow.create")
    @mcp_tool_error_handler
    async def flow_create(spec: dict) -> dict:
        """Create and persist a Flow from a FlowSpec dict.

        Validates structure and graph before saving. Consult
        ``navbe://catalog/steps`` and ``navbe://catalog/connectors`` first
        for valid ``step_type`` / connector values.
        """
        metadata = await flow_service.create(spec)
        return {
            "flow_id": metadata.flow_id,
            "version": metadata.version,
            "path": metadata.path,
        }

    @mcp.tool(name="flow.validate")
    @mcp_tool_error_handler
    async def flow_validate(spec: dict) -> dict:
        """Validate a FlowSpec without persisting it.

        Use before ``flow.create`` to catch graph/shape issues cheaply.
        """
        try:
            flow_spec = FlowSpec.model_validate(spec)
        except pydantic.ValidationError as exc:
            raise ValidationError(
                "Invalid FlowSpec structure",
                details={"errors": exc.errors()},
            ) from exc
        result = flow_service.validate(flow_spec)
        return result.model_dump()

    @mcp.tool(name="flow.run")
    @mcp_tool_error_handler
    async def flow_run(flow_id: str, initial_input: dict | None = None) -> dict:
        """Start execution of an existing flow.

        Returns immediately with a ``run_id``; poll ``flow.status`` for
        progress. Does not wait for the run to finish.
        """
        run_id = await run_service.start(flow_id, initial_input)
        return {"run_id": run_id, "status": "started"}

    @mcp.tool(name="flow.status")
    @mcp_tool_error_handler
    async def flow_status(run_id: str) -> dict:
        """Return current run state: status, current_node, outputs, error."""
        state = await run_service.status(run_id)
        return state.model_dump(mode="json")

    @mcp.tool(name="flow.resume")
    @mcp_tool_error_handler
    async def flow_resume(run_id: str, decision: dict) -> dict:
        """Resume a PAUSED run (typically after an approval node).

        ``decision`` shape: ``{"approved": bool, ...}``.
        """
        state = await run_service.resume(run_id, decision)
        return state.model_dump(mode="json")

    @mcp.tool(name="flow.list_runs")
    @mcp_tool_error_handler
    async def flow_list_runs(flow_id: str) -> dict:
        """List all runs for a flow, most recent first (by updated_at)."""
        runs = await run_service.list_runs(flow_id)
        return {"runs": [run.model_dump(mode="json") for run in runs]}
