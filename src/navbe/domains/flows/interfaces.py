"""Flow repository contracts."""

from typing import Protocol, runtime_checkable

from navbe.domains.flows.models import FlowMetadata, FlowSpec


@runtime_checkable
class FlowRepository(Protocol):
    """Persistence port for validated flow specs."""

    async def save(self, flow_spec: FlowSpec) -> FlowMetadata:
        """Persist a new flow and return its metadata."""
        ...

    async def get(self, flow_id: str) -> FlowSpec:
        """Load a flow by id."""
        ...

    async def list(self) -> list[FlowMetadata]:
        """List indexed flow metadata."""
        ...

    async def update(self, flow_spec: FlowSpec) -> FlowMetadata:
        """Update an existing flow, archiving the previous version."""
        ...

    async def upsert(self, flow_spec: FlowSpec) -> FlowMetadata:
        """Write flow.json and upsert index without archival (sync import)."""
        ...

    async def delete_index(self, flow_id: str) -> None:
        """Remove a flow_id from the index after its directory was deleted."""
        ...
