"""Base exception hierarchy for Navbe.

Every domain error must inherit from ``NavbeError`` — never raise bare
``Exception`` / ``ValueError`` from domain code.
"""


class NavbeError(Exception):
    """Base exception. Every domain error inherits from this."""

    code: str = "navbe_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        """Create an error with a message and optional structured details."""
        self.message = message
        self.details = details or {}
        super().__init__(message)


class ValidationError(NavbeError):
    """Input or domain validation failed."""

    code = "validation_error"


class NotFoundError(NavbeError):
    """Requested resource does not exist."""

    code = "not_found"


class ExecutionError(NavbeError):
    """A flow or step failed during execution."""

    code = "execution_error"


class ConfigurationError(NavbeError):
    """Invalid or missing configuration."""

    code = "configuration_error"
