"""Tests for step service."""

import pytest

import navbe.domains.steps.implementations  # noqa: F401
from navbe.core.exceptions import NotFoundError, ValidationError
from navbe.domains.steps.implementations.set_var import SetVarStep
from navbe.domains.steps.service import StepService


def test_get_config_schema_returns_valid_json_schema() -> None:
    """HTTP request schema exposes expected config properties."""
    schema = StepService().get_config_schema("http_request")
    assert "properties" in schema
    assert {"connector", "method", "path", "body_template", "params"}.issubset(
        schema["properties"]
    )


def test_validate_config_valid_passes_silently() -> None:
    """Valid http_request config raises nothing."""
    StepService().validate_config("http_request", {"connector": "api", "method": "get"})


def test_validate_config_missing_required_field_raises() -> None:
    """Invalid config becomes Navbe ValidationError with Pydantic details."""
    with pytest.raises(ValidationError) as exc_info:
        StepService().validate_config("http_request", {"method": "get"})

    assert exc_info.value.details["errors"]


def test_build_returns_instance_of_correct_step_class() -> None:
    """Registry-backed build creates the expected step implementation."""
    step = StepService().build("set_var", {"var_name": "x", "value_from": "x"})
    assert isinstance(step, SetVarStep)


def test_unknown_step_type_propagates_not_found() -> None:
    """Unknown step types bubble up NotFoundError unchanged."""
    with pytest.raises(NotFoundError):
        StepService().get_config_schema("missing")
