"""LLM call step implementation."""

import json
from typing import Any, Protocol

import httpx

from navbe.core.exceptions import ExecutionError, NotFoundError
from navbe.domains.steps.implementations.http_request import resolve_templates
from navbe.domains.steps.interfaces import StepContext
from navbe.domains.steps.models import StepConfig
from navbe.domains.steps.registry import StepRegistry

_ANTHROPIC_SECRET_KEY = "NAVBE_ANTHROPIC_API_KEY"


class LLMClient(Protocol):
    """Minimal async LLM client contract for this step."""

    async def complete(self, *, prompt: str, model: str) -> str:
        """Return a text completion for ``prompt``."""
        ...


class SecretResolver(Protocol):
    """Minimal secrets lookup used by ``AnthropicClient``."""

    async def resolve_ref(self, key: str) -> str:
        """Return the plaintext value for ``key``."""
        ...


class AnthropicClient:
    """Anthropic Messages API client; API key from the credentials JSON store."""

    def __init__(self, secrets: SecretResolver) -> None:
        """Bind a secrets resolver (credentials file only — never env)."""
        self._secrets = secrets

    async def complete(self, *, prompt: str, model: str) -> str:
        """Call Anthropic and return the first text block."""
        try:
            api_key = await self._secrets.resolve_ref(_ANTHROPIC_SECRET_KEY)
        except NotFoundError as exc:
            raise ExecutionError(
                f"{_ANTHROPIC_SECRET_KEY} not found in credentials store",
                details={
                    "key": _ANTHROPIC_SECRET_KEY,
                    "hint": "navbe secret set NAVBE_ANTHROPIC_API_KEY",
                },
            ) from exc

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            payload = response.json()

        for block in payload.get("content", []):
            if block.get("type") == "text":
                return str(block.get("text", ""))
        raise ExecutionError("Anthropic response did not include text content")


class LLMCallConfig(StepConfig):
    """Configuration for an LLM prompt call."""

    prompt_template: str
    output_schema: dict[str, Any] | None = None
    model: str = "claude-sonnet-4-6"


def _check_json_schema_type(name: str, value: Any, schema: dict[str, Any]) -> None:
    """Validate the small JSON-schema subset needed by step tests."""
    expected = schema.get("type")
    checks = {
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, int | float) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
    }
    if expected in checks and not checks[expected]:
        raise ExecutionError(
            f"Structured LLM output field '{name}' did not match schema",
            details={"field": name, "expected": expected},
        )


def _parse_structured_output(raw_text: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Parse and lightly validate JSON object output."""
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ExecutionError("LLM returned malformed JSON", details={"raw": raw_text}) from exc

    if not isinstance(parsed, dict):
        raise ExecutionError("LLM structured output must be a JSON object")

    for field in schema.get("required", []):
        if field not in parsed:
            raise ExecutionError(
                f"LLM structured output missing required field '{field}'",
                details={"field": field},
            )

    properties = schema.get("properties", {})
    if isinstance(properties, dict):
        for field, field_schema in properties.items():
            if field in parsed and isinstance(field_schema, dict):
                _check_json_schema_type(field, parsed[field], field_schema)

    return parsed


@StepRegistry.register("llm_call")
class LLMCallStep:
    """Call an LLM with a resolved prompt template."""

    config_schema = LLMCallConfig

    def __init__(self, config: dict[str, Any], client: LLMClient | None = None) -> None:
        """Validate config and store an injectable client.

        Production wires ``AnthropicClient(secrets_provider)`` via the engine.
        Unit tests inject a fake ``LLMClient``.
        """
        self.config = LLMCallConfig.model_validate(config)
        if client is None:
            raise ExecutionError(
                "llm_call requires an injected LLM client",
                details={"hint": "wire AnthropicClient with the credentials store"},
            )
        self._client = client

    async def run(self, ctx: StepContext) -> Any:
        """Resolve the prompt and return raw or structured output."""
        prompt = resolve_templates(self.config.prompt_template, ctx.flow_vars)
        try:
            raw_text = await self._client.complete(prompt=prompt, model=self.config.model)
        except ExecutionError:
            raise
        except Exception as exc:
            raise ExecutionError("LLM call failed", details={"model": self.config.model}) from exc

        if self.config.output_schema is None:
            return raw_text
        return _parse_structured_output(raw_text, self.config.output_schema)
