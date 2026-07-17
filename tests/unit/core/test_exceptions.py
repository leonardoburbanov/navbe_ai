"""Tests for ``navbe.core.exceptions``."""

from navbe.core.exceptions import (
    ConfigurationError,
    ExecutionError,
    NavbeError,
    NotFoundError,
    ValidationError,
)


def test_all_inherit_from_navbe_error() -> None:
    """Every public error subclass is a ``NavbeError`` instance."""
    for cls in (ValidationError, NotFoundError, ExecutionError, ConfigurationError):
        err = cls("boom")
        assert isinstance(err, NavbeError)


def test_message_and_details_accessible() -> None:
    """Message and details are exposed as attributes."""
    err = ValidationError("x", details={"field": "y"})
    assert err.message == "x"
    assert err.details == {"field": "y"}


def test_default_details_is_empty_dict() -> None:
    """Omitting details yields ``{}``, never ``None``."""
    err = ValidationError("x")
    assert err.details == {}
    assert err.details is not None
