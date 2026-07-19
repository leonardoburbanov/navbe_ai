"""Pydantic models for secret references."""

from typing import Any

from pydantic import BaseModel


class SecretRef(BaseModel):
    """A reference to a named secret."""

    key: str


def is_secret_ref(value: Any) -> bool:
    """True if value is shaped like ``{"$secret": "SOME_KEY"}``."""
    return (
        isinstance(value, dict)
        and set(value.keys()) == {"$secret"}
        and isinstance(value.get("$secret"), str)
    )


def parse_secret_ref(value: dict) -> SecretRef:
    """Parse a secret-ref dict into a ``SecretRef``."""
    return SecretRef(key=value["$secret"])
