"""Use-cases for validating and persisting flows."""

from typing import Any

import pydantic

from navbe.core.exceptions import ValidationError
from navbe.domains.flows.interfaces import FlowRepository
from navbe.domains.flows.models import FlowMetadata, FlowSpec
from navbe.domains.flows.validator import ValidationResult, validate_graph


class FlowService:
    """Facade for flow validation and persistence."""

    def __init__(self, repository: FlowRepository) -> None:
        """Create a service with an injectable repository."""
        self._repository = repository

    def validate(self, flow_spec: FlowSpec | dict[str, Any]) -> ValidationResult:
        """Parse (if dict) and run structural graph validation."""
        if isinstance(flow_spec, dict):
            try:
                flow_spec = FlowSpec.model_validate(flow_spec)
            except pydantic.ValidationError as exc:
                raise ValidationError(
                    "Invalid FlowSpec structure",
                    details={"errors": exc.errors()},
                ) from exc
        return validate_graph(flow_spec)

    async def create(self, flow_spec_dict: dict[str, Any]) -> FlowMetadata:
        """Validate then persist a new flow."""
        try:
            flow_spec = FlowSpec.model_validate(flow_spec_dict)
        except pydantic.ValidationError as exc:
            raise ValidationError(
                "Invalid FlowSpec structure",
                details={"errors": exc.errors()},
            ) from exc

        result = self.validate(flow_spec)
        if not result.valid:
            raise ValidationError(
                "FlowSpec failed graph validation",
                details={"issues": [issue.model_dump() for issue in result.issues]},
            )

        return await self._repository.save(flow_spec)

    async def update(self, flow_spec_dict: dict[str, Any]) -> FlowMetadata:
        """Validate then overwrite an existing flow (archives prior version)."""
        try:
            flow_spec = FlowSpec.model_validate(flow_spec_dict)
        except pydantic.ValidationError as exc:
            raise ValidationError(
                "Invalid FlowSpec structure",
                details={"errors": exc.errors()},
            ) from exc

        result = self.validate(flow_spec)
        if not result.valid:
            raise ValidationError(
                "FlowSpec failed graph validation",
                details={"issues": [issue.model_dump() for issue in result.issues]},
            )

        return await self._repository.update(flow_spec)

    async def get(self, flow_id: str) -> FlowSpec:
        """Load a flow by id."""
        return await self._repository.get(flow_id)

    async def list(self) -> list[FlowMetadata]:
        """List saved flow metadata."""
        return await self._repository.list()

    async def delete(self, flow_id: str) -> None:
        """Delete a persisted flow (files + index)."""
        await self._repository.delete(flow_id)
