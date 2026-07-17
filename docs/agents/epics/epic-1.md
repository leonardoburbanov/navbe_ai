# EPIC 1 — Steps Domain

**Status:** done  
**Goal:** Build standalone step types with direct `StepContext` execution.  
**Non-goal:** No Flow, execution engine, HTTP API, or MCP tools.

## Delivered

| Area | Location |
| --- | --- |
| Step contracts | `src/navbe/domains/steps/interfaces.py` |
| Config base | `src/navbe/domains/steps/models.py` |
| Step registry | `src/navbe/domains/steps/registry.py` |
| Built-in implementations | `src/navbe/domains/steps/implementations/` |
| Step service | `src/navbe/domains/steps/service.py` |
| Standalone integration proof | `tests/integration/test_steps_standalone.py` |

## Built-in step types

| Step type | Purpose |
| --- | --- |
| `http_request` | Resolve templates and call a connector-like object from `ctx.flow_vars["connectors"]` |
| `set_var` | Extract a value from `ctx.input_data` using JMESPath |
| `transform` | Run DuckDB SQL against one in-memory table named `input` |
| `llm_call` | Resolve prompt templates and call an injectable LLM client |
| `router` | Evaluate a sandboxed `simpleeval.simple_eval` condition into a route |

## Definition of Done

- [x] `uv run pytest tests/unit/domains/steps -v` all green
- [x] `uv run pytest tests/integration/test_steps_standalone.py -v` green
- [x] `uv run pytest -m integration -v` cleanly skips real LLM test without API key
- [x] `uv run ruff check .` → 0 errors
- [x] `uv run ty check src/navbe/domains/steps` → 0 errors
- [x] `uv run lint-imports` → 0 violations
- [x] All five steps registered through `StepRegistry`
- [x] No raw `eval()` in `domains/steps`; router uses `simpleeval.simple_eval`
- [x] No bare `raise ValueError` / `raise Exception` in `domains/steps`

## Notes

- `transform` returns rows via DuckDB cursor metadata instead of `fetch_arrow_table()` to avoid adding `pyarrow`.
- `llm_call` defaults to a tiny `httpx` Anthropic client only when no fake client is injected.
- Connector resolution is intentionally duck-typed; the connectors domain does not exist yet.
