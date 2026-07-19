"""Tests for secrets interfaces."""

from navbe.domains.secrets.interfaces import SecretsProvider


class FakeSecretsProvider:
    """Fake provider satisfying SecretsProvider."""

    async def resolve(self, key: str) -> str:
        """Return a deterministic value."""
        return f"value-for-{key}"


def test_fake_provider_satisfies_protocol() -> None:
    """Runtime-checkable Protocol accepts structural implementation."""
    assert isinstance(FakeSecretsProvider(), SecretsProvider)
