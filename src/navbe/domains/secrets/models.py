"""Pydantic models and key validation for secrets."""

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from navbe.core.exceptions import ValidationError

# Env-style keys only (ponytail: flat map — upgrade: namespaced connector records).
_SECRET_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_APP_SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]*$")


class SecretRef(BaseModel):
    """A reference to a named secret."""

    key: str


class CredentialRecord(BaseModel):
    """Stored credential entry (value kept internal to the secrets domain)."""

    value: str = Field(min_length=1)
    app: str | None = None
    updated_at: datetime | None = None


class CredentialHint(BaseModel):
    """Public credential metadata — never includes the secret value."""

    key: str
    hint: str | None = None
    app: str | None = None
    source: Literal["store", "env"]
    updated_at: datetime | None = None


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


def validate_app(app: str) -> str:
    """Return ``app`` if it is a valid lowercase slug, else raise ValidationError."""
    if not app or not _APP_SLUG_RE.match(app):
        raise ValidationError(
            "Invalid app slug",
            details={
                "app": app,
                "hint": "use lowercase slugs: [a-z][a-z0-9_-]* (e.g. resend)",
            },
        )
    return app


def mask_secret(value: str) -> str:
    """Return a masked preview: ``****`` + last 4 chars (or ``****`` if too short)."""
    if len(value) < 4:
        return "****"
    return f"****{value[-4:]}"


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
