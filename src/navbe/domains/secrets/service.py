"""Secrets resolution and local credentials store use-cases."""

import os
from typing import Any

from dotenv import load_dotenv

from navbe.core.exceptions import NotFoundError, ValidationError
from navbe.domains.secrets.interfaces import SecretsProvider, SecretsStore
from navbe.domains.secrets.models import (
    CredentialHint,
    is_secret_ref,
    mask_secret,
    parse_secret_ref,
    validate_secret_key,
)

# ponytail: load once at import — upgrade: injectable env source
load_dotenv()


class EnvSecretsProvider:
    """v0.1 provider: reads from process env / loaded .env file."""

    async def resolve(self, key: str) -> str:
        """Resolve ``key`` from the process environment."""
        value = os.environ.get(key)
        if value is None:
            raise NotFoundError(
                f"Secret '{key}' not found in environment",
                details={
                    "key": key,
                    "hint": "define it in .env or export it before running navbe",
                },
            )
        return value

    async def has(self, key: str) -> bool:
        """True if ``key`` is set in the process environment."""
        return key in os.environ


class SecretsService:
    """Resolve secret refs and manage the local credentials store."""

    def __init__(
        self,
        provider: SecretsProvider,
        store: SecretsStore | None = None,
        *,
        presence_checks: list[Any] | None = None,
    ) -> None:
        """Create a service with resolve provider and optional mutable store.

        ``presence_checks`` are objects with ``async has(key) -> bool`` used by
        ``has()`` (JSON store then env). Defaults to ``[store]`` when store set.
        """
        self._provider = provider
        self._store = store
        if presence_checks is not None:
            self._presence = list(presence_checks)
        elif store is not None:
            self._presence = [store]
        else:
            self._presence = []

    def _require_store(self) -> SecretsStore:
        """Return the store or raise if credentials file management is disabled."""
        if self._store is None:
            raise ValidationError(
                "Credentials store is not configured",
                details={"hint": "set NAVBE_CREDENTIALS_PATH and restart navbe"},
            )
        return self._store

    async def resolve_ref(self, key: str) -> str:
        """Resolve a single secret key via the provider."""
        return await self._provider.resolve(key)

    async def resolve_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Recursively replace every ``{"$secret": "X"}`` leaf with its value."""
        return await self._walk(config)

    async def set(self, key: str, value: str, *, app: str | None = None) -> CredentialHint:
        """Store ``key`` in the local credentials file; return masked metadata."""
        validate_secret_key(key)
        await self._require_store().set(key, value, app=app)
        return await self.get_hint(key)

    async def delete(self, key: str) -> bool:
        """Delete ``key`` from the local credentials file."""
        validate_secret_key(key)
        return await self._require_store().delete(key)

    async def list_keys(self) -> list[str]:
        """List keys in the local credentials file (never values)."""
        if self._store is None:
            return []
        return await self._store.list_keys()

    async def list_credentials(self) -> list[CredentialHint]:
        """List stored credentials with masked hints (never values)."""
        if self._store is None:
            return []
        records = await self._store.list_records()
        items: list[CredentialHint] = []
        for key in sorted(records.keys()):
            record = records[key]
            items.append(
                CredentialHint(
                    key=key,
                    hint=mask_secret(record.value),
                    app=record.app,
                    source="store",
                    updated_at=record.updated_at,
                )
            )
        return items

    async def get_hint(self, key: str) -> CredentialHint:
        """Return masked metadata for ``key`` from store or env (never the value)."""
        validate_secret_key(key)
        store = self._store
        if store is not None:
            record = await store.get_record(key)
            if record is not None:
                return CredentialHint(
                    key=key,
                    hint=mask_secret(record.value),
                    app=record.app,
                    source="store",
                    updated_at=record.updated_at,
                )
        for checker in self._presence:
            if store is not None and checker is store:
                continue
            if await checker.has(key):
                return CredentialHint(
                    key=key,
                    hint=None,
                    app=None,
                    source="env",
                    updated_at=None,
                )
        raise NotFoundError(
            f"Secret '{key}' not found in credentials file or environment",
            details={
                "key": key,
                "hint": "use secret_set or define it in .env / export it",
            },
        )

    async def has(self, key: str) -> bool:
        """True if ``key`` is present in the credentials file or environment."""
        validate_secret_key(key)
        for checker in self._presence:
            if await checker.has(key):
                return True
        return False

    async def _walk(self, node: Any) -> Any:
        """Walk dict/list trees replacing secret refs."""
        if is_secret_ref(node):
            return await self.resolve_ref(parse_secret_ref(node).key)
        if isinstance(node, dict):
            return {key: await self._walk(value) for key, value in node.items()}
        if isinstance(node, list):
            return [await self._walk(value) for value in node]
        return node
