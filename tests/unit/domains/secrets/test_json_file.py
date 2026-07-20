"""Tests for JSON credentials file and chained secrets resolution."""

from pathlib import Path

import pytest

from navbe.core.exceptions import NotFoundError, ValidationError
from navbe.domains.secrets.json_file import ChainedSecretsProvider, JsonFileSecretsProvider
from navbe.domains.secrets.service import EnvSecretsProvider, SecretsService


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


async def test_chain_prefers_json_over_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JSON file wins when both define the same key."""
    monkeypatch.setenv("API_KEY", "from-env")
    store = JsonFileSecretsProvider(tmp_path / "creds.json")
    await store.set("API_KEY", "from-file")
    chain = ChainedSecretsProvider([store, EnvSecretsProvider()])
    service = SecretsService(chain, store=store, presence_checks=[store, EnvSecretsProvider()])
    assert await service.resolve_ref("API_KEY") == "from-file"
    resolved = await service.resolve_config({"h": {"$secret": "API_KEY"}})
    assert resolved == {"h": "from-file"}


async def test_chain_falls_back_to_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing JSON key falls back to environment."""
    monkeypatch.setenv("ONLY_ENV", "env-value")
    store = JsonFileSecretsProvider(tmp_path / "creds.json")
    chain = ChainedSecretsProvider([store, EnvSecretsProvider()])
    service = SecretsService(chain, store=store, presence_checks=[store, EnvSecretsProvider()])
    assert await service.resolve_ref("ONLY_ENV") == "env-value"
    assert await service.has("ONLY_ENV") is True


async def test_chain_missing_raises_without_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing everywhere raises NotFoundError with key name only."""
    monkeypatch.delenv("NOPE", raising=False)
    store = JsonFileSecretsProvider(tmp_path / "creds.json")
    chain = ChainedSecretsProvider([store, EnvSecretsProvider()])
    service = SecretsService(chain, store=store)
    with pytest.raises(NotFoundError) as exc_info:
        await service.resolve_ref("NOPE")
    assert exc_info.value.details["key"] == "NOPE"


async def test_service_set_list_has(tmp_path: Path) -> None:
    """SecretsService mutators write through the JSON store."""
    store = JsonFileSecretsProvider(tmp_path / "creds.json")
    env = EnvSecretsProvider()
    service = SecretsService(
        ChainedSecretsProvider([store, env]),
        store=store,
        presence_checks=[store, env],
    )
    await service.set("RESEND_API_KEY", "re-test")
    assert await service.list_keys() == ["RESEND_API_KEY"]
    assert await service.has("RESEND_API_KEY") is True
    assert await service.delete("RESEND_API_KEY") is True
