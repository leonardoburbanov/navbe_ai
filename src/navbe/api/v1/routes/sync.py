"""REST mirror of sync + GitHub auth MCP tools."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from navbe.api.errors import to_http_exception
from navbe.core.exceptions import NavbeError
from navbe.dependencies import get_github_auth_service, get_sync_service
from navbe.domains.sync.github_auth import GitHubAuthService
from navbe.domains.sync.service import SyncService

router = APIRouter()


class SyncConfigureBody(BaseModel):
    """Optional fields for sync_configure."""

    remote_url: str | None = None
    local_repo_dir: str | None = None
    flows_subdir: str | None = None
    default_branch: str | None = None


class SyncConnectBody(BaseModel):
    """Create-or-bind a GitHub repo for workspace sync."""

    owner: str
    name: str
    private: bool = True
    local_repo_dir: str | None = None
    default_branch: str | None = None


class SyncPushBody(BaseModel):
    """Optional commit message for sync_push."""

    message: str | None = None


class SyncBranchBody(BaseModel):
    """Branch name payload."""

    name: str


class SyncCheckoutBody(BaseModel):
    """Checkout branch payload."""

    branch: str


class AuthCompleteBody(BaseModel):
    """Optional timeout for device-flow poll."""

    timeout: float = 300.0


@router.put("/config")
async def configure_sync(
    body: SyncConfigureBody,
    service: Annotated[SyncService, Depends(get_sync_service)],
) -> dict[str, Any]:
    """Update sync settings (no tokens)."""
    try:
        config = await service.configure(**body.model_dump())
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return config.model_dump()


@router.post("/connect")
async def connect_sync(
    body: SyncConnectBody,
    service: Annotated[SyncService, Depends(get_sync_service)],
) -> dict[str, Any]:
    """Create-or-bind repo, configure, and init clone."""
    try:
        status = await service.connect(**body.model_dump())
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return status.model_dump()


@router.post("/init")
async def init_sync(
    service: Annotated[SyncService, Depends(get_sync_service)],
) -> dict[str, Any]:
    """Clone or bind the remote workspace repo."""
    try:
        status = await service.init()
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return status.model_dump()


@router.get("/status")
async def sync_status(
    service: Annotated[SyncService, Depends(get_sync_service)],
) -> dict[str, Any]:
    """Return branch and asset-count status."""
    try:
        status = await service.status()
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return status.model_dump()


@router.post("/branches")
async def create_branch(
    body: SyncBranchBody,
    service: Annotated[SyncService, Depends(get_sync_service)],
) -> dict[str, Any]:
    """Create and checkout a branch."""
    try:
        status = await service.branch_create(body.name)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return status.model_dump()


@router.post("/checkout")
async def checkout_branch(
    body: SyncCheckoutBody,
    service: Annotated[SyncService, Depends(get_sync_service)],
) -> dict[str, Any]:
    """Checkout an existing branch."""
    try:
        status = await service.checkout(body.branch)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return status.model_dump()


@router.post("/push")
async def push_workspace(
    body: SyncPushBody,
    service: Annotated[SyncService, Depends(get_sync_service)],
) -> dict[str, Any]:
    """Push local workspace assets."""
    try:
        result = await service.push(body.message)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return result.model_dump()


@router.post("/pull")
async def pull_workspace(
    service: Annotated[SyncService, Depends(get_sync_service)],
) -> dict[str, Any]:
    """Pull workspace assets from GitHub into Navbe."""
    try:
        result = await service.pull()
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return result.model_dump()


@router.post("/auth/github/begin")
async def auth_github_begin(
    auth: Annotated[GitHubAuthService, Depends(get_github_auth_service)],
) -> dict[str, Any]:
    """Start GitHub Device Flow (user_code + verification_uri only)."""
    try:
        result = await auth.begin()
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return result.model_dump()


@router.post("/auth/github/complete")
async def auth_github_complete(
    body: AuthCompleteBody,
    auth: Annotated[GitHubAuthService, Depends(get_github_auth_service)],
) -> dict[str, Any]:
    """Finish device flow poll; never returns the token."""
    try:
        status = await auth.complete(timeout=body.timeout)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return status.model_dump()


@router.get("/auth/github")
async def auth_github_status(
    auth: Annotated[GitHubAuthService, Depends(get_github_auth_service)],
) -> dict[str, Any]:
    """OAuth presence only."""
    try:
        status = await auth.status()
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return status.model_dump()


@router.get("/auth/github/repos")
async def auth_github_repos(
    auth: Annotated[GitHubAuthService, Depends(get_github_auth_service)],
) -> dict[str, Any]:
    """List repos the installed GitHub App can access (for sync_connect picker)."""
    try:
        repos = await auth.list_accessible_repos()
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return {"repos": [repo.model_dump() for repo in repos]}


@router.delete("/auth/github")
async def auth_github_logout(
    auth: Annotated[GitHubAuthService, Depends(get_github_auth_service)],
) -> dict[str, Any]:
    """Clear managed GitHub OAuth token."""
    try:
        status = await auth.logout()
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return status.model_dump()
