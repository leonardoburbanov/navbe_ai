"""REST mirror of run MCP tools (thin service adapters)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from navbe.api.errors import to_http_exception
from navbe.core.exceptions import NavbeError
from navbe.dependencies import get_run_service
from navbe.domains.execution.payloads import run_detail_payload
from navbe.domains.execution.service import RunService

router = APIRouter()


class StartRunRequest(BaseModel):
    """Body for starting a flow run."""

    flow_id: str
    initial_input: dict[str, Any] | None = None


@router.post("")
async def start_run(
    body: StartRunRequest,
    service: Annotated[RunService, Depends(get_run_service)],
) -> dict[str, str]:
    """Start a flow run; returns immediately with run_id."""
    try:
        run_id = await service.start(body.flow_id, body.initial_input)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    assert run_id is not None
    return {"run_id": run_id}


@router.get("")
async def list_runs(
    service: Annotated[RunService, Depends(get_run_service)],
    flow_id: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """List runs, optionally filtered by flow_id (most recent first)."""
    runs = await service.list_runs(flow_id)
    return {"runs": [run.model_dump(mode="json") for run in runs]}


@router.get("/{run_id}")
async def get_run_status(
    run_id: str,
    service: Annotated[RunService, Depends(get_run_service)],
) -> dict[str, Any]:
    """Return run state plus steps timeline and Mermaid diagram."""
    try:
        detail = await service.detail(run_id)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return run_detail_payload(detail)


@router.post("/{run_id}/resume")
async def resume_run(
    run_id: str,
    decision: dict[str, Any],
    service: Annotated[RunService, Depends(get_run_service)],
) -> dict[str, Any]:
    """Resume a paused run with a decision payload; returns enriched detail."""
    try:
        await service.resume(run_id, decision)
        detail = await service.detail(run_id)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return run_detail_payload(detail)


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    service: Annotated[RunService, Depends(get_run_service)],
) -> dict[str, Any]:
    """Cancel an active run."""
    try:
        state = await service.cancel(run_id)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return state.model_dump(mode="json")
