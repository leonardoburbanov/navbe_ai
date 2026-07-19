"""Tests for secrets service."""

import pytest

from navbe.core.exceptions import NotFoundError
from navbe.domains.secrets.service import EnvSecretsProvider, SecretsService


async def test_env_provider_resolves_existing_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing env vars resolve to their values."""
    monkeypatch.setenv("API_KEY", "sk-123")
    assert await EnvSecretsProvider().resolve("API_KEY") == "sk-123"


async def test_env_provider_missing_var_raises_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing env vars raise NotFoundError with key + hint only."""
    monkeypatch.delenv("MISSING_SECRET", raising=False)
    with pytest.raises(NotFoundError) as exc_info:
        await EnvSecretsProvider().resolve("MISSING_SECRET")

    assert exc_info.value.details["key"] == "MISSING_SECRET"
    assert "hint" in exc_info.value.details
    assert "sk-" not in str(exc_info.value.details)
    assert "sk-" not in exc_info.value.message


async def test_resolve_config_replaces_nested_secret_ref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nested secret refs resolve; sibling fields stay untouched."""
    monkeypatch.setenv("API_KEY", "sk-123")
    service = SecretsService(EnvSecretsProvider())
    resolved = await service.resolve_config(
        {
            "base_url": "https://example.com",
            "headers": {"Authorization": {"$secret": "API_KEY"}, "Accept": "application/json"},
        }
    )
    assert resolved == {
        "base_url": "https://example.com",
        "headers": {"Authorization": "sk-123", "Accept": "application/json"},
    }


async def test_resolve_config_replaces_secret_ref_inside_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Secret refs inside lists resolve; plain values stay as-is."""
    monkeypatch.setenv("A", "token-a")
    service = SecretsService(EnvSecretsProvider())
    resolved = await service.resolve_config({"tokens": [{"$secret": "A"}, "plain"]})
    assert resolved == {"tokens": ["token-a", "plain"]}


async def test_resolve_config_no_refs_returns_equivalent_dict() -> None:
    """Configs without secret refs return an equivalent dict."""
    service = SecretsService(EnvSecretsProvider())
    config = {"base_url": "https://example.com", "timeout": 5}
    resolved = await service.resolve_config(config)
    assert resolved == config
    assert resolved is not config


async def test_resolve_config_missing_secret_raises_and_identifies_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing nested secret identifies the failing key name only."""
    monkeypatch.setenv("PRESENT", "ok")
    monkeypatch.delenv("MISSING_NESTED", raising=False)
    service = SecretsService(EnvSecretsProvider())

    with pytest.raises(NotFoundError) as exc_info:
        await service.resolve_config(
            {
                "headers": {
                    "Authorization": {"$secret": "PRESENT"},
                    "X-Extra": {"$secret": "MISSING_NESTED"},
                }
            }
        )

    assert exc_info.value.details["key"] == "MISSING_NESTED"
    assert "ok" not in str(exc_info.value.details)
    assert "ok" not in exc_info.value.message
