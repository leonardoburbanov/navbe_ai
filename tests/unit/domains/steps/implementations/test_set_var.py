"""Tests for set-var step."""

import pytest

from navbe.core.exceptions import ValidationError
from navbe.domains.steps.implementations.set_var import SetVarStep
from navbe.domains.steps.interfaces import StepContext


async def test_extract_top_level_field() -> None:
    """Extract a top-level field from input data."""
    step = SetVarStep({"var_name": "session", "value_from": "session_id"})
    result = await step.run(StepContext(node_id="n1", input_data={"session_id": "abc"}))
    assert result == {"var_name": "session", "value": "abc"}


async def test_extract_nested_field() -> None:
    """Extract a nested field from input data."""
    step = SetVarStep({"var_name": "user_id", "value_from": "data.user.id"})
    result = await step.run(
        StepContext(node_id="n1", input_data={"data": {"user": {"id": "u1"}}})
    )
    assert result == {"var_name": "user_id", "value": "u1"}


async def test_missing_path_returns_none() -> None:
    """JMESPath missing-path behavior is preserved."""
    step = SetVarStep({"var_name": "missing", "value_from": "data.nope"})
    result = await step.run(StepContext(node_id="n1", input_data={"data": {}}))
    assert result == {"var_name": "missing", "value": None}


async def test_invalid_jmespath_expression_raises() -> None:
    """Malformed JMESPath raises Navbe ValidationError."""
    step = SetVarStep({"var_name": "bad", "value_from": "[[["})

    with pytest.raises(ValidationError):
        await step.run(StepContext(node_id="n1", input_data={}))
