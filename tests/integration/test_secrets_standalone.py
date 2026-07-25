"""Standalone secrets resolution without Flow or connectors."""

from pathlib import Path

from navbe.domains.secrets.json_file import JsonFileSecretsProvider
from navbe.domains.secrets.service import SecretsService


async def test_secret_resolution_end_to_end(tmp_path: Path) -> None:
    """Resolve nested secret refs end-to-end via JSON credentials file."""
    store = JsonFileSecretsProvider(tmp_path / "creds.json")
    service = SecretsService(store, store=store)
    await service.set("SALES_BOT_KEY", "sk-test-456")

    config = {
        "base_url": "https://example.com",
        "headers": {"Authorization": {"$secret": "SALES_BOT_KEY"}},
    }
    resolved = await service.resolve_config(config)

    assert resolved == {
        "base_url": "https://example.com",
        "headers": {"Authorization": "sk-test-456"},
    }
