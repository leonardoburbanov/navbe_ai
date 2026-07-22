"""Tests for ``navbe.core.config``."""

from pathlib import Path

import pytest

from navbe.core.config import Settings, get_settings


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Defaults land under the active data home when env/.env are unset."""
    for key in (
        "NAVBE_DB_PATH",
        "NAVBE_FLOWS_DIR",
        "NAVBE_CREDENTIALS_PATH",
        "NAVBE_SYNC_CONFIG_PATH",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    # Outside a checkout, data home is ~/.navbe (not tmp_path).
    monkeypatch.setattr(
        "navbe.core.config.default_data_home",
        lambda: tmp_path / ".navbe",
    )
    settings = Settings(_env_file=None)
    home = tmp_path / ".navbe"
    assert settings.db_path == home / "navbe.db"
    assert settings.credentials_path == home / "navbe_credentials.json"


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
