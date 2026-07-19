# EPIC 6 — Catalog Domain

**Status:** done  
**Goal:** Read-only JSON Schema catalog over StepRegistry + ConnectorRegistry for agents authoring FlowSpecs.  
**Non-goal:** No MCP tools (EPIC 7); no persistence; no models/interfaces/repository.

## Delivered

| Area | Location |
| --- | --- |
| Service | `src/navbe/domains/catalog/service.py` |
| Synthetic HITL step | `approval` merged into steps catalog (not in StepRegistry) |
| Validator patch | `RESERVED_STEP_TYPES` in `flows/validator.py` |
| Standalone integration | `tests/integration/test_catalog_standalone.py` |

## Definition of Done

- [x] `uv run pytest tests/unit/domains/catalog -v` all green
- [x] `uv run pytest tests/integration/test_catalog_standalone.py -v` green
- [x] `flows/validator.py` accepts `approval`; flows unit tests green
- [x] `uv run ruff check .` → 0 errors
- [x] `uv run ty check src/navbe/domains/catalog` → 0 errors
- [x] `uv run lint-imports` → 0 violations
- [x] Catalog schemas JSON-serializable (`json.dumps` round-trip)

## Notes

- Single-file domain: no `models.py` / `interfaces.py` / repository.
- `catalog/` may import registries from `steps/` and `connectors/` only — never `implementations/`.
- Nothing imports *from* `catalog/` except future `mcp_app/` / `api/`.
