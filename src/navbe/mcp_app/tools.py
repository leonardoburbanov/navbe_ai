"""Thin MCP tool adapters over FlowService, RunService, and CatalogService."""


import pydantic
from fastmcp import FastMCP

from navbe.core.exceptions import ValidationError
from navbe.domains.catalog.service import CatalogService
from navbe.domains.execution.models import RunDetail
from navbe.domains.execution.service import RunService
from navbe.domains.flows.models import FlowSpec
from navbe.domains.flows.service import FlowService
from navbe.domains.secrets.service import SecretsService
from navbe.domains.sync.github_auth import GitHubAuthService
from navbe.domains.sync.service import SyncService
from navbe.mcp_app.errors import mcp_tool_error_handler
from navbe.mcp_app.guide import NAVBE_HOWTO


def _run_detail_payload(detail: RunDetail) -> dict:
    """Flatten RunDetail into the MCP response shape (state + steps + diagram)."""
    payload = detail.state.model_dump(mode="json")
    payload["steps"] = [step.model_dump(mode="json") for step in detail.steps]
    payload["diagram"] = detail.diagram
    return payload


def register_tools(
    mcp: FastMCP,
    *,
    flow_service: FlowService,
    run_service: RunService,
    catalog_service: CatalogService,
    secrets_service: SecretsService,
    sync_service: SyncService,
    github_auth_service: GitHubAuthService,
) -> None:
    """Register flow_*, catalog_*, secret_*, auth_*, and sync_* tools on ``mcp``.

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
    async def secret_set(key: str, value: str, app: str | None = None) -> dict:
        """Store a secret in the local credentials JSON file.

        Optional ``app`` slug (e.g. resend). Returns masked hint, never the value.
        Prefer this over editing .env for agent keys.
        """
        hint = await secrets_service.set(key, value, app=app)
        return {
            "key": hint.key,
            "stored": True,
            "hint": hint.hint,
            "app": hint.app,
        }

    @mcp.tool(name="secret_list")
    @mcp_tool_error_handler
    async def secret_list() -> dict:
        """List credentials in the JSON file (keys + masked items; never values)."""
        keys = await secrets_service.list_keys()
        items = await secrets_service.list_credentials()
        return {
            "keys": keys,
            "items": [item.model_dump(mode="json") for item in items],
        }

    @mcp.tool(name="secret_hint")
    @mcp_tool_error_handler
    async def secret_hint(key: str) -> dict:
        """Return masked metadata for a key (store or env); never the value."""
        hint = await secrets_service.get_hint(key)
        return hint.model_dump(mode="json")

    @mcp.tool(name="secret_delete")
    @mcp_tool_error_handler
    async def secret_delete(key: str) -> dict:
        """Delete a key from the local credentials JSON file."""
        deleted = await secrets_service.delete(key)
        return {"key": key, "deleted": deleted}

    @mcp.tool(name="secret_has")
    @mcp_tool_error_handler
    async def secret_has(key: str) -> dict:
        """Check whether a key exists in the credentials file (no value)."""
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
    async def flow_run(
        flow_id: str,
        initial_input: dict | None = None,
        wait: bool = True,
        timeout: float = 300.0,
    ) -> dict:
        """Start a flow run. Ask the user before calling.

        Default ``wait=true``: blocks until completed / failed / paused, then
        returns the full status including ``steps`` and Mermaid ``diagram``.
        ALWAYS show the user the ``diagram`` as a mermaid fenced code block
        (and a short ``steps`` summary) — do not only report business side
        effects. Use ``wait=false`` only for fire-and-forget, then poll
        ``flow_status``.
        """
        run_id = await run_service.start(
            flow_id,
            initial_input,
            wait=wait,
            timeout=timeout,
        )
        if not wait:
            return {"run_id": run_id, "status": "started"}
        detail = await run_service.detail(run_id)
        return _run_detail_payload(detail)

    @mcp.tool(name="flow_status")
    @mcp_tool_error_handler
    async def flow_status(run_id: str) -> dict:
        """Poll run state: status, steps timeline, Mermaid diagram, outputs, error.

        ALWAYS show the user the ``diagram`` Mermaid block when status is
        completed, failed, or paused — do not omit it.
        """
        detail = await run_service.detail(run_id)
        return _run_detail_payload(detail)

    @mcp.tool(name="flow_resume")
    @mcp_tool_error_handler
    async def flow_resume(run_id: str, decision: dict) -> dict:
        """Resume a paused approval node. decision: {\"approved\": bool, ...}.

        Returns steps + diagram. ALWAYS show the user the ``diagram`` Mermaid block.
        """
        await run_service.resume(run_id, decision)
        detail = await run_service.detail(run_id)
        return _run_detail_payload(detail)

    @mcp.tool(name="flow_list_runs")
    @mcp_tool_error_handler
    async def flow_list_runs(flow_id: str) -> dict:
        """List runs for one flow, most recent first."""
        runs = await run_service.list_runs(flow_id)
        return {"runs": [run.model_dump(mode="json") for run in runs]}

    @mcp.tool(name="auth_github_begin")
    @mcp_tool_error_handler
    async def auth_github_begin() -> dict:
        """Start GitHub Device Flow. Show user_code + verification_uri to the user.

        Then call auth_github_complete. Never returns tokens.
        """
        result = await github_auth_service.begin()
        return result.model_dump()

    @mcp.tool(name="auth_github_complete")
    @mcp_tool_error_handler
    async def auth_github_complete(timeout: float = 300.0) -> dict:
        """Poll until the user finishes device login; store managed token.

        Never returns the token — only logged_in / login / pending.
        """
        status = await github_auth_service.complete(timeout=timeout)
        return status.model_dump()

    @mcp.tool(name="auth_github_status")
    @mcp_tool_error_handler
    async def auth_github_status() -> dict:
        """GitHub App presence (logged_in, install/uninstall URLs) — never the token."""
        status = await github_auth_service.status()
        return status.model_dump()

    @mcp.tool(name="auth_github_logout")
    @mcp_tool_error_handler
    async def auth_github_logout() -> dict:
        """Clear the managed GitHub OAuth token."""
        status = await github_auth_service.logout()
        return status.model_dump()

    @mcp.tool(name="auth_github_repos")
    @mcp_tool_error_handler
    async def auth_github_repos() -> dict:
        """List repos granted to the installed Navbe AI GitHub App.

        Use this before sync_connect so the user can pick owner/name.
        """
        repos = await github_auth_service.list_accessible_repos()
        return {"repos": [repo.model_dump() for repo in repos]}

    @mcp.tool(name="sync_configure")
    @mcp_tool_error_handler
    async def sync_configure(
        remote_url: str | None = None,
        local_repo_dir: str | None = None,
        flows_subdir: str | None = None,
        default_branch: str | None = None,
    ) -> dict:
        """Set GitHub sync settings. Auth via auth_github_* (Device Flow), never here.

        Workspace layout: flows/<id>/flow.json (+ reserved connectors/destinations/schedules).
        """
        config = await sync_service.configure(
            remote_url=remote_url,
            local_repo_dir=local_repo_dir,
            flows_subdir=flows_subdir,
            default_branch=default_branch,
        )
        return config.model_dump()

    @mcp.tool(name="sync_connect")
    @mcp_tool_error_handler
    async def sync_connect(
        owner: str,
        name: str,
        private: bool = True,
        local_repo_dir: str | None = None,
        default_branch: str | None = None,
    ) -> dict:
        """Create-or-bind owner/name on GitHub, configure remote, and init clone.

        Requires prior auth_github_begin + auth_github_complete.
        """
        status = await sync_service.connect(
            owner=owner,
            name=name,
            private=private,
            local_repo_dir=local_repo_dir,
            default_branch=default_branch,
        )
        return status.model_dump()

    @mcp.tool(name="sync_init")
    @mcp_tool_error_handler
    async def sync_init() -> dict:
        """Clone or bind the configured GitHub repo (workspace mirror)."""
        status = await sync_service.init()
        return status.model_dump()

    @mcp.tool(name="sync_status")
    @mcp_tool_error_handler
    async def sync_status() -> dict:
        """Branch, dirty flag, OAuth presence, and local vs remote asset counts."""
        status = await sync_service.status()
        return status.model_dump()

    @mcp.tool(name="sync_branch_create")
    @mcp_tool_error_handler
    async def sync_branch_create(name: str) -> dict:
        """Create and checkout a branch from default_branch."""
        status = await sync_service.branch_create(name)
        return status.model_dump()

    @mcp.tool(name="sync_checkout")
    @mcp_tool_error_handler
    async def sync_checkout(branch: str) -> dict:
        """Checkout an existing branch (fails if working tree dirty)."""
        status = await sync_service.checkout(branch)
        return status.model_dump()

    @mcp.tool(name="sync_push")
    @mcp_tool_error_handler
    async def sync_push(message: str | None = None) -> dict:
        """Push local workspace assets to GitHub (flows registered today)."""
        result = await sync_service.push(message)
        return result.model_dump()

    @mcp.tool(name="sync_pull")
    @mcp_tool_error_handler
    async def sync_pull() -> dict:
        """Pull workspace assets from GitHub into Navbe (ff-only)."""
        result = await sync_service.pull()
        return result.model_dump()
