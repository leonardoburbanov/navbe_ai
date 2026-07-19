"""Secrets resolution use-cases."""

import os
from typing import Any

from navbe.core.exceptions import NotFoundError
from navbe.domains.secrets.interfaces import SecretsProvider
from navbe.domains.secrets.models import is_secret_ref, parse_secret_ref


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


class SecretsService:
    """Resolve secret refs for connectors and other consumers."""

    def __init__(self, provider: SecretsProvider) -> None:
        """Create a service with an injectable provider."""
        self._provider = provider

    async def resolve_ref(self, key: str) -> str:
        """Resolve a single secret key via the provider."""
        return await self._provider.resolve(key)

    async def resolve_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Recursively replace every ``{"$secret": "X"}`` leaf with its value."""
        return await self._walk(config)

    async def _walk(self, node: Any) -> Any:
        """Walk dict/list trees replacing secret refs."""
        if is_secret_ref(node):
            return await self.resolve_ref(parse_secret_ref(node).key)
        if isinstance(node, dict):
            return {key: await self._walk(value) for key, value in node.items()}
        if isinstance(node, list):
            return [await self._walk(value) for value in node]
        return node
