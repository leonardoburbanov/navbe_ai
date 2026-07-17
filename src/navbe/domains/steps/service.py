"""Use-cases for validating and building steps."""

from typing import Any, cast

import pydantic

from navbe.core.exceptions import ValidationError
from navbe.domains.steps.registry import StepRegistry


class StepService:
    """Facade over the step registry."""

    def __init__(self, registry: type[StepRegistry] = StepRegistry) -> None:
        """Create a service with an injectable registry class."""
        self._registry = registry

    def get_config_schema(self, step_type: str) -> dict[str, Any]:
        """Return a step config JSON schema."""
        step_cls = cast(Any, self._registry.get(step_type))
        return step_cls.config_schema.model_json_schema()

    def validate_config(self, step_type: str, config: dict[str, Any]) -> None:
        """Validate config for a registered step type."""
        step_cls = cast(Any, self._registry.get(step_type))
        try:
            step_cls.config_schema.model_validate(config)
        except pydantic.ValidationError as exc:
            raise ValidationError(
                f"Invalid config for step_type '{step_type}'",
                details={"errors": exc.errors()},
            ) from exc

    def build(self, step_type: str, config: dict[str, Any]) -> Any:
        """Build a step instance from registered type + config."""
        step_cls = self._registry.get(step_type)
        return step_cls(config)
