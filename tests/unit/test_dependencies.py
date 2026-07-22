"""Tests for shared DI providers in dependencies.py."""

import pytest

from navbe.dependencies import (
    clear_dependency_caches,
    get_flow_service,
    get_run_service,
    get_secrets_service,
)
from navbe.domains.secrets.service import EnvSecretsProvider


@pytest.fixture(autouse=True)
def _reset_dependency_caches() -> None:
    """Ensure each test starts with empty provider caches."""
    clear_dependency_caches()
    yield
    clear_dependency_caches()


def test_get_flow_service_returns_singleton() -> None:
    """Two calls return the same object."""
    assert get_flow_service() is get_flow_service()


def test_get_run_service_wires_correct_dependencies() -> None:
    """RunService shares the FlowService singleton."""
    assert get_run_service()._flow_service is get_flow_service()


def test_dependencies_resettable_between_tests() -> None:
    """cache_clear produces genuinely new instances afterward."""
    first_flow = get_flow_service()
    first_run = get_run_service()
    clear_dependency_caches()
    second_flow = get_flow_service()
    second_run = get_run_service()
    assert first_flow is not second_flow
    assert first_run is not second_run
    assert second_run._flow_service is second_flow


def test_get_secrets_service_uses_env_provider() -> None:
    """SecretsService chains JSON credentials then EnvSecretsProvider."""
    from navbe.domains.secrets.json_file import ChainedSecretsProvider

    provider = get_secrets_service()._provider
    assert isinstance(provider, ChainedSecretsProvider)
    assert any(isinstance(p, EnvSecretsProvider) for p in provider._providers)
