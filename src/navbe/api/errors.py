"""Shared NavbeError → HTTPException mapping for REST routes."""

from fastapi import HTTPException

from navbe.core.exceptions import NavbeError

_STATUS_MAP = {
    "validation_error": 422,
    "not_found": 404,
    "execution_error": 500,
    "configuration_error": 500,
}


def to_http_exception(exc: NavbeError) -> HTTPException:
    """Map a NavbeError to a structured HTTPException."""
    return HTTPException(
        status_code=_STATUS_MAP.get(exc.code, 500),
        detail={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        },
    )
