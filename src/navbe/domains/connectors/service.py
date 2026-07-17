"""Use-cases for resolving connector instances."""

from typing import Any, Protocol, cast

from navbe.domains.connectors.registry import ConnectorRegistry


class SecretsService(Protocol):
    """Minimal secret resolver injected until the secrets domain exists."""

    async def resolve(self, name: str) -> str:
        """Return the plaintext value for a secret name."""
        ...


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

    async def _resolve_secrets(self, config: Any) -> Any:
        """Recursively replace ``{\"$secret\": \"X\"}`` refs with resolved values."""
        if self._secrets is None:
            return config

        if isinstance(config, dict):
            if set(config) == {"$secret"} and isinstance(config["$secret"], str):
                return await self._secrets.resolve(config["$secret"])
            return {key: await self._resolve_secrets(value) for key, value in config.items()}

        if isinstance(config, list):
            return [await self._resolve_secrets(item) for item in config]

        return config
