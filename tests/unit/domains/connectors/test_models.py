"""Tests for connector models."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from navbe.domains.connectors.models import ConnectorInstanceConfig


def test_connector_instance_config_parses_minimal() -> None:
    """Minimal connector instance config parses."""
    config = ConnectorInstanceConfig(type="http", config={"base_url": "https://x.com"})
    assert config.type == "http"
    assert config.config == {"base_url": "https://x.com"}


def test_connector_instance_config_requires_type() -> None:
    """Missing type field raises Pydantic ValidationError."""
    with pytest.raises(PydanticValidationError):
        ConnectorInstanceConfig(config={"base_url": "https://x.com"})
