"""REST mirror of flow MCP tools (thin service adapters)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from navbe.api.errors import to_http_exception
from navbe.core.exceptions import NavbeError
from navbe.dependencies import get_flow_service
from navbe.domains.flows.service import FlowService

router = APIRouter()


@router.post("", status_code=201)
async def create_flow(
    spec: dict[str, Any],
    service: Annotated[FlowService, Depends(get_flow_service)],
) -> dict[str, Any]:
    """Create and persist a flow from a FlowSpec dict."""
    try:
        metadata = await service.create(spec)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return metadata.model_dump(mode="json")


@router.get("/{flow_id}")
async def get_flow(
    flow_id: str,
    service: Annotated[FlowService, Depends(get_flow_service)],
) -> dict[str, Any]:
    """Return a persisted FlowSpec by id."""
    try:
        flow_spec = await service.get(flow_id)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return flow_spec.model_dump(by_alias=True)


@router.get("")
async def list_flows(
    service: Annotated[FlowService, Depends(get_flow_service)],
) -> list[dict[str, Any]]:
    """List saved flow metadata."""
    flows = await service.list()
    return [flow.model_dump(mode="json") for flow in flows]
