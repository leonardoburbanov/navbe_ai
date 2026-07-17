"""Tests for connector registry."""

from collections.abc import Iterator

import pytest

from navbe.core.exceptions import NotFoundError
from navbe.domains.connectors.registry import ConnectorRegistry


@pytest.fixture(autouse=True)
def reset_registry() -> Iterator[None]:
    """Avoid cross-test registry pollution."""
    original = ConnectorRegistry._connectors
    ConnectorRegistry._connectors = {}
    yield
    ConnectorRegistry._connectors = original


class FakeConnector:
    """Fake registry target."""


def test_register_and_get() -> None:
    """Registered connectors can be retrieved by key."""
    ConnectorRegistry.register("fake")(FakeConnector)
    assert ConnectorRegistry.get("fake") is FakeConnector


def test_get_unknown_raises_not_found() -> None:
    """Unknown keys raise NotFoundError with available details."""
    with pytest.raises(NotFoundError) as exc_info:
        ConnectorRegistry.get("nonexistent")

    assert exc_info.value.details["connector_type"] == "nonexistent"
    assert "available" in exc_info.value.details


def test_list_all_returns_copy() -> None:
    """Mutating list_all output does not mutate registry state."""
    ConnectorRegistry.register("fake")(FakeConnector)
    listed = ConnectorRegistry.list_all()
    listed.clear()
    assert ConnectorRegistry.get("fake") is FakeConnector
