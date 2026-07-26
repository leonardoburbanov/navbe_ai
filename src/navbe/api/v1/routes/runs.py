"""REST mirror of run MCP tools (thin service adapters)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from navbe.api.errors import to_http_exception
from navbe.core.exceptions import NavbeError
from navbe.dependencies import get_run_service
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


@router.get("/{run_id}")
async def get_run_status(
    run_id: str,
    service: Annotated[RunService, Depends(get_run_service)],
) -> dict[str, Any]:
    """Return the latest RunState for a run."""
    try:
        state = await service.status(run_id)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return state.model_dump(mode="json")


@router.post("/{run_id}/resume")
async def resume_run(
    run_id: str,
    decision: dict[str, Any],
    service: Annotated[RunService, Depends(get_run_service)],
) -> dict[str, Any]:
    """Resume a paused run with a decision payload."""
    try:
        state = await service.resume(run_id, decision)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return state.model_dump(mode="json")


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
