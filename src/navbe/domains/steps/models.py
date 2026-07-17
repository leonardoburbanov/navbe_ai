"""Pydantic models for step configuration."""

from pydantic import BaseModel


class StepConfig(BaseModel):
    """Base class every step-specific config inherits from."""

    model_config = {"extra": "forbid"}
