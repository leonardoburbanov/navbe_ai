"""Thin MCP tool adapters over FlowService, RunService, and CatalogService."""


import pydantic
from fastmcp import FastMCP

from navbe.core.exceptions import ValidationError
from navbe.domains.catalog.service import CatalogService
from navbe.domains.execution.service import RunService
from navbe.domains.flows.models import FlowSpec
from navbe.domains.flows.service import FlowService
from navbe.domains.secrets.service import SecretsService
from navbe.mcp_app.errors import mcp_tool_error_handler
from navbe.mcp_app.guide import NAVBE_HOWTO


def register_tools(
    mcp: FastMCP,
    *,
    flow_service: FlowService,
    run_service: RunService,
    catalog_service: CatalogService,
    secrets_service: SecretsService,
) -> None:
    """Register flow_*, catalog_*, and secret_* tools on ``mcp``.

    Underscored names (not dotted) so clients like Claude accept them:
    ``^[a-zA-Z0-9_-]{1,64}$``.
    """

    @mcp.tool(name="navbe_howto")
    @mcp_tool_error_handler
    async def navbe_howto() -> dict:
        """Read this first on Claude Desktop: Navbe tool playbook.

        Returns the discover → validate → create → ask → run loop, FlowSpec
        shape, and tool map. Prefer this over ``navbe://`` resources.
        """
        return {"guide": NAVBE_HOWTO}

    @mcp.tool(name="secret_set")
    @mcp_tool_error_handler
    async def secret_set(key: str, value: str) -> dict:
        """Store a secret in the local credentials JSON file.

        Never returns the value. Prefer this over editing .env for agent keys.
        """
        await secrets_service.set(key, value)
        return {"key": key, "stored": True}

    @mcp.tool(name="secret_list")
    @mcp_tool_error_handler
    async def secret_list() -> dict:
        """List credential keys stored in the local JSON file (never values)."""
        keys = await secrets_service.list_keys()
        return {"keys": keys}

    @mcp.tool(name="secret_delete")
    @mcp_tool_error_handler
    async def secret_delete(key: str) -> dict:
        """Delete a key from the local credentials JSON file."""
        deleted = await secrets_service.delete(key)
        return {"key": key, "deleted": deleted}

    @mcp.tool(name="secret_has")
    @mcp_tool_error_handler
    async def secret_has(key: str) -> dict:
        """Check whether a key exists in credentials file or environment (no value)."""
        present = await secrets_service.has(key)
        return {"key": key, "present": present}

    @mcp.tool(name="catalog_steps")
    @mcp_tool_error_handler
    async def catalog_steps() -> dict:
        """List valid step_type values and config schemas. Call before authoring.

        Prefer this tool over ``navbe://catalog/steps`` on Claude Desktop.
        """
        return await catalog_service.get_steps_catalog()

    @mcp.tool(name="catalog_connectors")
    @mcp_tool_error_handler
    async def catalog_connectors() -> dict:
        """List valid connector types and config schemas. Call before authoring.

        Prefer this tool over ``navbe://catalog/connectors`` on Claude Desktop.
        """
        return await catalog_service.get_connectors_catalog()

    @mcp.tool(name="catalog_full")
    @mcp_tool_error_handler
    async def catalog_full() -> dict:
        """Combined steps + connectors catalogs. Call before authoring a FlowSpec."""
        return await catalog_service.get_full_catalog()

    @mcp.tool(name="flow_list")
    @mcp_tool_error_handler
    async def flow_list() -> dict:
        """List saved flows. Call before create to avoid duplicates."""
        flows = await flow_service.list()
        return {"flows": [flow.model_dump(mode="json") for flow in flows]}

    @mcp.tool(name="flow_get")
    @mcp_tool_error_handler
    async def flow_get(flow_id: str) -> dict:
        """Return a persisted FlowSpec by id. Call before flow_update."""
        flow_spec = await flow_service.get(flow_id)
        return flow_spec.model_dump(by_alias=True)

    @mcp.tool(name="flow_create")
    @mcp_tool_error_handler
    async def flow_create(spec: dict) -> dict:
        """Create and persist a FlowSpec. Call catalog_steps + flow_validate first.

        Do not run the flow here — use flow_run only after user confirmation.
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
        """Validate a FlowSpec without saving. Use before flow_create / flow_update."""
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
        """Overwrite an existing flow (archives prior version). Call flow_get first."""
        metadata = await flow_service.update(spec)
        return {
            "flow_id": metadata.flow_id,
            "version": metadata.version,
            "path": metadata.path,
        }

    @mcp.tool(name="flow_run")
    @mcp_tool_error_handler
    async def flow_run(flow_id: str, initial_input: dict | None = None) -> dict:
        """Start a flow run. Ask the user before calling. Returns run_id immediately.

        Then poll flow_status until completed / failed / paused.
        """
        run_id = await run_service.start(flow_id, initial_input)
        return {"run_id": run_id, "status": "started"}

    @mcp.tool(name="flow_status")
    @mcp_tool_error_handler
    async def flow_status(run_id: str) -> dict:
        """Poll run state: status, current_node, outputs, error."""
        state = await run_service.status(run_id)
        return state.model_dump(mode="json")

    @mcp.tool(name="flow_resume")
    @mcp_tool_error_handler
    async def flow_resume(run_id: str, decision: dict) -> dict:
        """Resume a paused approval node. decision: {\"approved\": bool, ...}."""
        state = await run_service.resume(run_id, decision)
        return state.model_dump(mode="json")

    @mcp.tool(name="flow_list_runs")
    @mcp_tool_error_handler
    async def flow_list_runs(flow_id: str) -> dict:
        """List runs for one flow, most recent first."""
        runs = await run_service.list_runs(flow_id)
        return {"runs": [run.model_dump(mode="json") for run in runs]}
