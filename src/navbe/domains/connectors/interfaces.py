"""Connector contracts."""

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class ConnectorConfig(BaseModel):
    """Base connector configuration."""

    model_config = {"extra": "forbid"}


@runtime_checkable
class Connector(Protocol):
    """Protocol implemented by all connector types."""

    config_schema: type[ConnectorConfig]
    actions: dict[str, str]

    async def test_connection(self) -> bool:
        """Return whether the external system is reachable."""
        ...

    async def execute(self, action: str, payload: dict) -> Any:
        """Run a named connector action."""
        ...
