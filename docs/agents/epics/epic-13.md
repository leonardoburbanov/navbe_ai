# EPIC 13 — Human CLI (ops console)

**Status:** done  
**Goal:** Terminal CLI for humans to manage credentials, GitHub flow sync, run history/live watch, and step catalog — without a web UI.  
**Non-goal:** Flow authoring in CLI; starting runs from CLI (v0.1); Textual TUI; duplicating domain logic.

## Depends on

- EPIC 11 — `navbe secret` → credentials store
- EPIC 12 — `navbe sync` → GitHub flows mirror
- EPIC 5/6/7 — runs + catalog services

## Command surface

```
uv run navbe --help
uv run navbe secret set|list|delete|has
uv run navbe sync configure|init|status|branch create|checkout|push|pull
uv run navbe runs list|status|watch
uv run navbe steps [show]
uv run navbe serve [--host] [--port]
```

Agents keep using `navbe-mcp`.

## Design

- Package: `src/navbe/cli/` — Click + Rich; calls `dependencies.py` singletons.
- Entrypoint: `navbe = navbe.cli.main:main`; HTTP server moved to `navbe serve`.
- Import layer: `navbe.cli` with `mcp_app | api` above domains.

## Definition of Done

- [x] `uv run navbe` is the human CLI; `navbe serve` runs API; `navbe-mcp` unchanged
- [x] Secret set/list/delete/has; values never printed
- [x] Sync subcommands for configure/init/status/branch/checkout/push/pull
- [x] Runs history + status + live watch until terminal state
- [x] Steps list/show from catalog
- [x] Unit tests + ruff / ty / lint-imports green
- [x] Docs updated
