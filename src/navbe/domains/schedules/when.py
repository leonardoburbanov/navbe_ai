"""Parse ``when`` expressions into next-fire datetimes."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from croniter import croniter

from navbe.core.exceptions import ValidationError

_RELATIVE_RE = re.compile(
    r"^\+(?P<amount>\d+)(?P<unit>[smhd])$",
    re.IGNORECASE,
)

_UNIT_SECONDS: dict[str, int] = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
}


def parse_relative_delta(when: str) -> timedelta | None:
    """Return a timedelta for ``+30s`` / ``+1h`` style, else None."""
    match = _RELATIVE_RE.match(when.strip())
    if match is None:
        return None
    amount = int(match.group("amount"))
    unit = match.group("unit").lower()
    return timedelta(seconds=amount * _UNIT_SECONDS[unit])


def is_cron_expression(when: str) -> bool:
    """True when ``when`` looks like a 5-field cron expression."""
    parts = when.strip().split()
    return len(parts) == 5 and croniter.is_valid(when.strip())


def validate_when(when: str) -> str:
    """Return stripped ``when`` if valid relative or cron; else raise."""
    cleaned = when.strip()
    if not cleaned:
        raise ValidationError(
            "Schedule 'when' must not be empty",
            details={"when": when},
        )
    if parse_relative_delta(cleaned) is not None:
        return cleaned
    if is_cron_expression(cleaned):
        return cleaned
    raise ValidationError(
        "Invalid schedule 'when' (use +30s/+1h/+1d or a 5-field cron)",
        details={"when": when},
    )


def compute_next_run_at(when: str, *, after: datetime | None = None) -> datetime:
    """Compute the next fire time after ``after`` (default: now UTC)."""
    cleaned = validate_when(when)
    base = after if after is not None else datetime.now(UTC)
    if base.tzinfo is None:
        base = base.replace(tzinfo=UTC)
    else:
        base = base.astimezone(UTC)

    relative = parse_relative_delta(cleaned)
    if relative is not None:
        return base + relative

    iterator = croniter(cleaned, base)
    nxt = iterator.get_next(datetime)
    if nxt.tzinfo is None:
        return nxt.replace(tzinfo=UTC)
    return nxt.astimezone(UTC)
