# EPIC 16 — Per-app credentials (masked preview + rotate)

**Status:** done  
**Goal:** Manage API keys for any external app via CLI/MCP with optional `app` label, masked last-4 preview, and overwrite/rotate — machine-local store only (no multi-user identity).  
**Non-goal:** Multi-user accounts; GitHub-login tagging; encrypting credentials; remote key minting; changing `$secret` shape; syncing credentials; new connector types.

## Why

EPIC 11 shipped a flat credentials JSON map with set/list/delete/has, but list returns keys only. Operators and agents cannot confirm *which* key is stored (e.g. Resend) without guessing. Per-app labels and masked suffixes make rotate/overwrite safe without echoing full values.

## Design

### Identity / scope

Machine-local: one Navbe data dir = one operator. No Navbe user accounts. Env remains resolve fallback only; management UX targets the JSON file.

### Storage (backward compatible)

Same path (`NAVBE_CREDENTIALS_PATH`). Entries may be:

- Legacy string: `"RESEND_API_KEY": "re_…"`
- Record (new writes): `{ "value": "…", "app": "resend", "updated_at": "…" }`

Reader normalizes both to `CredentialRecord`. Writer persists the record shape. `$secret` resolution uses the string value.

### Masking

Hint = `****` + last 4 chars. Values shorter than 4 → `****` only (no short-secret leak). Hints only from the JSON store. Env-only: `has=true`, `hint=null`, `source="env"`.

### App label

Optional slug `^[a-z][a-z0-9_-]*$` on set. If omitted on rotate, preserve existing `app`. Convention: `RESEND_API_KEY` + `app="resend"` (docs only).

### MCP

| Tool | Behavior |
| --- | --- |
| `secret_set` | Optional `app`; return `{key, stored, hint, app}` — never full value |
| `secret_list` | `{keys: [...], items: [...]}` — `keys` kept for compatibility |
| `secret_hint` | Single-key masked inspect |
| `secret_delete` / `secret_has` | Unchanged |

### CLI / REST

Parity with MCP: `navbe secret set KEY [--app …]`, `list` table, `hint KEY`; REST mirrors including `GET /{key}/hint` and optional `app` on PUT.

## In scope

- `CredentialRecord`, `mask_secret`, app validation
- JSON store legacy ↔ record
- Service `set(app=)`, `list_credentials`, `get_hint`
- MCP / REST / CLI surfaces
- Epic index + howto / architecture note

## Out of scope

- Encrypting `navbe_credentials.json`
- Multi-user / tenant / GitHub-login association
- Calling providers to mint keys
- Renaming `$secret` refs
- Syncing credentials (never)

## Tasks

### T1 — Models + mask

- `CredentialRecord`, `CredentialHint`, `mask_secret`, `validate_app` in `domains/secrets/models.py`.

**Verify:** `uv run pytest tests/unit/domains/secrets/test_models.py -q`

### T2 — JSON store

- Normalize string | record on read; write records; preserve `app` on rotate when omitted.

**Verify:** `uv run pytest tests/unit/domains/secrets/test_json_file.py -q`

### T3 — Service

- `set(..., app=)`, `list_credentials()`, `get_hint(key)`.

**Verify:** `uv run pytest tests/unit/domains/secrets -q`

### T4 — MCP + REST + CLI

- Thin surfaces; fakes updated for new methods.

**Verify:** `uv run pytest tests/unit/mcp_app/test_tools_secret.py tests/unit/api/test_secrets_routes.py tests/unit/cli/test_secret.py -q`

### T5 — Docs

- Index in `delivery.md`; update howto + architecture secrets paragraph.

**Verify:** guide mentions `secret_hint` / masked preview; epic DoD checked.

## Definition of Done

- [x] Set key via CLI/MCP with `app=resend`; list shows `****` + last 4
- [x] Rotate (set again) updates hint; full value never in responses
- [x] Legacy flat JSON still resolves for flows
- [x] Env-only key: `has` true, no hint from env value
- [x] `uv run ruff check .` / `ty check src/` / `lint-imports` / `pytest` green
- [x] Agent docs + howto updated

## Notes

- Values never returned over MCP/API/CLI.
- `secret_list` keeps `keys` for agents that already depend on it; `items` is additive.
