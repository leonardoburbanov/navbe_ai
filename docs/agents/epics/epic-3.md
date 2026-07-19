# EPIC 3 — Secrets Domain

**Status:** done  
**Goal:** Resolve `{"$secret": "KEY"}` refs from connector configs via local env/.env.  
**Non-goal:** No vault, no encryption at rest, no MCP tools.

## Delivered

| Area | Location |
| --- | --- |
| Secret ref models | `src/navbe/domains/secrets/models.py` |
| Provider Protocol | `src/navbe/domains/secrets/interfaces.py` |
| Env provider + service | `src/navbe/domains/secrets/service.py` |
| Connector wiring | `src/navbe/domains/connectors/service.py` → `SecretsService.resolve_config` |
| Standalone integration | `tests/integration/test_secrets_standalone.py` |

## Definition of Done

- [x] `uv run pytest tests/unit/domains/secrets -v` all green
- [x] `uv run pytest tests/unit/domains/connectors/test_service.py -v` with real SecretsService
- [x] `uv run pytest tests/integration/test_secrets_standalone.py -v` green
- [x] `uv run ruff check .` → 0 errors
- [x] `uv run ty check src/navbe/domains/secrets` → 0 errors
- [x] `uv run lint-imports` → 0 violations
- [x] Missing-secret `NotFoundError` exposes key name + hint only (never resolved values)
- [x] `.env.example` documents `$secret` ref pattern

## Notes

- `SecretsProvider` is the swap seam for a future Vault/1Password backend.
- `connectors` depends on `secrets` (leaf); secrets never imports connectors/steps/flows.
