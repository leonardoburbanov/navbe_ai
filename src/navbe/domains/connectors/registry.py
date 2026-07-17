"""Registry for available connector implementations."""

from typing import ClassVar

from navbe.core.exceptions import NotFoundError


class ConnectorRegistry:
    """In-memory registry keyed by connector type."""

    _connectors: ClassVar[dict[str, type]] = {}

    @classmethod
    def register(cls, key: str):
        """Register a connector class under ``key``."""

        def decorator(connector_cls):
            cls._connectors[key] = connector_cls
            return connector_cls

        return decorator

    @classmethod
    def get(cls, key: str) -> type:
        """Return a registered connector class or raise ``NotFoundError``."""
        if key not in cls._connectors:
            raise NotFoundError(
                f"Unknown connector type: '{key}'",
                details={"connector_type": key, "available": list(cls._connectors)},
            )
        return cls._connectors[key]

    @classmethod
    def list_all(cls) -> dict[str, type]:
        """Return a copy of registered connector classes."""
        return dict(cls._connectors)
