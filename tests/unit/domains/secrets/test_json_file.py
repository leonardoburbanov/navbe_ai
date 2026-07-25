"""Tests for JSON credentials file secrets resolution."""

from pathlib import Path

import pytest

from navbe.core.exceptions import NotFoundError, ValidationError
from navbe.domains.secrets.json_file import JsonFileSecretsProvider
from navbe.domains.secrets.service import SecretsService


async def test_json_set_resolve_list_delete(tmp_path: Path) -> None:
    """Round-trip store without leaking values through list_keys."""
    path = tmp_path / "creds.json"
    store = JsonFileSecretsProvider(path)
    await store.set("API_KEY", "sk-secret-value")
    assert await store.resolve("API_KEY") == "sk-secret-value"
    assert await store.list_keys() == ["API_KEY"]
    assert "sk-secret-value" not in str(await store.list_keys())
    assert await store.has("API_KEY") is True
    assert await store.delete("API_KEY") is True
    assert await store.list_keys() == []
    assert await store.delete("API_KEY") is False


async def test_json_invalid_key_rejected(tmp_path: Path) -> None:
    """Lowercase / empty keys are rejected."""
    store = JsonFileSecretsProvider(tmp_path / "creds.json")
    with pytest.raises(ValidationError):
        await store.set("bad-key", "x")
    with pytest.raises(ValidationError):
        await store.set("API_KEY", "")


async def test_service_ignores_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SecretsService never resolves from environment variables."""
    monkeypatch.setenv("API_KEY", "from-env")
    store = JsonFileSecretsProvider(tmp_path / "creds.json")
    service = SecretsService(store, store=store)
    with pytest.raises(NotFoundError):
        await service.resolve_ref("API_KEY")
    assert await service.has("API_KEY") is False


async def test_missing_raises_without_value(tmp_path: Path) -> None:
    """Missing key raises NotFoundError with key name only."""
    store = JsonFileSecretsProvider(tmp_path / "creds.json")
    service = SecretsService(store, store=store)
    with pytest.raises(NotFoundError) as exc_info:
        await service.resolve_ref("NOPE")
    assert exc_info.value.details["key"] == "NOPE"


async def test_service_set_list_has(tmp_path: Path) -> None:
    """SecretsService mutators write through the JSON store."""
    store = JsonFileSecretsProvider(tmp_path / "creds.json")
    service = SecretsService(store, store=store)
    hint = await service.set("RESEND_API_KEY", "re-test-key", app="resend")
    assert hint.hint == "****-key"
    assert hint.app == "resend"
    assert await service.list_keys() == ["RESEND_API_KEY"]
    items = await service.list_credentials()
    assert items[0].hint == "****-key"
    assert items[0].app == "resend"
    assert await service.has("RESEND_API_KEY") is True
    assert await service.delete("RESEND_API_KEY") is True


async def test_legacy_string_entry_still_resolves(tmp_path: Path) -> None:
    """Flat string credentials files remain readable."""
    path = tmp_path / "creds.json"
    path.write_text('{"LEGACY_KEY": "legacy-secret-value"}\n', encoding="utf-8")
    store = JsonFileSecretsProvider(path)
    assert await store.resolve("LEGACY_KEY") == "legacy-secret-value"
    record = await store.get_record("LEGACY_KEY")
    assert record is not None
    assert record.value == "legacy-secret-value"
    assert record.app is None


async def test_set_preserves_app_on_rotate(tmp_path: Path) -> None:
    """Rotating without app keeps the existing app label."""
    store = JsonFileSecretsProvider(tmp_path / "creds.json")
    await store.set("RESEND_API_KEY", "old-value-aaaa", app="resend")
    await store.set("RESEND_API_KEY", "new-value-bbbb")
    record = await store.get_record("RESEND_API_KEY")
    assert record is not None
    assert record.value == "new-value-bbbb"
    assert record.app == "resend"


async def test_get_hint_missing_key(tmp_path: Path) -> None:
    """get_hint raises when the key is not in the credentials file."""
    store = JsonFileSecretsProvider(tmp_path / "creds.json")
    service = SecretsService(store, store=store)
    with pytest.raises(NotFoundError) as exc_info:
        await service.get_hint("MISSING_KEY")
    assert exc_info.value.details["key"] == "MISSING_KEY"
