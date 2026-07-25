"""Tests for schedule when-expression parsing."""

from datetime import UTC, datetime, timedelta

import pytest

from navbe.core.exceptions import ValidationError
from navbe.domains.schedules.when import compute_next_run_at, validate_when


def test_validate_relative_when() -> None:
    """Relative +Nh forms are accepted."""
    assert validate_when("+30s") == "+30s"
    assert validate_when("+1h") == "+1h"
    assert validate_when(" +1d ") == "+1d"


def test_validate_cron_when() -> None:
    """Five-field cron is accepted."""
    assert validate_when("*/5 * * * *") == "*/5 * * * *"


def test_validate_rejects_garbage() -> None:
    """Unknown when expressions raise ValidationError."""
    with pytest.raises(ValidationError):
        validate_when("tomorrow")


def test_compute_next_relative() -> None:
    """Relative when advances from the given base time."""
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    nxt = compute_next_run_at("+30s", after=base)
    assert nxt == base + timedelta(seconds=30)


def test_compute_next_cron() -> None:
    """Cron when returns a time after the base."""
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    nxt = compute_next_run_at("0 * * * *", after=base)
    assert nxt > base
