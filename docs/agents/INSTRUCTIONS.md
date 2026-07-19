# Wiki instructions (human-authored)

Scope and priorities for Navbe agent documentation under `docs/agents/`.

Agents **read** this file for guidance on what the wiki should cover. Do **not** rewrite this file unless the user explicitly asks.

## Product scope

Navbe is a local-first workflow orchestration engine operated by AI agents over MCP. Document reality that exists in the repo; do not invent APIs or domain packages that are not merged yet.

## What to document now (EPIC 0+)

- Delivery / EPIC process — [delivery.md](delivery.md) and status under `epics/`
- `core/` — Settings (`NAVBE_` env), SQLAlchemy async engine/session helpers, `NavbeError` hierarchy
- `steps` domain — standalone Step contracts, registry, service, and built-in implementations
- `connectors` domain — standalone Connector contracts, registry, service, HTTP implementation
- `secrets` domain — env-backed `{"$secret": "KEY"}` resolution for connector configs
- Domain package pattern — `models.py` / `interfaces.py` / `service.py` (even before domain folders exist)
- Layering — `.importlinter` contract: `mcp_app` | `api` → `domains` → `core`
- Tooling — `uv`, ruff, ty, pytest, lint-imports, CI workflow
- DuckDB destination caveats (product rules; destinations not implemented yet)

## Defer until the matching EPIC lands

- Per-domain pages (flows, execution, catalog)
- MCP tool catalogs and HTTP route maps
- Destination writers, LangGraph graphs, SQLite table schemas

## Maintenance

When an EPIC merges domain logic, update the matching page in `docs/agents/` in the same PR (or immediately after). Change [AGENTS.md](../../AGENTS.md) only when coding rules change.
