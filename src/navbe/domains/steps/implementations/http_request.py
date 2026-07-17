"""HTTP request step implementation."""

import re
from typing import Any, Protocol

from navbe.core.exceptions import ExecutionError, ValidationError
from navbe.domains.steps.interfaces import StepContext
from navbe.domains.steps.models import StepConfig
from navbe.domains.steps.registry import StepRegistry

_TEMPLATE_RE = re.compile(r"{{\s*(flow_vars|node_outputs)\.([a-zA-Z0-9_.-]+)\s*}}")


class Connector(Protocol):
    """Minimal connector contract needed by ``HTTPRequestStep``."""

    async def execute(self, method: str, request: dict[str, Any]) -> Any:
        """Execute a connector-specific request."""
        ...


class HTTPRequestConfig(StepConfig):
    """Configuration for an HTTP request step."""

    connector: str
    method: str
    path: str = ""
    body_template: dict[str, Any] = {}
    params: dict[str, Any] = {}


def _lookup_path(root: Any, path: str) -> Any:
    """Resolve a dotted path inside dictionaries/objects."""
    current = root
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        if hasattr(current, part):
            current = getattr(current, part)
            continue
        raise ValidationError(
            f"Unable to resolve template key '{path}'",
            details={"path": path, "missing": part},
        )
    return current


def _resolve_match(match: re.Match[str], flow_vars: dict[str, Any]) -> Any:
    """Resolve one placeholder regex match."""
    scope, path = match.groups()
    root = flow_vars if scope == "flow_vars" else flow_vars.get("node_outputs", {})
    return _lookup_path(root, path)


def resolve_templates(value: Any, flow_vars: dict[str, Any]) -> Any:
    """Recursively resolve ``{{flow_vars.x}}`` and ``{{node_outputs.y.z}}``."""
    if isinstance(value, dict):
        return {key: resolve_templates(item, flow_vars) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_templates(item, flow_vars) for item in value]
    if not isinstance(value, str):
        return value

    full_match = _TEMPLATE_RE.fullmatch(value)
    if full_match:
        return _resolve_match(full_match, flow_vars)

    return _TEMPLATE_RE.sub(lambda match: str(_resolve_match(match, flow_vars)), value)


@StepRegistry.register("http_request")
class HTTPRequestStep:
    """Execute an HTTP-like request through an injected connector."""

    config_schema = HTTPRequestConfig

    def __init__(self, config: dict[str, Any]) -> None:
        """Validate and store request config."""
        self.config = HTTPRequestConfig.model_validate(config)

    async def run(self, ctx: StepContext) -> Any:
        """Resolve templates and call the named connector."""
        connectors = ctx.flow_vars.get("connectors", {})
        connector = connectors.get(self.config.connector) if isinstance(connectors, dict) else None
        if connector is None:
            raise ExecutionError(
                f"Connector '{self.config.connector}' not found in flow_vars['connectors']",
                details={"connector": self.config.connector},
            )

        request = {
            "path": resolve_templates(self.config.path, ctx.flow_vars),
            "body": resolve_templates(self.config.body_template, ctx.flow_vars),
            "params": resolve_templates(self.config.params, ctx.flow_vars),
        }
        try:
            return await connector.execute(self.config.method, request)
        except Exception as exc:
            raise ExecutionError(
                f"HTTP request step failed for connector '{self.config.connector}'",
                details={"connector": self.config.connector, "method": self.config.method},
            ) from exc
