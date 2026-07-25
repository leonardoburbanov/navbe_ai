"""REST mirror of schedule MCP tools (thin service adapters)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from navbe.api.errors import to_http_exception
from navbe.core.exceptions import NavbeError
from navbe.dependencies import get_run_service, get_schedule_service
from navbe.domains.execution.service import RunService
from navbe.domains.schedules.service import ScheduleService

router = APIRouter()


@router.post("")
async def create_schedule(
    spec: dict[str, Any],
    service: Annotated[ScheduleService, Depends(get_schedule_service)],
) -> dict[str, Any]:
    """Create a new schedule."""
    try:
        metadata = await service.create(spec)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return metadata.model_dump(mode="json")


@router.get("")
async def list_schedules(
    service: Annotated[ScheduleService, Depends(get_schedule_service)],
) -> dict[str, Any]:
    """List schedule metadata."""
    items = await service.list()
    return {"schedules": [item.model_dump(mode="json") for item in items]}


@router.get("/{schedule_id}")
async def get_schedule(
    schedule_id: str,
    service: Annotated[ScheduleService, Depends(get_schedule_service)],
) -> dict[str, Any]:
    """Return one schedule document."""
    try:
        schedule = await service.get(schedule_id)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return schedule.model_dump(mode="json", by_alias=True)


@router.put("/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    spec: dict[str, Any],
    service: Annotated[ScheduleService, Depends(get_schedule_service)],
) -> dict[str, Any]:
    """Overwrite an existing schedule."""
    payload = {**spec, "schedule_id": schedule_id}
    try:
        metadata = await service.update(payload)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return metadata.model_dump(mode="json")


@router.post("/{schedule_id}/enable")
async def enable_schedule(
    schedule_id: str,
    service: Annotated[ScheduleService, Depends(get_schedule_service)],
) -> dict[str, Any]:
    """Enable a schedule and refresh next_run_at."""
    try:
        schedule = await service.enable(schedule_id)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return schedule.model_dump(mode="json", by_alias=True)


@router.post("/{schedule_id}/disable")
async def disable_schedule(
    schedule_id: str,
    service: Annotated[ScheduleService, Depends(get_schedule_service)],
) -> dict[str, Any]:
    """Disable a schedule."""
    try:
        schedule = await service.disable(schedule_id)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return schedule.model_dump(mode="json", by_alias=True)


@router.get("/{schedule_id}/runs")
async def list_schedule_runs(
    schedule_id: str,
    runs: Annotated[RunService, Depends(get_run_service)],
) -> dict[str, Any]:
    """List runs triggered by one schedule."""
    items = await runs.list_schedule_runs(schedule_id)
    return {"runs": [item.model_dump(mode="json") for item in items]}
