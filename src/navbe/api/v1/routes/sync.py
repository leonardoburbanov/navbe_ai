"""REST mirror of sync MCP tools (flows organization only)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from navbe.api.errors import to_http_exception
from navbe.core.exceptions import NavbeError
from navbe.dependencies import get_sync_service
from navbe.domains.sync.service import SyncService

router = APIRouter()


class SyncConfigureBody(BaseModel):
    """Optional fields for sync_configure."""

    remote_url: str | None = None
    local_repo_dir: str | None = None
    flows_subdir: str | None = None
    default_branch: str | None = None
    token_secret_key: str | None = None


class SyncPushBody(BaseModel):
    """Optional commit message for sync_push."""

    message: str | None = None


class SyncBranchBody(BaseModel):
    """Branch name payload."""

    name: str


class SyncCheckoutBody(BaseModel):
    """Checkout branch payload."""

    branch: str


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


@router.post("/init")
async def init_sync(
    service: Annotated[SyncService, Depends(get_sync_service)],
) -> dict[str, Any]:
    """Clone or bind the remote flows repo."""
    try:
        status = await service.init()
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return status.model_dump()


@router.get("/status")
async def sync_status(
    service: Annotated[SyncService, Depends(get_sync_service)],
) -> dict[str, Any]:
    """Return branch and flow-count status."""
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
async def push_flows(
    body: SyncPushBody,
    service: Annotated[SyncService, Depends(get_sync_service)],
) -> dict[str, Any]:
    """Push local flow.json files only."""
    try:
        result = await service.push(body.message)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return result.model_dump()


@router.post("/pull")
async def pull_flows(
    service: Annotated[SyncService, Depends(get_sync_service)],
) -> dict[str, Any]:
    """Pull flows/<id>/flow.json from GitHub into Navbe."""
    try:
        result = await service.pull()
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return result.model_dump()
