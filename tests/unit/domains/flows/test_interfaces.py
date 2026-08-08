"""Tests for flow repository Protocol."""

from datetime import UTC, datetime

from navbe.core.exceptions import NotFoundError
from navbe.domains.flows.interfaces import FlowRepository
from navbe.domains.flows.models import FlowMetadata, FlowSpec


class FakeFlowRepository:
    """In-memory FlowRepository for protocol / service tests."""

    def __init__(self) -> None:
        """Create empty store."""
        self.saved: list[FlowSpec] = []
        self.updated: list[FlowSpec] = []
        self.flows: dict[str, FlowSpec] = {}
        self.versions: dict[str, int] = {}

    async def save(self, flow_spec: FlowSpec) -> FlowMetadata:
        """Record and store a flow."""
        self.saved.append(flow_spec)
        self.flows[flow_spec.flow_id] = flow_spec
        self.versions[flow_spec.flow_id] = 1
        now = datetime.now(UTC)
        return FlowMetadata(
            flow_id=flow_spec.flow_id,
            name=flow_spec.name,
            created_at=now,
            updated_at=now,
            version=1,
            path=f"/fake/{flow_spec.flow_id}/flow.json",
        )

    async def get(self, flow_id: str) -> FlowSpec:
        """Return a stored flow."""
        if flow_id not in self.flows:
            raise NotFoundError(
                f"Flow '{flow_id}' not found",
                details={"flow_id": flow_id},
            )
        return self.flows[flow_id]

    async def list(self) -> list[FlowMetadata]:
        """List stored flow metadata."""
        now = datetime.now(UTC)
        return [
            FlowMetadata(
                flow_id=flow.flow_id,
                name=flow.name,
                created_at=now,
                updated_at=now,
                version=self.versions.get(flow.flow_id, 1),
                path=f"/fake/{flow.flow_id}/flow.json",
            )
            for flow in self.flows.values()
        ]

    async def update(self, flow_spec: FlowSpec) -> FlowMetadata:
        """Replace a stored flow."""
        if flow_spec.flow_id not in self.flows:
            raise NotFoundError(
                f"Flow '{flow_spec.flow_id}' not found",
                details={"flow_id": flow_spec.flow_id},
            )
        self.updated.append(flow_spec)
        self.flows[flow_spec.flow_id] = flow_spec
        self.versions[flow_spec.flow_id] = self.versions.get(flow_spec.flow_id, 1) + 1
        now = datetime.now(UTC)
        return FlowMetadata(
            flow_id=flow_spec.flow_id,
            name=flow_spec.name,
            created_at=now,
            updated_at=now,
            version=self.versions[flow_spec.flow_id],
            path=f"/fake/{flow_spec.flow_id}/flow.json",
        )

    async def upsert(self, flow_spec: FlowSpec) -> FlowMetadata:
        """Upsert without archival."""
        now = datetime.now(UTC)
        if flow_spec.flow_id in self.flows:
            self.flows[flow_spec.flow_id] = flow_spec
            return FlowMetadata(
                flow_id=flow_spec.flow_id,
                name=flow_spec.name,
                created_at=now,
                updated_at=now,
                version=self.versions.get(flow_spec.flow_id, 1),
                path=f"/fake/{flow_spec.flow_id}/flow.json",
            )
        return await self.save(flow_spec)

    async def delete_index(self, flow_id: str) -> None:
        """Remove from in-memory store."""
        self.flows.pop(flow_id, None)
        self.versions.pop(flow_id, None)

    async def delete(self, flow_id: str) -> None:
        """Remove a flow or raise if missing."""
        if flow_id not in self.flows:
            raise NotFoundError(
                f"Flow '{flow_id}' not found",
                details={"flow_id": flow_id},
            )
        await self.delete_index(flow_id)


def test_fake_repository_satisfies_protocol() -> None:
    """Runtime-checkable Protocol accepts structural implementation."""
    assert isinstance(FakeFlowRepository(), FlowRepository)
