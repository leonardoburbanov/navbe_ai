# EPIC 7 — MCP App (FastMCP Server)

**Status:** done  
**Goal:** Expose flows/execution/catalog to agents via FastMCP tools and resources.  
**Non-goal:** Full DI wiring in `dependencies.py` (EPIC 8); HTTP API routes.

## Delivered

| Area | Location |
| --- | --- |
| Server factory | `src/navbe/mcp_app/server.py` |
| Tools | `src/navbe/mcp_app/tools.py` (`flow_*`; discovery tools added in EPIC 10) |
| Resources | `src/navbe/mcp_app/resources.py` (`navbe://catalog/*`) |
| Error adapter | `src/navbe/mcp_app/errors.py` → FastMCP `ToolError` + JSON payload |
| Background runs | `RunService.start` schedules `engine.run` via `asyncio.create_task` |
| Standalone integration | `tests/integration/test_mcp_server_standalone.py` |

## Tools

- `flow_create` / `flow_validate` / `flow_run` / `flow_status` / `flow_resume` / `flow_list_runs`

## Resources

- `navbe://catalog/steps`
- `navbe://catalog/connectors`
- `navbe://catalog/full`

## Definition of Done

- [x] `uv run pytest tests/unit/mcp_app -v` all green
- [x] `uv run pytest tests/integration/test_mcp_server_standalone.py -v` green
- [x] `uv run ruff check .` → 0 errors
- [x] `uv run ty check src/navbe/mcp_app` → 0 errors
- [x] `uv run lint-imports` → 0 violations
- [x] NavbeError → structured `ToolError` (never raw traceback to client)
- [x] `flow_run` returns before multi-node execution completes
- [x] pydantic ValidationError normalized in `flow_validate`
- [x] `list_runs` ordered most-recent-first (`updated_at` desc)
- [x] Resume of non-paused run raises `ExecutionError`

## Notes

- Dependencies are injected into `create_mcp_server` (no service construction in `mcp_app/`).
- Error contract: raise `ToolError(json.dumps({error, code, message, details}))`.
