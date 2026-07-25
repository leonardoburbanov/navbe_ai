"""Secrets provider / store contracts."""

from typing import Protocol, runtime_checkable

from navbe.domains.secrets.models import CredentialRecord


@runtime_checkable
class SecretsProvider(Protocol):
    """Minimal seam for resolving named secrets."""

    async def resolve(self, key: str) -> str:
        """Return the plaintext value for ``key``."""
        ...


@runtime_checkable
class SecretsStore(Protocol):
    """Mutable store for named secrets (values never exposed via MCP)."""

    async def set(self, key: str, value: str, *, app: str | None = None) -> None:
        """Create or overwrite ``key`` (optional ``app`` label)."""
        ...

    async def delete(self, key: str) -> bool:
        """Remove ``key``. Return True if it existed."""
        ...

    async def list_keys(self) -> list[str]:
        """Return stored key names only (never values)."""
        ...

    async def has(self, key: str) -> bool:
        """True if ``key`` is present in this store."""
        ...

    async def get_record(self, key: str) -> CredentialRecord | None:
        """Return the stored record for ``key``, or None if missing."""
        ...

    async def list_records(self) -> dict[str, CredentialRecord]:
        """Return all stored records keyed by secret name."""
        ...
