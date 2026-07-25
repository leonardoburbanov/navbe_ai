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
    app: str | None = None


@router.get("")
async def list_secrets(
    service: Annotated[SecretsService, Depends(get_secrets_service)],
) -> dict[str, Any]:
    """List credential keys and masked items (never values)."""
    keys = await service.list_keys()
    items = await service.list_credentials()
    return {
        "keys": keys,
        "items": [item.model_dump(mode="json") for item in items],
    }


@router.put("/{key}")
async def put_secret(
    key: str,
    body: SecretValueBody,
    service: Annotated[SecretsService, Depends(get_secrets_service)],
) -> dict[str, Any]:
    """Store a secret by key. Returns masked hint; never the value."""
    try:
        hint = await service.set(key, body.value, app=body.app)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return {
        "key": hint.key,
        "stored": True,
        "hint": hint.hint,
        "app": hint.app,
    }


@router.get("/{key}/hint")
async def hint_secret(
    key: str,
    service: Annotated[SecretsService, Depends(get_secrets_service)],
) -> dict[str, Any]:
    """Return masked metadata for a key (never the value)."""
    try:
        hint = await service.get_hint(key)
    except NavbeError as exc:
        raise to_http_exception(exc) from exc
    return hint.model_dump(mode="json")


@router.get("/{key}/has")
async def has_secret(
    key: str,
    service: Annotated[SecretsService, Depends(get_secrets_service)],
) -> dict[str, Any]:
    """Check whether a key exists in the credentials file."""
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
