# EPIC 5 — Execution Domain

**Status:** done  
**Goal:** Compile FlowSpec → LangGraph StateGraph, run with SQLite checkpoints, traces/transcripts, HITL pause/resume.  
**Non-goal:** No MCP tools (EPIC 7); execution is triggered via `RunService` / engine directly.

## Delivered

| Area | Location |
| --- | --- |
| Models | `src/navbe/domains/execution/models.py` |
| Protocols | `src/navbe/domains/execution/interfaces.py` |
| Graph compiler | `src/navbe/domains/execution/graph_compiler.py` |
| LangGraph engine | `src/navbe/domains/execution/engine.py` |
| Run repository | `src/navbe/domains/execution/repository.py` |
| Run service | `src/navbe/domains/execution/service.py` |
| HITL approval | reserved `approval` step_type in compiler (`interrupt` / `Command(resume=…)`) |
| Standalone integration | `tests/integration/test_execution_standalone.py` |

## Definition of Done

- [x] `uv run pytest tests/unit/domains/execution -v` all green
- [x] `uv run pytest tests/integration/test_execution_standalone.py -v` green
- [x] `uv run ruff check .` → 0 errors
- [x] `uv run ty check src/navbe/domains/execution` → 0 errors
- [x] `uv run lint-imports` → 0 violations
- [x] Router `node_outputs[x]["route"]` convention matches RouterStep
- [x] HITL pause / resume (`approved=True` / `False`) works
- [x] `transcript.md` generated after runs
- [x] Failures surface as `NavbeError` subclasses (no bare leaks from `RunService`)

## Notes

- `execution/` may import `flows/`, `steps/`, `connectors/`, `secrets/`; nothing imports *from* `execution/` except future `mcp_app/` / `api/`.
- Live connector instances are closed over at compile time (not stored in LangGraph state) so `AsyncSqliteSaver` msgpack does not choke on `HTTPConnector`.
- `approval` is compiler-reserved — not registered in `StepRegistry`.
- `ExecutionEngine.list_runs` is on the Protocol (no `hasattr` workaround).
