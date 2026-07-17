"""Tests for step config models."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from navbe.domains.steps.models import StepConfig


class FakeConfig(StepConfig):
    """Config used to prove extra fields are rejected."""

    x: int


def test_extra_field_rejected() -> None:
    """Unknown fields fail validation loudly."""
    with pytest.raises(PydanticValidationError):
        FakeConfig(x=1, typo=2)
