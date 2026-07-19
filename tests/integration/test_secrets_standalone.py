"""Standalone secrets resolution without Flow or connectors."""

import pytest

from navbe.domains.secrets.service import EnvSecretsProvider, SecretsService


async def test_secret_resolution_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolve nested secret refs end-to-end via EnvSecretsProvider."""
    monkeypatch.setenv("SALES_BOT_KEY", "sk-test-456")
    service = SecretsService(EnvSecretsProvider())

    config = {
        "base_url": "https://example.com",
        "headers": {"Authorization": {"$secret": "SALES_BOT_KEY"}},
    }
    resolved = await service.resolve_config(config)

    assert resolved == {
        "base_url": "https://example.com",
        "headers": {"Authorization": "sk-test-456"},
    }
