"""Tests for LLM call step."""

import os
from typing import Any

import pytest

from navbe.core.config import get_settings
from navbe.core.exceptions import ExecutionError
from navbe.domains.steps.implementations.llm_call import LLMCallStep
from navbe.domains.steps.interfaces import StepContext


class FakeLLMClient:
    """Fake LLM client that records prompts and returns canned text."""

    def __init__(self, response: str) -> None:
        """Create a fake with a fixed response."""
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def complete(self, *, prompt: str, model: str) -> str:
        """Record the request and return canned text."""
        self.calls.append({"prompt": prompt, "model": model})
        return self.response


async def test_prompt_template_resolved_before_call() -> None:
    """Prompt placeholders are resolved before client invocation."""
    client = FakeLLMClient("done")
    step = LLMCallStep({"prompt_template": "Hello {{flow_vars.name}}"}, client=client)

    await step.run(StepContext(node_id="n1", input_data=None, flow_vars={"name": "Ada"}))

    assert client.calls == [{"prompt": "Hello Ada", "model": "claude-sonnet-4-6"}]


async def test_structured_output_parsed_against_schema() -> None:
    """Raw JSON text is parsed and lightly validated against schema."""
    schema = {
        "type": "object",
        "required": ["answer"],
        "properties": {"answer": {"type": "string"}},
    }
    step = LLMCallStep(
        {"prompt_template": "Answer", "output_schema": schema},
        client=FakeLLMClient('{"answer": "yes"}'),
    )

    assert await step.run(StepContext(node_id="n1", input_data=None)) == {"answer": "yes"}


async def test_malformed_structured_output_raises_execution_error() -> None:
    """Invalid JSON raises ExecutionError when structured output is expected."""
    step = LLMCallStep(
        {"prompt_template": "Answer", "output_schema": {"type": "object"}},
        client=FakeLLMClient("{nope"),
    )

    with pytest.raises(ExecutionError):
        await step.run(StepContext(node_id="n1", input_data=None))


async def test_no_output_schema_returns_raw_text() -> None:
    """Without output_schema, raw client text is returned."""
    step = LLMCallStep({"prompt_template": "Say hi"}, client=FakeLLMClient("hi"))
    assert await step.run(StepContext(node_id="n1", input_data=None)) == "hi"


@pytest.mark.integration
async def test_real_anthropic_call_requires_api_key() -> None:
    """Real network smoke test, skipped unless NAVBE_ANTHROPIC_API_KEY is set."""
    if not os.getenv("NAVBE_ANTHROPIC_API_KEY"):
        pytest.skip("NAVBE_ANTHROPIC_API_KEY is not set")

    get_settings.cache_clear()
    step = LLMCallStep({"prompt_template": "Reply with exactly: navbe-ok"})
    result = await step.run(StepContext(node_id="n1", input_data=None))

    assert isinstance(result, str)
    assert result.strip()
