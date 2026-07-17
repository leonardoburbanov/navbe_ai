"""Registry for available step implementations."""

from typing import ClassVar

from navbe.core.exceptions import NotFoundError


class StepRegistry:
    """In-memory registry keyed by step type."""

    _steps: ClassVar[dict[str, type]] = {}

    @classmethod
    def register(cls, key: str):
        """Register a step class under ``key``."""

        def decorator(step_cls):
            cls._steps[key] = step_cls
            return step_cls

        return decorator

    @classmethod
    def get(cls, key: str) -> type:
        """Return a registered step class or raise ``NotFoundError``."""
        if key not in cls._steps:
            raise NotFoundError(
                f"Unknown step_type: '{key}'",
                details={"step_type": key, "available": list(cls._steps)},
            )
        return cls._steps[key]

    @classmethod
    def list_all(cls) -> dict[str, type]:
        """Return a copy of registered step classes."""
        return dict(cls._steps)
