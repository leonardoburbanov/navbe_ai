"""Tests for CatalogService."""

import json

import navbe.domains.connectors.implementations  # noqa: F401
import navbe.domains.steps.implementations  # noqa: F401
from navbe.domains.catalog.service import CatalogService
from navbe.domains.connectors.implementations.http import HTTPConnector


async def test_get_steps_catalog_includes_all_five_registered_steps() -> None:
    """Built-in steps appear with JSON Schema properties."""
    catalog = CatalogService()
    steps = await catalog.get_steps_catalog()
    for key in ("http_request", "set_var", "transform", "llm_call", "router"):
        assert key in steps
        schema = steps[key]["config_schema"]
        assert "properties" in schema
        json.dumps(schema)


async def test_get_steps_catalog_includes_synthetic_approval() -> None:
    """approval is advertised even though it is not in StepRegistry."""
    catalog = CatalogService()
    steps = await catalog.get_steps_catalog()
    assert "approval" in steps
    assert steps["approval"]["step_type"] == "approval"
    json.dumps(steps["approval"]["config_schema"])


async def test_get_connectors_catalog_includes_http_with_actions() -> None:
    """http connector advertises the same actions as HTTPConnector."""
    catalog = CatalogService()
    connectors = await catalog.get_connectors_catalog()
    assert "http" in connectors
    assert connectors["http"]["actions"] == HTTPConnector.actions
    json.dumps(connectors["http"]["config_schema"])


async def test_get_full_catalog_combines_both() -> None:
    """Full catalog has non-empty steps and connectors sections."""
    catalog = CatalogService()
    full = await catalog.get_full_catalog()
    assert set(full) == {"steps", "connectors"}
    assert full["steps"]
    assert full["connectors"]
    json.dumps(full)


async def test_catalog_reflects_empty_registry_gracefully() -> None:
    """Empty registries do not crash; registered sections stay empty."""

    class EmptyStepRegistry:
        @classmethod
        def list_all(cls) -> dict[str, type]:
            return {}

    class EmptyConnectorRegistry:
        @classmethod
        def list_all(cls) -> dict[str, type]:
            return {}

    catalog = CatalogService(
        step_registry=EmptyStepRegistry,  # type: ignore[arg-type]
        connector_registry=EmptyConnectorRegistry,  # type: ignore[arg-type]
    )
    assert await catalog.get_connectors_catalog() == {}
    steps = await catalog.get_steps_catalog()
    assert set(steps) == {"approval"}
