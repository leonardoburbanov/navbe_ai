# EPIC 4 — Flows Domain

**Status:** done  
**Goal:** FlowSpec definition, graph validation, and persistence (filesystem + SQLite index).  
**Non-goal:** No LangGraph execution (EPIC 5), no MCP tools.

## Delivered

| Area | Location |
| --- | --- |
| Models | `src/navbe/domains/flows/models.py` |
| Graph validator | `src/navbe/domains/flows/validator.py` |
| Repository Protocol | `src/navbe/domains/flows/interfaces.py` |
| File + SQLite repo | `src/navbe/domains/flows/repository.py` |
| Service | `src/navbe/domains/flows/service.py` |
| Demo fixture | `tests/fixtures/sales_bot_objection_test.json` |
| Standalone integration | `tests/integration/test_flows_standalone.py` |

## Definition of Done

- [x] `uv run pytest tests/unit/domains/flows -v` all green
- [x] `uv run pytest tests/integration/test_flows_standalone.py -v` green
- [x] `uv run ruff check .` → 0 errors
- [x] `uv run ty check src/navbe/domains/flows` → 0 errors
- [x] `uv run lint-imports` → 0 violations
- [x] Sales-bot demo parses, validates, saves, retrieves
- [x] `update()` archives `flow.v{n}.json` before overwrite
- [x] `EdgeSpec` `from`/`from_` alias round-trips

## Notes

- Cycles are intentionally allowed (router retry loops).
- Validator uses `StepRegistry` for step types; connector refs checked against `flow_spec.connectors`.
- Persistence path: `{flows_dir}/{flow_id}/flow.json` + `flows_index` SQLite table.
