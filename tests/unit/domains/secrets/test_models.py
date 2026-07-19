"""Tests for secret models."""

from navbe.domains.secrets.models import SecretRef, is_secret_ref, parse_secret_ref


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
