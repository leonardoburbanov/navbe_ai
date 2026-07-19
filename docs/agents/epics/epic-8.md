# EPIC 8 — FastAPI Wiring + dependencies.py

**Status:** done  
**Goal:** Shared DI providers, combined FastAPI + FastMCP process, thin REST mirror for flows/runs.  
**Non-goal:** New domain logic; agent-facing features stay on MCP.

## Delivered

| Area | Location |
| --- | --- |
| DI providers | `src/navbe/dependencies.py` (+ `clear_dependency_caches`) |
| App entry | `src/navbe/main.py` (`create_app`, `/health`, MCP mount) |
| REST flows | `src/navbe/api/v1/routes/flows.py` |
| REST runs | `src/navbe/api/v1/routes/runs.py` |
| Error map | `src/navbe/api/errors.py` (422/404/500) |

## FastMCP mount (verified)

Installed `fastmcp` 3.4.x: `mcp_http = mcp.http_app(path="/")`, pass `lifespan=mcp_http.lifespan` (wrapped with DB `create_all`), then `app.mount("/mcp", mcp_http)`.

## Definition of Done

- [x] `uv run pytest tests/unit/test_dependencies.py -v` green (singletons + cache_clear)
- [x] `uv run pytest tests/unit/api -v` green
- [x] `uv run pytest tests/integration/test_main_app.py -v` green (`/health` + MCP initialize)
- [x] FastMCP mount method verified against installed version
- [x] `uv run ruff check .` / `uv run ty check src/` → 0 errors
- [x] `uv run lint-imports` → 0 violations
- [x] NavbeError → HTTP status mapping tested
- [x] AST thin-route check (`tests/unit/test_no_route_logic_duplication.py`)
- [x] `create_app()` starts with real wired dependencies

## Notes

- `LangGraphEngine` is wired with `resolve_connectors` / `get_flow_spec` (not a raw `connector_service` kwarg).
- Checkpoint SQLite is a sibling file (`*_checkpoints.db`) to avoid sharing the control-plane DB.
