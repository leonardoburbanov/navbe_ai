# Delivery process (project manager logic)

How Navbe ships work. Coding rules stay in [AGENTS.md](../../AGENTS.md). Epic status lives under [epics/](epics/).

## EPIC model

An **EPIC** is a vertical slice with:

1. Clear **in / out of scope**
2. Numbered **tasks** with exact acceptance commands (not vibes)
3. A binary **Definition of Done** — all boxes must pass before the next EPIC

Do not start EPIC *N+1* until EPIC *N* DoD is green.

## Agent workflow per EPIC

1. Read the epic page under `docs/agents/epics/` (or the user’s task brief).
2. Implement only what that epic allows (e.g. EPIC 0: no domain logic).
3. Run every acceptance command locally; fix until exit code 0.
4. Update the matching `docs/agents/` pages so they match merged code.
5. Commit / push only when the user asks.

## Task shape (preferred)

Each task should specify:

- **Files / structure** to create or change
- **Exact commands** to verify (e.g. `uv run pytest tests/unit/core/test_config.py -v`)
- **Non-goals** (what not to build yet)

## Guards (always leave green)

```bash
uv sync
uv run ruff check .
uv run ty check src/
uv run lint-imports
uv run pytest
```

CI runs the same sequence — see [operations.md](operations.md).

## Docs ownership

| Artifact | Owner | When to change |
| --- | --- | --- |
| [AGENTS.md](../../AGENTS.md) | Human + agent (rules only) | Coding rules / boundaries change |
| [INSTRUCTIONS.md](INSTRUCTIONS.md) | Human | Wiki scope / priorities change |
| Topic pages (`architecture`, `operations`, …) | Agent with PR | Behavior in that area lands |
| `epics/epic-N.md` | Agent with PR | Epic starts, finishes, or DoD changes |

Prefer code as source of truth. No speculative docs for packages that do not exist yet.

## Current epic index

- [EPIC 0 — Bootstrap](epics/epic-0.md) — done (installable project, core, CI)
- [EPIC 1 — Steps Domain](epics/epic-1.md) — done (standalone step implementations)
- [EPIC 2 — Connectors Domain](epics/epic-2.md) — done (standalone HTTP connector)
- [EPIC 3 — Secrets Domain](epics/epic-3.md) — done (env-backed secret refs)
- [EPIC 4 — Flows Domain](epics/epic-4.md) — done (FlowSpec validate + persist)
- [EPIC 5 — Execution Domain](epics/epic-5.md) — done (LangGraph run + HITL)
- [EPIC 6 — Catalog Domain](epics/epic-6.md) — done (agent-facing step/connector schemas)
- [EPIC 7 — MCP App](epics/epic-7.md) — done (FastMCP tools + catalog resources)
- [EPIC 8 — FastAPI Wiring](epics/epic-8.md) — done (dependencies + REST + MCP mount)
- [EPIC 9 — E2E Demo + Clients](epics/epic-9.md) — done (stdio entrypoint + dual-client docs)
- [EPIC 10 — MCP Discovery Parity](epics/epic-10.md) — done (list/get/update flows + catalog tool mirrors + `navbe://flows`)
- See also [../connect_agents.md](../connect_agents.md) for Claude Desktop / Cursor setup
