# EPIC 2 — Connectors Domain

**Status:** done  
**Goal:** Standalone connectors wrapping external systems (auth, connection, actions).  
**Non-goal:** No Flow, execution engine, steps wiring, or secrets domain implementation.

## Delivered

| Area | Location |
| --- | --- |
| Connector contracts | `src/navbe/domains/connectors/interfaces.py` |
| Flow reference model | `src/navbe/domains/connectors/models.py` |
| Connector registry | `src/navbe/domains/connectors/registry.py` |
| HTTP connector | `src/navbe/domains/connectors/implementations/http.py` |
| Connector service | `src/navbe/domains/connectors/service.py` |
| Standalone integration proof | `tests/integration/test_connectors_standalone.py` |

## Built-in connector types

| Type | Purpose |
| --- | --- |
| `http` | GET/POST/PUT/DELETE against a configured `base_url` via httpx |

## Definition of Done

- [x] `uv run pytest tests/unit/domains/connectors -v` all green
- [x] `uv run pytest tests/integration/test_connectors_standalone.py -v` green
- [x] `uv run ruff check .` → 0 errors
- [x] `uv run ty check src/navbe/domains/connectors` → 0 errors
- [x] `uv run lint-imports` → 0 violations
- [x] `HTTPConnector` registered via `ConnectorRegistry`
- [x] No bare `raise ValueError` / `raise Exception` in `domains/connectors/`
- [x] `httpx.HTTPStatusError` / `httpx.HTTPError` wrapped as `ExecutionError` in `execute()`

## Notes

- `ConnectorService._resolve_secrets` accepts an injected duck-typed `secrets_service`; real secrets domain wiring lands in EPIC 3.
- `test_connection()` returns `False` on network errors instead of raising.
- Steps consume connectors later via `ctx.flow_vars["connectors"][name]` — not wired in this EPIC.
