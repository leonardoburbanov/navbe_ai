# EPIC 12 — GitHub Sync & Branching

**Status:** done  
**Goal:** Sync Navbe flow definitions with a GitHub repository (`flows/<flow_id>/flow.json` only), including create/checkout branch, push, and pull.  
**Non-goal:** Syncing Python step/connector **source code**; SQLite run history; credentials; archives by default; full Git UI; GitHub Actions hosting.

## Why

Flows lived only under `NAVBE_FLOWS_DIR`. Agents and humans need GitHub as the remote of truth for flow specs, with branch workflows.

## Depends on

- **EPIC 11** — `GITHUB_TOKEN` (or `GH_TOKEN`) via `secret_set`.

## What syncs

| Asset | v0.1 | Notes |
| --- | --- | --- |
| Flow specs | Yes | `flows/<flow_id>/flow.json` only |
| Archives (`flow.vN.json`) | No | Excluded on push/pull |
| Runs | No | Local only |
| Credentials | **Never** | |
| Step/connector Python | No | |

## Design (shipped)

- Domain: `src/navbe/domains/sync/` — `SyncService` + `GitSubprocessRemote` (subprocess `git`, token via in-process `http.extraHeader` only).
- Config: `./navbe_sync.json` (`NAVBE_SYNC_CONFIG_PATH` / settings `sync_config_path`) — no tokens.
- Clone: `./navbe_sync_repo` (gitignored). Layout inside clone: `flows/<flow_id>/flow.json`.
- Pull: ff-only; upsert into `FileSystemFlowRepository`; remove local flows absent on remote.
- Push: copy only `flow.json` into clone `flows/`; `git add` scoped to `flows_subdir`.

### MCP tools

`sync_configure`, `sync_init`, `sync_status`, `sync_branch_create`, `sync_checkout`, `sync_push`, `sync_pull`

### REST

`/api/v1/sync/*` mirrors the tools.

## Definition of Done

- [x] Configure remote + init clone with token from credentials store
- [x] Create/checkout branch; push local flows; pull ff-only into Navbe
- [x] Dirty working tree → structured ValidationError (no silent overwrite)
- [x] MCP tools registered (underscored); no token in responses
- [x] Credentials file and sync clone dir gitignored
- [x] Unit tests + ruff / ty / lint-imports green
- [x] Docs + howto mention sync tools (flows organization only)

## Agent loop

1. `secret_set` → `GITHUB_TOKEN`
2. `sync_configure` → `sync_init`
3. `sync_pull` (or edit locally then `sync_branch_create` → `sync_push`)
4. `flow_list` to confirm

## Notes

- ponytail: subprocess git — upgrade: pygit2 / Contents API.
- ponytail: ff-only pull — upgrade: merge + conflict report.
- Security: sync repo is public-safe — `$secret` refs OK, never resolved values.
