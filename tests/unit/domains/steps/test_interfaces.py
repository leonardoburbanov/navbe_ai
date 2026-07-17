"""Tests for step interfaces."""

from typing import Any

from pydantic import BaseModel

from navbe.domains.steps.interfaces import Step, StepContext


class FakeConfig(BaseModel):
    """Fake config schema for protocol checks."""


class FakeStep:
    """Fake step that structurally satisfies ``Step``."""

    config_schema = FakeConfig

    async def run(self, ctx: StepContext) -> Any:
        """Return input data unchanged."""
        return ctx.input_data


def test_fake_step_satisfies_protocol() -> None:
    """Runtime-checkable Protocol accepts structural implementation."""
    assert isinstance(FakeStep(), Step)


def test_step_context_defaults() -> None:
    """StepContext defaults flow_vars to an empty dict."""
    assert StepContext(node_id="n1", input_data=None).flow_vars == {}
