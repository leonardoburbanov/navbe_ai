# EPIC 13 — Human CLI (ops console)

**Status:** done  
**Goal:** Terminal CLI for humans to manage credentials, GitHub flow sync, run history/live watch, and step catalog — without a web UI.  
**Non-goal:** Flow authoring in CLI; starting runs from CLI (v0.1); Textual TUI; duplicating domain logic; Windows desktop app.

## Depends on

- EPIC 11 — `navbe secret` → credentials store
- EPIC 12 — `navbe sync` → GitHub flows mirror
- EPIC 5/6/7 — runs + catalog services

## Command surface

```
navbe --help
navbe setup                         # first-run onboarding
navbe info [--json]                 # paths, credentials readiness, sync
navbe login [--status]              # recommended key presence
navbe mcp show|configure            # MCP snippet / write Cursor & Claude configs
navbe secret set|list|delete|has
navbe sync configure|init|status|branch create|checkout|push|pull
navbe flows|runs|steps …
navbe serve [--host] [--port]
```

From a checkout: prefix with `uv run`. Agents keep using `navbe-mcp`.

End-user install (no clone): [../../install.md](../../install.md).

## Design

- Package: `src/navbe/cli/` — Typer + Rich; calls `dependencies.py` singletons.
- Entrypoint: `navbe = navbe.cli.main:main`; HTTP server is `navbe serve`.
- MCP stdio: `navbe-mcp = navbe.mcp_stdio:main`.
- Import layer: `navbe.cli` with `mcp_app | api` above domains.
- Data home: checkout root vs `~/.navbe` — `navbe.core.paths`.

## Distribution (follow-on)

- `scripts/install.sh` / `scripts/install.ps1` → `uv tool install` from git
- Tag `v*` → [`.github/workflows/release.yml`](../../../.github/workflows/release.yml) uploads wheel + install scripts
- Docs hub: [../../install.md](../../install.md)

## Definition of Done

- [x] `navbe` is the human CLI; `navbe serve` runs API; `navbe-mcp` unchanged
- [x] Secret set/list/delete/has; values never printed
- [x] Sync subcommands for configure/init/status/branch/checkout/push/pull
- [x] Runs history + status + live watch until terminal state
- [x] Steps list/show from catalog
- [x] `navbe mcp configure` writes Cursor / Claude Desktop MCP configs
- [x] Install scripts + release workflow for end-user distribution
- [x] Unit tests + ruff / ty / lint-imports green
- [x] Docs updated ([install.md](../../install.md), connect_agents, architecture, operations)
