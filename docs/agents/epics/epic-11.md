# EPIC 11 — Local Credentials Store

**Status:** done  
**Goal:** Manage external auth (API keys, tokens) via a local JSON credentials store — Cursor-style — instead of requiring everything in `.env`. Agents set/list/delete credentials over MCP; `{"$secret": "KEY"}` resolution prefers the store, then falls back to env.  
**Non-goal:** Cloud vaults (1Password/Vault); OAuth browser flows; encrypting the JSON file beyond OS file permissions (v0.1); returning secret **values** over MCP/API; GitHub sync (EPIC 12).

## Why

Today secrets only resolve from process env / `.env` (EPIC 3). Agents and Claude Desktop users must edit env files outside Navbe. Cursor stores MCP credentials in a local machine store; Navbe should offer the same ergonomics: a file under the user’s Navbe data dir, managed by a service + thin MCP tools, never echoed in tool responses.

## Design

### Storage (Cursor-like)

| Item | Choice |
| --- | --- |
| Path | `NAVBE_CREDENTIALS_PATH` (default `./navbe_credentials.json`) |
| Format | JSON object: `{ "RESEND_API_KEY": "…", "GITHUB_TOKEN": "…" }` — flat key → string value |
| Git | Must be gitignored (like `.env`) |
| Permissions | Create file `0600` when writing (Unix); best-effort on Windows |
| Scope | Global per Navbe process / working directory — not per-flow (ponytail). Optional later: namespaced keys `connector.resend.api_key` |

### Resolution chain

`SecretsProvider` chain (first hit wins):

1. **JsonFileSecretsProvider** — read `navbe_credentials.json`
2. **EnvSecretsProvider** — existing env / `.env` (unchanged)

`{"$secret": "KEY"}` in FlowSpecs stays the only in-spec shape. No plaintext keys in flow JSON.

### “Auth per tools”

v0.1 interpretation (lazy): credentials are **named keys** that any connector/MCP consumer resolves via `$secret`. “Per tool” = agents use conventional key names documented per connector (e.g. `RESEND_API_KEY`, `NAVBE_ANTHROPIC_API_KEY`, `GITHUB_TOKEN`).  

**Not in this epic:** a separate OAuth session table per MCP tool name. Upgrade path: namespaced keys or a `CredentialRecord { tool, kind, fields }` schema — mark with `ponytail` if deferred.

### Domain

Prefer **extending** `domains/secrets/` (EPIC 3 already reserved `SecretsProvider` as the swap seam). No new top-level domain unless the JSON store grows past a single provider file.

| File | Role |
| --- | --- |
| `interfaces.py` | Keep `SecretsProvider`; add optional `SecretsStore` Protocol (`set` / `delete` / `list_keys`) |
| `json_file.py` (new) | File-backed provider + store |
| `service.py` | `set` / `delete` / `list_keys` + existing `resolve_*`; compose chain |
| `models.py` | Optional `CredentialKey` validation (safe key pattern) |

### MCP tools (underscored)

| Tool | Behavior |
| --- | --- |
| `secret_set` | `{ "key": str, "value": str }` → write to JSON; return `{ "key", "stored": true }` — **never** echo value |
| `secret_list` | Return `{ "keys": [...] }` only |
| `secret_delete` | Remove key; `{ "key", "deleted": true\|false }` |
| `secret_has` | `{ "key" }` → `{ "key", "present": bool }` (checks store then env, no value) |

REST mirrors under `/api/v1/secrets` (same no-value rule) for parity with flows.

### Security (hard rules)

- Never log or return resolved values from MCP/API/tool errors.
- `secret_list` / `secret_has` only.
- Reject empty keys; key pattern: `^[A-Z][A-Z0-9_]*$` (env-style) — ponytail ceiling: no nested JSON secrets yet.
- Guide/skill: prefer `secret_set` over editing `.env` for agent-operated keys.

## In scope

- `JsonFileSecretsProvider` + chain with env fallback
- Settings: `credentials_path`
- MCP + REST secret management tools/routes
- `.gitignore` + `.env.example` notes
- Unit tests with temp files (no real secrets in fixtures)
- Update `navbe_howto` / Claude skill to mention `secret_set`

## Out of scope

- Encrypting `navbe_credentials.json` at rest
- OAuth device/code flows
- Syncing credentials to GitHub (never)
- Renaming existing `$secret` ref shape
- EPIC 12 GitHub sync

## Tasks

### T1 — Settings + gitignore

- Add `credentials_path: Path = Path("./navbe_credentials.json")` to Settings.
- Gitignore `navbe_credentials.json` and `*.credentials.json`.
- Document in `.env.example`.

**Verify:** settings unit test + gitignore present.

### T2 — JSON provider + store + chain

- Implement file read/write (atomic write: temp + replace).
- `ChainedSecretsProvider([json, env])` or service-level fallback.
- Unit tests: set → resolve via `$secret` walk; missing key → NotFoundError with key name only; list never includes values.

**Verify:** `uv run pytest tests/unit/domains/secrets -q`

### T3 — Wire DI

- `dependencies.py`: build chained provider; inject into `SecretsService`.
- Existing connector resolution keeps working with env-only if file absent.

**Verify:** `uv run pytest tests/unit/domains/connectors tests/integration/test_secrets_standalone.py -q`

### T4 — MCP + REST

- Tools `secret_set` / `secret_list` / `secret_delete` / `secret_has`.
- REST thin mirrors.
- Error handler: never put value in `details`.

**Verify:** `uv run pytest tests/unit/mcp_app tests/unit/api -q` (new secret route tests)

### T5 — Docs / guide / skill

- Update `navbe_howto`, Claude `navbe-flows` skill, `connect_agents.md`, architecture secrets paragraph.
- Rebuild Claude zips if skill text changes (`claude-plugin/build_zips.py`).

**Verify:** docs mention store path + MCP tools; guide string contains `secret_set`.

## Definition of Done

- [x] Credentials file path configurable; default gitignored
- [x] `$secret` resolves from JSON file first, then env
- [x] MCP `secret_set` / `secret_list` / `secret_delete` / `secret_has` green; values never returned
- [x] REST parity for the same operations
- [x] Env-only setups still work with no credentials file
- [x] `uv run ruff check .` / `ty check src/` / `lint-imports` / relevant pytest green
- [x] Agent docs + howto/skill updated

## Notes

- ponytail: plaintext JSON on disk — upgrade: OS keychain / age encryption.
- ponytail: flat string map — upgrade: per-connector structured auth records.
- Follows AGENTS.md: secrets domain owns storage; never echo values in MCP responses.
