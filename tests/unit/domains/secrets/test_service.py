"""Tests for secrets service."""

from pathlib import Path

import pytest

from navbe.core.exceptions import NotFoundError
from navbe.domains.secrets.json_file import JsonFileSecretsProvider
from navbe.domains.secrets.service import SecretsService


async def _service(tmp_path: Path) -> SecretsService:
    """Build a JSON-backed secrets service under ``tmp_path``."""
    store = JsonFileSecretsProvider(tmp_path / "creds.json")
    return SecretsService(store, store=store)


async def test_resolve_config_replaces_nested_secret_ref(tmp_path: Path) -> None:
    """Nested secret refs resolve; sibling fields stay untouched."""
    service = await _service(tmp_path)
    await service.set("API_KEY", "sk-123")
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


async def test_resolve_config_replaces_secret_ref_inside_list(tmp_path: Path) -> None:
    """Secret refs inside lists resolve; plain values stay as-is."""
    service = await _service(tmp_path)
    await service.set("A", "token-a")
    resolved = await service.resolve_config({"tokens": [{"$secret": "A"}, "plain"]})
    assert resolved == {"tokens": ["token-a", "plain"]}


async def test_resolve_config_no_refs_returns_equivalent_dict(tmp_path: Path) -> None:
    """Configs without secret refs return an equivalent dict."""
    service = await _service(tmp_path)
    config = {"base_url": "https://example.com", "timeout": 5}
    resolved = await service.resolve_config(config)
    assert resolved == config
    assert resolved is not config


async def test_resolve_config_missing_secret_raises_and_identifies_key(
    tmp_path: Path,
) -> None:
    """Missing nested secret identifies the failing key name only."""
    service = await _service(tmp_path)
    await service.set("PRESENT", "ok")

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
