"""Shared pytest fixtures for Navbe tests."""

import pytest

from navbe.core.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Return Settings suitable for isolated tests."""
    return Settings(db_path=":memory:", flows_dir="/tmp/navbe_test_flows")
