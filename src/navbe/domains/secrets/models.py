"""Pydantic models and key validation for secrets."""

import re
from typing import Any

from pydantic import BaseModel

from navbe.core.exceptions import ValidationError

# Env-style keys only (ponytail: flat map — upgrade: namespaced connector records).
_SECRET_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


class SecretRef(BaseModel):
    """A reference to a named secret."""

    key: str


def validate_secret_key(key: str) -> str:
    """Return ``key`` if it matches the allowed pattern, else raise ValidationError."""
    if not key or not _SECRET_KEY_RE.match(key):
        raise ValidationError(
            "Invalid secret key",
            details={
                "key": key,
                "hint": "use env-style names: UPPER_SNAKE_CASE starting with a letter",
            },
        )
    return key


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
