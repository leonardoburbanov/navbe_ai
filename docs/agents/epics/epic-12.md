# EPIC 12 — GitHub Sync & Branching

**Status:** planned (starts after EPIC 11 DoD is green — needs `GITHUB_TOKEN` via credentials store)  
**Goal:** Sync Navbe flow definitions (and related local artifacts) with a GitHub repository, including create/checkout branch, push, and pull — so agents can version and collaborate on flows like code.  
**Non-goal:** Syncing Python step/connector **source code** from `domains/`; syncing SQLite run history; syncing credentials; full Git UI; hosting Navbe itself on GitHub Actions as the product.

## Why

Flows today live only under `NAVBE_FLOWS_DIR` (local filesystem + SQLite index). There is no first-class way to share, review, or branch flow JSON. Agents and humans need GitHub as the remote of truth for flow specs, with branch workflows (feature branch → push → PR outside Navbe or later).

## Depends on

- **EPIC 11** — `GITHUB_TOKEN` (or `GH_TOKEN`) stored via `secret_set`, resolved with `$secret` / credentials provider. Do not require token only in `.env` for the happy path.

## What syncs

| Asset | v0.1 | Notes |
| --- | --- | --- |
| Flow specs | Yes | `navbe_flows/<flow_id>/flow.json` (+ optional archived `flow.vN.json` — default **exclude** archives) |
| Flows index (SQLite) | No | Rebuild index on pull via existing repo `save`/`list` scan or re-index helper |
| Run history | No | Local execution state stays local |
| Credentials | **Never** | |
| Built-in step/connector Python | No | Code stays in the Navbe package; catalogs are derived at runtime |
| Optional: exported catalog snapshot | Maybe | `catalog/steps.json` dump for docs — only if cheap; otherwise skip |

“Steps” in the user ask = **nodes inside FlowSpecs**, not shipping `Step` class implementations. Custom user step packs (if ever) would be a later epic.

## Design

### New domain: `sync` (ask-first satisfied by this epic)

```
src/navbe/domains/sync/
  models.py       # SyncRemote, BranchInfo, SyncStatus, SyncResult
  interfaces.py   # GitRemote Protocol (clone/fetch/checkout/commit/push/pull)
  service.py      # use-cases; depends on Protocols + FlowRepository/FlowService
  github.py       # concrete adapter (GitPython or subprocess git — prefer subprocess+gh? )
```

ponytail pick for v0.1: **subprocess `git`** (must be on PATH) + HTTPS remote with token from credentials. Avoid PyGithub for file sync; use git itself. Optional: `gh` CLI only for “open PR” later (out of scope).

### Config

Settings (or a small `navbe_sync.json` next to flows):

| Field | Meaning |
| --- | --- |
| `remote_url` | `https://github.com/org/navbe-flows.git` |
| `local_repo_dir` | Default `./navbe_sync_repo` (working clone; gitignored) |
| `flows_subdir` | Default `flows/` inside the clone (maps to Navbe `flows_dir` content) |
| `default_branch` | `main` |

Auth: remote URL rewritten at runtime to embed token **only in memory** for `git` credential helper / `Authorization` header via `GIT_ASKPASS` or `http.extraHeader` — never write token into `.git/config` on disk.

### Branching model

1. `sync_init` — clone or set remote; verify token with `git ls-remote`
2. `sync_status` — current branch, dirty?, ahead/behind (best-effort)
3. `sync_branch_create` — create + checkout from default branch
4. `sync_checkout` — switch branch (fail if dirty unless `force`/stash — v0.1: fail if dirty)
5. `sync_push` — copy local flows → clone working tree → commit → push current branch
6. `sync_pull` — fetch + merge/rebase (v0.1: **ff-only pull**) → copy into `flows_dir` → refresh SQLite index

Conflict policy v0.1: abort with structured error listing conflicting paths; no auto-merge UI.

### MCP tools

| Tool | Role |
| --- | --- |
| `sync_configure` | Set remote_url / dirs (no token in args — token via `secret_set`) |
| `sync_init` | Clone or bind existing clone |
| `sync_status` | Branch + sync state |
| `sync_branch_create` | `{ name }` |
| `sync_checkout` | `{ branch }` |
| `sync_push` | `{ message? }` — commit local flows and push |
| `sync_pull` | Fast-forward and import into Navbe flows |

All underscored. Never return token. Push/pull results: counts of flows added/updated + commit sha.

### REST

Thin mirrors under `/api/v1/sync/*` matching tools.

## In scope

- `domains/sync` + git subprocess adapter
- Bidirectional sync of flow JSON with branch create/checkout
- MCP + REST tools above
- Gitignore sync clone dir + any sync config that might hold secrets (token never in config file)
- Unit tests with fake `GitRemote` Protocol; one integration test optional behind env flag / marked

## Out of scope

- Opening GitHub PRs automatically
- Syncing run DB, credentials, DuckDB
- Multi-remote / monorepo path mapping beyond one `flows_subdir`
- Rebase/conflict resolution UI
- Hosting step Python modules from the repo

## Tasks

### T1 — Domain skeleton + models

- Package under `domains/sync/` with Protocol + models.
- Import linter: sync may depend on `flows` + `secrets` + `core`; not on `mcp_app`/`api`.

**Verify:** `uv run lint-imports` + empty service unit smoke.

### T2 — Git subprocess adapter

- Implement clone/status/branch/checkout/commit/push/pull against a temp remote in tests (or fake).
- Token injection without persisting secrets.

**Verify:** unit tests with mocked subprocess or local `git init` bare repo.

### T3 — SyncService use-cases

- Map `flows_dir` ↔ clone `flows_subdir`.
- After pull: re-index / load flows into `FileSystemFlowRepository` (add `reindex` or call `save` per file carefully).

**Verify:** `uv run pytest tests/unit/domains/sync -q`

### T4 — MCP + REST + DI

- Register tools; wire settings + credentials for `GITHUB_TOKEN`.
- Update howto/skill: sync loop after `secret_set("GITHUB_TOKEN")`.

**Verify:** mcp unit tests with FakeGitRemote.

### T5 — Docs

- Epic DoD, architecture “sync domain”, connect_agents / howto.
- AGENTS.md: ask-first resolved for `sync` domain; note credentials never synced.

## Definition of Done

- [ ] Configure remote + init clone with token from credentials store
- [ ] Create/checkout branch; push local flows; pull ff-only into Navbe
- [ ] Dirty working tree / conflict → structured NavbeError (no silent overwrite)
- [ ] MCP tools registered (underscored); no token in responses
- [ ] Credentials file and sync clone dir gitignored
- [ ] Unit tests + ruff / ty / lint-imports green
- [ ] Docs + howto mention sync tools

## Suggested agent loop (after)

1. `secret_set` → `GITHUB_TOKEN`
2. `sync_configure` → `sync_init`
3. `flow_list` / edit flows locally
4. `sync_branch_create` → `sync_push`
5. On another machine/agent: `sync_pull` → `flow_list`

## Notes

- ponytail: subprocess git — upgrade: pygit2 / GitHub Contents API for single-file repos.
- ponytail: ff-only pull — upgrade: merge + conflict report with both sides.
- Security: treat the sync repo as **public-safe** — flows may still contain `$secret` refs (OK) but never resolved values.
- Split from EPIC 11 so credentials ship without blocking on git complexity.
