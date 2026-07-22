# EPIC 14 — GitHub OAuth + Workspace Sync

**Status:** done  
**Goal:** Replace PAT/`GITHUB_TOKEN` sync auth with GitHub Device Flow, and expand sync from flows-only to a pluggable workspace layout (flows now; connectors/destinations/schedules as registered assets later).  
**Non-goal:** Building destinations / schedules / standalone connector-store domains; syncing runs/credentials/archives/Python source; browser localhost OAuth; GitHub App install; new generic secrets UX.

## Why

EPIC 12 mirrored `flows/<id>/flow.json` via `secret_set GITHUB_TOKEN`. Humans and agents need a one-shot GitHub login (device flow) and a workspace-shaped sync contract that grows as new versionable domains land — without ever putting tokens in `secret_set` for sync.

## Depends on

- **EPIC 12** — sync domain + `sync_*` MCP/CLI/REST
- **EPIC 13** — human CLI (`navbe login`, setup, onboarding)

## What syncs

| Asset | v0.1 (this epic) | Notes |
| --- | --- | --- |
| Flow specs | Yes | `flows/<flow_id>/flow.json` via `FlowsAsset` |
| Connectors | Reserved | Layout `connectors/<id>/connector.json` when a store exists |
| Destinations | Reserved | Layout `destinations/<id>/destination.json` when a store exists |
| Schedules | Reserved | Layout `schedules/<id>/schedule.json` when a store exists |
| Archives / runs | No | Local only |
| Credentials / OAuth tokens | **Never** | |

Connectors embedded in `FlowSpec.connectors` already travel with flow.json.

## Design

### Auth (Device Flow)

- Module: `domains/sync/github_auth.py` + managed token file `navbe_github_oauth.json` (gitignored).
- Public OAuth App `client_id` via `NAVBE_GITHUB_OAUTH_CLIENT_ID` (settings); no client secret for device flow.
- CLI: `navbe login github` / `--status` / `navbe logout github`
- MCP: `auth_github_begin` / `auth_github_complete` / `auth_github_status` / `auth_github_logout`
- `SyncService` resolves token **only** from the OAuth store — no `GITHUB_TOKEN` / `GH_TOKEN` / `token_secret_key`.

### Easy repo bind

- `sync_connect(owner, name, *, private=True)` — create repo via GitHub API if missing, configure, init clone.
- `sync_configure(remote_url=...)` still binds an existing remote.

### Workspace assets

- `WorkspaceAsset` Protocol: `subdir`, `list_local_ids()`, `export_to(clone_root)`, `import_from(clone_root)`.
- Push/pull iterates registered assets; EPIC 14 registers **only** `FlowsAsset`.
- Default commit message: `navbe: sync workspace`.

## Tasks

1. OAuth device flow + token store; wire CLI/MCP; gitignore oauth file.
2. Point `SyncService` at OAuth store; remove PAT path from sync.
3. Add `sync_connect` (CLI + MCP + REST).
4. Add `WorkspaceAsset` + `FlowsAsset`; refactor push/pull.
5. Update howto / onboarding / architecture / operations; guards green.

## Acceptance

```bash
uv run ruff check .
uv run ty check src/
uv run lint-imports
uv run pytest tests/unit/domains/sync -q
uv run pytest -q
```

## Definition of Done

- [x] Device login stores a managed token; sync works without `secret_set GITHUB_TOKEN`
- [x] `navbe login github` and MCP auth tools work; token never echoed
- [x] `sync_connect` can create/bind a repo and init clone
- [x] Push/pull use WorkspaceAsset list (flows registered); layout documented for connectors/destinations/schedules
- [x] PAT/`token_secret_key` removed from sync path and docs
- [x] Guards green

## Agent loop

1. `auth_github_begin` → show user the code → `auth_github_complete`
2. `sync_connect` (or `sync_configure` + `sync_init`)
3. `sync_pull` / edit / `sync_branch_create` → `sync_push`
4. `flow_list` to confirm

## Notes

- ponytail: subprocess git — upgrade: pygit2 / Contents API.
- ponytail: ff-only pull — upgrade: merge + conflict report.
- Security: workspace repo is public-safe — `$secret` refs OK, never resolved values. OAuth token never in MCP/CLI responses.
