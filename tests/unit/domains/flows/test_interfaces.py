"""Tests for flow repository Protocol."""

from datetime import UTC, datetime

from navbe.domains.flows.interfaces import FlowRepository
from navbe.domains.flows.models import FlowMetadata, FlowSpec


class FakeFlowRepository:
    """In-memory FlowRepository for protocol / service tests."""

    def __init__(self) -> None:
        """Create empty store."""
        self.saved: list[FlowSpec] = []
        self.flows: dict[str, FlowSpec] = {}

    async def save(self, flow_spec: FlowSpec) -> FlowMetadata:
        """Record and store a flow."""
        self.saved.append(flow_spec)
        self.flows[flow_spec.flow_id] = flow_spec
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
                version=1,
                path=f"/fake/{flow.flow_id}/flow.json",
            )
            for flow in self.flows.values()
        ]

    async def update(self, flow_spec: FlowSpec) -> FlowMetadata:
        """Replace a stored flow."""
        self.flows[flow_spec.flow_id] = flow_spec
        now = datetime.now(UTC)
        return FlowMetadata(
            flow_id=flow_spec.flow_id,
            name=flow_spec.name,
            created_at=now,
            updated_at=now,
            version=2,
            path=f"/fake/{flow_spec.flow_id}/flow.json",
        )


def test_fake_repository_satisfies_protocol() -> None:
    """Runtime-checkable Protocol accepts structural implementation."""
    assert isinstance(FakeFlowRepository(), FlowRepository)
