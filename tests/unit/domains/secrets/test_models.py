"""Tests for secret models."""

import pytest

from navbe.core.exceptions import ValidationError
from navbe.domains.secrets.models import (
    SecretRef,
    is_secret_ref,
    mask_secret,
    parse_secret_ref,
    validate_app,
)


def test_is_secret_ref_true_for_valid_shape() -> None:
    """Valid secret-ref shape is detected."""
    assert is_secret_ref({"$secret": "API_KEY"}) is True


def test_is_secret_ref_false_for_plain_dict() -> None:
    """Plain dicts are not secret refs."""
    assert is_secret_ref({"foo": "bar"}) is False


def test_is_secret_ref_false_for_non_dict() -> None:
    """Non-dicts are not secret refs."""
    assert is_secret_ref("plain string") is False
    assert is_secret_ref(123) is False
    assert is_secret_ref(None) is False


def test_is_secret_ref_false_for_extra_keys() -> None:
    """Extra keys disqualify the secret-ref shape."""
    assert is_secret_ref({"$secret": "X", "other": "y"}) is False


def test_parse_secret_ref_extracts_key() -> None:
    """parse_secret_ref extracts the key name."""
    assert parse_secret_ref({"$secret": "API_KEY"}) == SecretRef(key="API_KEY")


def test_mask_secret_shows_last_four() -> None:
    """Long values mask to **** + last 4."""
    assert mask_secret("re_abcdefgh") == "****efgh"


def test_mask_secret_short_value_fully_masked() -> None:
    """Short values do not leak via hint."""
    assert mask_secret("ab") == "****"
    assert mask_secret("abc") == "****"


def test_validate_app_accepts_slug() -> None:
    """Lowercase app slugs are accepted."""
    assert validate_app("resend") == "resend"
    assert validate_app("langfuse-cloud") == "langfuse-cloud"


def test_validate_app_rejects_invalid() -> None:
    """Invalid app slugs raise ValidationError."""
    with pytest.raises(ValidationError):
        validate_app("Resend")
    with pytest.raises(ValidationError):
        validate_app("1bad")
