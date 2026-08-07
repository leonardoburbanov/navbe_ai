"""REST mirror of flow MCP tools (thin service adapters)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from navbe.api.errors import to_http_exception
from navbe.core.exceptions import NavbeError, ValidationError
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


@router.post("/validate")
async def validate_flow(
    spec: dict[str, Any],
    service: Annotated[FlowService, Depends(get_flow_service)],
) -> dict[str, Any]:
    """Validate a FlowSpec without saving."""
    try:
        result = service.validate(spec)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return result.model_dump()


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


@router.put("/{flow_id}")
async def update_flow(
    flow_id: str,
    spec: dict[str, Any],
    service: Annotated[FlowService, Depends(get_flow_service)],
) -> dict[str, Any]:
    """Validate and overwrite an existing flow.

    Path ``flow_id`` wins. If the body includes a different ``flow_id``, 422.
    """
    if "flow_id" in spec and spec["flow_id"] != flow_id:
        raise to_http_exception(
            ValidationError(
                "Body flow_id does not match path",
                details={"path_flow_id": flow_id, "body_flow_id": spec["flow_id"]},
            )
        )
    payload = {**spec, "flow_id": flow_id}
    try:
        metadata = await service.update(payload)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return metadata.model_dump(mode="json")


@router.get("")
async def list_flows(
    service: Annotated[FlowService, Depends(get_flow_service)],
) -> list[dict[str, Any]]:
    """List saved flow metadata."""
    flows = await service.list()
    return [flow.model_dump(mode="json") for flow in flows]
