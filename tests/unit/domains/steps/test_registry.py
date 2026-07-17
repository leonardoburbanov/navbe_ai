"""Tests for step registry."""

from collections.abc import Iterator

import pytest

from navbe.core.exceptions import NotFoundError
from navbe.domains.steps.registry import StepRegistry


@pytest.fixture(autouse=True)
def reset_registry() -> Iterator[None]:
    """Avoid cross-test registry pollution."""
    original = StepRegistry._steps
    StepRegistry._steps = {}
    yield
    StepRegistry._steps = original


class FakeStep:
    """Fake registry target."""


def test_register_and_get() -> None:
    """Registered steps can be retrieved by key."""
    StepRegistry.register("fake")(FakeStep)
    assert StepRegistry.get("fake") is FakeStep


def test_get_unknown_raises_not_found() -> None:
    """Unknown keys raise NotFoundError with available details."""
    with pytest.raises(NotFoundError) as exc_info:
        StepRegistry.get("nonexistent")

    assert exc_info.value.details["step_type"] == "nonexistent"
    assert "available" in exc_info.value.details


def test_list_all_returns_copy() -> None:
    """Mutating list_all output does not mutate registry state."""
    StepRegistry.register("fake")(FakeStep)
    listed = StepRegistry.list_all()
    listed.clear()
    assert StepRegistry.get("fake") is FakeStep
