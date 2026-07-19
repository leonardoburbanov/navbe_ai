"""Secrets provider contracts."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretsProvider(Protocol):
    """Minimal seam for resolving named secrets."""

    async def resolve(self, key: str) -> str:
        """Return the plaintext value for ``key``."""
        ...
