"""Agent-facing catalog of registered steps and connectors."""

from typing import Any, cast

from navbe.domains.connectors.registry import ConnectorRegistry
from navbe.domains.steps.registry import StepRegistry

# approval is handled by graph_compiler, not StepRegistry — agents still need
# to discover it when authoring FlowSpecs.
_SYNTHETIC_STEPS: dict[str, dict[str, Any]] = {
    "approval": {
        "step_type": "approval",
        "config_schema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "description": (
                "Pauses execution for human approval. Handled structurally "
                "by the execution engine, not a registered Step class."
            ),
        },
    }
}


class CatalogService:
    """Read-only catalog over StepRegistry and ConnectorRegistry."""

    def __init__(
        self,
        step_registry: type[StepRegistry] = StepRegistry,
        connector_registry: type[ConnectorRegistry] = ConnectorRegistry,
    ) -> None:
        """Bind registry classes used for catalog lookups."""
        self._steps = step_registry
        self._connectors = connector_registry

    async def get_steps_catalog(self) -> dict[str, dict]:
        """Return JSON Schema catalog for all discoverable step types."""
        registered = {
            key: {
                "step_type": key,
                "config_schema": cast(Any, step_cls).config_schema.model_json_schema(),
            }
            for key, step_cls in self._steps.list_all().items()
        }
        return {**registered, **_SYNTHETIC_STEPS}

    async def get_connectors_catalog(self) -> dict[str, dict]:
        """Return JSON Schema catalog for all registered connector types."""
        return {
            key: {
                "connector_type": key,
                "config_schema": cast(Any, connector_cls).config_schema.model_json_schema(),
                "actions": cast(Any, connector_cls).actions,
            }
            for key, connector_cls in self._connectors.list_all().items()
        }

    async def get_full_catalog(self) -> dict:
        """Return combined steps + connectors catalog."""
        return {
            "steps": await self.get_steps_catalog(),
            "connectors": await self.get_connectors_catalog(),
        }
