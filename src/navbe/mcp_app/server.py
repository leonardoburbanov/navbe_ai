"""FastMCP server factory — dependencies injected by the caller."""

from fastmcp import FastMCP

from navbe.core.config import get_settings
from navbe.domains.catalog.service import CatalogService
from navbe.domains.execution.service import RunService
from navbe.domains.flows.service import FlowService
from navbe.domains.secrets.service import SecretsService
from navbe.domains.sync.github_auth import GitHubAuthService
from navbe.domains.sync.service import SyncService
from navbe.mcp_app.guide import register_prompts
from navbe.mcp_app.resources import register_resources
from navbe.mcp_app.tools import register_tools


def create_mcp_server(
    flow_service: FlowService,
    run_service: RunService,
    catalog_service: CatalogService,
    secrets_service: SecretsService,
    sync_service: SyncService,
    github_auth_service: GitHubAuthService,
) -> FastMCP:
    """Build a FastMCP server with flow/catalog/secret/auth/sync tools and resources."""
    settings = get_settings()
    mcp = FastMCP(settings.mcp_server_name)
    register_tools(
        mcp,
        flow_service=flow_service,
        run_service=run_service,
        catalog_service=catalog_service,
        secrets_service=secrets_service,
        sync_service=sync_service,
        github_auth_service=github_auth_service,
    )
    register_resources(
        mcp,
        catalog_service=catalog_service,
        flow_service=flow_service,
    )
    register_prompts(mcp)
    return mcp
