"""REST mirror of secret MCP tools (never returns secret values)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from navbe.api.errors import to_http_exception
from navbe.core.exceptions import NavbeError
from navbe.dependencies import get_secrets_service
from navbe.domains.secrets.service import SecretsService

router = APIRouter()


class SecretValueBody(BaseModel):
    """Body for storing a credential value."""

    value: str = Field(min_length=1)


@router.get("")
async def list_secrets(
    service: Annotated[SecretsService, Depends(get_secrets_service)],
) -> dict[str, Any]:
    """List credential keys only (never values)."""
    keys = await service.list_keys()
    return {"keys": keys}


@router.put("/{key}")
async def put_secret(
    key: str,
    body: SecretValueBody,
    service: Annotated[SecretsService, Depends(get_secrets_service)],
) -> dict[str, Any]:
    """Store a secret by key. Never returns the value."""
    try:
        await service.set(key, body.value)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return {"key": key, "stored": True}


@router.get("/{key}/has")
async def has_secret(
    key: str,
    service: Annotated[SecretsService, Depends(get_secrets_service)],
) -> dict[str, Any]:
    """Check whether a key exists in credentials file or environment."""
    try:
        present = await service.has(key)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return {"key": key, "present": present}


@router.delete("/{key}")
async def delete_secret(
    key: str,
    service: Annotated[SecretsService, Depends(get_secrets_service)],
) -> dict[str, Any]:
    """Delete a key from the local credentials file."""
    try:
        deleted = await service.delete(key)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return {"key": key, "deleted": deleted}
