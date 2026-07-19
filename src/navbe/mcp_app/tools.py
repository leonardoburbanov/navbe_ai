"""Thin MCP tool adapters over FlowService, RunService, and CatalogService."""


import pydantic
from fastmcp import FastMCP

from navbe.core.exceptions import ValidationError
from navbe.domains.catalog.service import CatalogService
from navbe.domains.execution.service import RunService
from navbe.domains.flows.models import FlowSpec
from navbe.domains.flows.service import FlowService
from navbe.mcp_app.errors import mcp_tool_error_handler


def register_tools(
    mcp: FastMCP,
    *,
    flow_service: FlowService,
    run_service: RunService,
    catalog_service: CatalogService,
) -> None:
    """Register flow_* and catalog_* tools on ``mcp``.

    Underscored names (not dotted) so clients like Claude accept them:
    ``^[a-zA-Z0-9_-]{1,64}$``.
    """

    @mcp.tool(name="catalog_steps")
    @mcp_tool_error_handler
    async def catalog_steps() -> dict:
        """JSON Schema catalog of available step types (mirrors navbe://catalog/steps)."""
        return await catalog_service.get_steps_catalog()

    @mcp.tool(name="catalog_connectors")
    @mcp_tool_error_handler
    async def catalog_connectors() -> dict:
        """JSON Schema catalog of connector types (mirrors navbe://catalog/connectors)."""
        return await catalog_service.get_connectors_catalog()

    @mcp.tool(name="catalog_full")
    @mcp_tool_error_handler
    async def catalog_full() -> dict:
        """Combined steps + connectors catalog (mirrors navbe://catalog/full)."""
        return await catalog_service.get_full_catalog()

    @mcp.tool(name="flow_list")
    @mcp_tool_error_handler
    async def flow_list() -> dict:
        """List saved flow metadata (flow_id, name, version, path, timestamps)."""
        flows = await flow_service.list()
        return {"flows": [flow.model_dump(mode="json") for flow in flows]}

    @mcp.tool(name="flow_get")
    @mcp_tool_error_handler
    async def flow_get(flow_id: str) -> dict:
        """Return a persisted FlowSpec by id."""
        flow_spec = await flow_service.get(flow_id)
        return flow_spec.model_dump(by_alias=True)

    @mcp.tool(name="flow_create")
    @mcp_tool_error_handler
    async def flow_create(spec: dict) -> dict:
        """Create and persist a Flow from a FlowSpec dict.

        Validates structure and graph before saving. Consult
        ``catalog_steps`` / ``navbe://catalog/steps`` first for valid types.
        """
        metadata = await flow_service.create(spec)
        return {
            "flow_id": metadata.flow_id,
            "version": metadata.version,
            "path": metadata.path,
        }

    @mcp.tool(name="flow_validate")
    @mcp_tool_error_handler
    async def flow_validate(spec: dict) -> dict:
        """Validate a FlowSpec without persisting it.

        Use before ``flow_create`` / ``flow_update`` to catch issues cheaply.
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

    @mcp.tool(name="flow_update")
    @mcp_tool_error_handler
    async def flow_update(spec: dict) -> dict:
        """Validate and overwrite an existing flow (archives the prior version)."""
        metadata = await flow_service.update(spec)
        return {
            "flow_id": metadata.flow_id,
            "version": metadata.version,
            "path": metadata.path,
        }

    @mcp.tool(name="flow_run")
    @mcp_tool_error_handler
    async def flow_run(flow_id: str, initial_input: dict | None = None) -> dict:
        """Start execution of an existing flow.

        Returns immediately with a ``run_id``; poll ``flow_status`` for
        progress. Does not wait for the run to finish.
        """
        run_id = await run_service.start(flow_id, initial_input)
        return {"run_id": run_id, "status": "started"}

    @mcp.tool(name="flow_status")
    @mcp_tool_error_handler
    async def flow_status(run_id: str) -> dict:
        """Return current run state: status, current_node, outputs, error."""
        state = await run_service.status(run_id)
        return state.model_dump(mode="json")

    @mcp.tool(name="flow_resume")
    @mcp_tool_error_handler
    async def flow_resume(run_id: str, decision: dict) -> dict:
        """Resume a PAUSED run (typically after an approval node).

        ``decision`` shape: ``{"approved": bool, ...}``.
        """
        state = await run_service.resume(run_id, decision)
        return state.model_dump(mode="json")

    @mcp.tool(name="flow_list_runs")
    @mcp_tool_error_handler
    async def flow_list_runs(flow_id: str) -> dict:
        """List all runs for a flow, most recent first (by updated_at)."""
        runs = await run_service.list_runs(flow_id)
        return {"runs": [run.model_dump(mode="json") for run in runs]}
