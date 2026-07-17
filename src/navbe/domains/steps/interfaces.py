"""Step execution contracts."""

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class StepContext(BaseModel):
    """Runtime context passed to every standalone step."""

    node_id: str
    input_data: Any
    flow_vars: dict[str, Any] = {}


@runtime_checkable
class Step(Protocol):
    """Protocol implemented by all step types."""

    config_schema: type[BaseModel]

    async def run(self, ctx: StepContext) -> Any:
        """Run the step against a direct context."""
        ...
