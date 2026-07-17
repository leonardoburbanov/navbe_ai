"""Pydantic models for connector references inside flows."""

from pydantic import BaseModel


class ConnectorInstanceConfig(BaseModel):
    """How a connector is referenced inside a FlowSpec's ``connectors`` block."""

    type: str
    config: dict
