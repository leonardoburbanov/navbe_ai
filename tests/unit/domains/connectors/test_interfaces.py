"""Tests for connector interfaces."""

from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from navbe.domains.connectors.interfaces import Connector, ConnectorConfig


class FakeConfig(ConnectorConfig):
    """Fake connector config schema."""

    host: str


class FakeConnector:
    """Fake connector satisfying the Connector protocol."""

    config_schema = FakeConfig
    actions = {"ping": "Ping the host"}

    async def test_connection(self) -> bool:
        """Always report connected."""
        return True

    async def execute(self, action: str, payload: dict) -> Any:
        """Echo action and payload."""
        return {"action": action, "payload": payload}


class BadConfig(ConnectorConfig):
    """Config with one required field."""

    host: str


def test_fake_connector_satisfies_protocol() -> None:
    """Runtime-checkable Protocol accepts structural implementation."""
    assert isinstance(FakeConnector(), Connector)


def test_connector_config_rejects_extra_fields() -> None:
    """Unknown config fields fail validation loudly."""
    with pytest.raises(PydanticValidationError):
        BadConfig(host="x", typo=True)
