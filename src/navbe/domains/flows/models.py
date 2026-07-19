"""Pydantic models for flow definitions."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from navbe.domains.connectors.models import ConnectorInstanceConfig


class NodeSpec(BaseModel):
    """A single step invocation inside a flow."""

    model_config = {"extra": "forbid"}

    id: str
    step_type: str
    config: dict = {}


class EdgeSpec(BaseModel):
    """A control-flow edge between nodes."""

    model_config = {"extra": "forbid", "populate_by_name": True}

    from_: str = Field(alias="from")
    to: str | None = None
    condition: str | None = None


class FlowSpec(BaseModel):
    """Agent-generated flow document (nodes, edges, connectors)."""

    model_config = {"extra": "forbid"}

    flow_id: str
    name: str = ""
    entry_node: str
    connectors: dict[str, ConnectorInstanceConfig] = {}
    nodes: list[NodeSpec]
    edges: list[EdgeSpec]

    @field_validator("nodes")
    @classmethod
    def nodes_must_not_be_empty(cls, v: list[NodeSpec]) -> list[NodeSpec]:
        """Reject flows with no nodes."""
        if not v:
            raise ValueError("FlowSpec must contain at least one node")
        return v


class FlowMetadata(BaseModel):
    """Index metadata for a persisted flow."""

    flow_id: str
    name: str
    created_at: datetime
    updated_at: datetime
    version: int
    path: str
