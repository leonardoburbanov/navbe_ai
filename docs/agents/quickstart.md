# Navbe agent quickstart

Start here for project context. Coding rules live in [AGENTS.md](../../AGENTS.md). Wiki scope lives in [INSTRUCTIONS.md](INSTRUCTIONS.md).

## What this is

Local-first workflow orchestration for AI agents (MCP). Control-plane state in SQLite; analytics destinations (DuckDB/CSV) come in later EPICs.

## Bootstrap (EPIC 0)

```bash
uv sync
uv run python -c "import navbe"
uv run ruff check .
uv run ty check src/
uv run lint-imports
uv run pytest
```

Copy [`.env.example`](../../.env.example) to `.env` for local settings (never commit secrets).

## Where code lives

| Path | Role today |
| --- | --- |
| `src/navbe/core/` | Config, async DB engine/session, base exceptions |
| `src/navbe/domains/steps/` | Standalone step contracts, registry, service, implementations |
| `src/navbe/domains/connectors/` | Standalone connector contracts, registry, service, HTTP implementation |
| `src/navbe/domains/` | Other domains arrive in later EPICs |
| `src/navbe/api/` | FastAPI surface (stub) |
| `src/navbe/mcp_app/` | FastMCP surface (stub) |
| `tests/` | Unit + integration; shared fixtures in `conftest.py` |

## Next reads

- [Delivery](delivery.md) — EPIC process and DoD rules
- [EPIC 0](epics/epic-0.md) — bootstrap status
- [EPIC 1](epics/epic-1.md) — steps domain status
- [EPIC 2](epics/epic-2.md) — connectors domain status
- [Architecture](architecture.md) — layers and domain pattern
- [Operations](operations.md) — commands and CI
