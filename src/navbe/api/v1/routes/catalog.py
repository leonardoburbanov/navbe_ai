"""REST mirror of catalog MCP tools (thin service adapters)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from navbe.dependencies import get_catalog_service
from navbe.domains.catalog.service import CatalogService

router = APIRouter()


@router.get("/steps")
async def catalog_steps(
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    """Return JSON Schema catalog for all discoverable step types."""
    return await service.get_steps_catalog()


@router.get("/connectors")
async def catalog_connectors(
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    """Return JSON Schema catalog for all registered connector types."""
    return await service.get_connectors_catalog()


@router.get("/full")
async def catalog_full(
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> dict[str, Any]:
    """Return combined steps + connectors catalog."""
    return await service.get_full_catalog()
