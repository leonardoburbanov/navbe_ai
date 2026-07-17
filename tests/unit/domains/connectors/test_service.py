"""Tests for connector service."""

import pytest

import navbe.domains.connectors.implementations  # noqa: F401
from navbe.core.exceptions import NotFoundError
from navbe.domains.connectors.implementations.http import HTTPConnector
from navbe.domains.connectors.service import ConnectorService


class FakeSecretsService:
    """Fake secret resolver for connector service tests."""

    async def resolve(self, name: str) -> str:
        """Return a deterministic fake secret value."""
        return {"API_KEY": "sk-123"}[name]


def test_get_config_schema_returns_valid_json_schema() -> None:
    """HTTP connector schema exposes base_url."""
    schema = ConnectorService().get_config_schema("http")
    assert "properties" in schema
    assert "base_url" in schema["properties"]
    assert "base_url" in schema.get("required", [])


async def test_resolve_without_secrets_service_passes_config_through() -> None:
    """Without a secrets service, config is passed through unchanged."""
    config = {"type": "http", "config": {"base_url": "https://x.com", "timeout": 5}}
    connector = await ConnectorService().resolve("bot", config)

    assert isinstance(connector, HTTPConnector)
    assert connector.config.base_url == "https://x.com"
    assert connector.config.timeout == 5


async def test_resolve_replaces_secret_ref() -> None:
    """Secret refs are resolved recursively before instantiation."""
    instance_config = {
        "type": "http",
        "config": {
            "base_url": "https://x.com",
            "headers": {"Authorization": {"$secret": "API_KEY"}},
        },
    }
    connector = await ConnectorService(secrets_service=FakeSecretsService()).resolve(
        "bot",
        instance_config,
    )

    assert connector.config.headers == {"Authorization": "sk-123"}


async def test_resolve_returns_connector_instance() -> None:
    """Resolve returns a concrete connector instance."""
    connector = await ConnectorService().resolve(
        "bot",
        {"type": "http", "config": {"base_url": "https://x.com"}},
    )

    assert isinstance(connector, HTTPConnector)


async def test_resolve_unknown_connector_type_propagates_not_found() -> None:
    """Unknown connector types bubble up NotFoundError unchanged."""
    with pytest.raises(NotFoundError):
        await ConnectorService().resolve("bot", {"type": "missing", "config": {}})
