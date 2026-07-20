"""Tests for ``navbe.core.config``."""

from pathlib import Path

import pytest

from navbe.core.config import Settings, get_settings


def test_settings_defaults() -> None:
    """Defaults match the documented Settings fields when env is unset."""
    settings = Settings(_env_file=None)
    assert settings.db_path == Path("./navbe.db")
    assert settings.credentials_path == Path("./navbe_credentials.json")


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """``NAVBE_`` env vars override Settings fields."""
    monkeypatch.setenv("NAVBE_LOG_LEVEL", "DEBUG")
    settings = Settings(_env_file=None)
    assert settings.log_level == "DEBUG"


def test_get_settings_is_cached() -> None:
    """``get_settings`` returns the same cached instance."""
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert id(first) == id(second)
