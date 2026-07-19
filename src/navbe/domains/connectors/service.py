"""Use-cases for resolving connector instances."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from navbe.domains.connectors.registry import ConnectorRegistry

if TYPE_CHECKING:
    from navbe.domains.secrets.service import SecretsService


class ConnectorService:
    """Facade over the connector registry with optional secret resolution."""

    def __init__(
        self,
        registry: type[ConnectorRegistry] = ConnectorRegistry,
        secrets_service: SecretsService | None = None,
    ) -> None:
        """Create a service with injectable registry and secrets resolver."""
        self._registry = registry
        self._secrets = secrets_service

    def get_config_schema(self, connector_type: str) -> dict[str, Any]:
        """Return a connector config JSON schema."""
        connector_cls = cast(Any, self._registry.get(connector_type))
        return connector_cls.config_schema.model_json_schema()

    async def resolve(self, name: str, instance_config: dict[str, Any]) -> Any:
        """Resolve secret refs and instantiate a connector."""
        _ = name
        connector_cls = self._registry.get(instance_config["type"])
        resolved_config = await self._resolve_secrets(instance_config["config"])
        return connector_cls(resolved_config)

    async def _resolve_secrets(self, config: dict[str, Any]) -> dict[str, Any]:
        """Delegate secret-ref walking to ``SecretsService`` when injected."""
        if self._secrets is None:
            return config
        return await self._secrets.resolve_config(config)
